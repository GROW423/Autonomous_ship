#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
无人船投料控制系统
==================
功能:
  1. 通过MAVLink监听飞控状态 (飞行模式/航速/当前航点)
  2. 根据状态自动控制投料电机启停
  3. 根据船速实时调节投料量 (速度补偿, 保证单位面积投料均匀)
  4. 通过GPIO + 软件PWM驱动BTS7960电机模块

硬件接线 (OrangePi Zero2W -> BTS7960):
  GPIO12 (PWM)   -> BTS7960 PWM
  GPIO16 (EN)     -> BTS7960 R_EN + L_EN (短接)
  GPIO18 (DIR)    -> BTS7960 R_PWM (方向, 固定正转)
  GND             -> GND
  电机12V电源     -> BTS7960 VCC (独立供电, 非香橙派5V)

运行: /opt/usv/venv/bin/python /opt/usv/services/feeder_control.py
"""

import os
import sys
import time
import signal
import logging
import threading
from pathlib import Path

import yaml
from periphery import GPIO

# pymavlink
from pymavlink import mavutil

# ============================================================
# 配置加载
# ============================================================
CONFIG_PATH = os.environ.get(
    "FEEDER_CONFIG", "/opt/usv/config/feeder_config.yaml"
)


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ============================================================
# 软件PWM控制器
# ============================================================
class SoftwarePWM:
    """
    通过GPIO快速切换实现软件PWM.
    频率默认100Hz (周期10ms), 适合电机调速.
    Linux非实时系统, 高频PWM精度有限, 100Hz是可靠选择.
    """

    def __init__(self, pin, freq=100):
        self._gpio = GPIO(pin, "out")
        self._freq = freq
        self._period = 1.0 / freq
        self._duty = 0.0  # 0.0 - 1.0
        self._running = False
        self._thread = None
        self._lock = threading.Lock()

    def set_duty(self, duty):
        """设置占空比 0.0-1.0"""
        duty = max(0.0, min(1.0, duty))
        with self._lock:
            self._duty = duty

    def get_duty(self):
        with self._lock:
            return self._duty

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        self._gpio.write(False)

    def _loop(self):
        while self._running:
            with self._lock:
                duty = self._duty
            if duty <= 0.0:
                self._gpio.write(False)
                time.sleep(self._period)
                continue
            if duty >= 1.0:
                self._gpio.write(True)
                time.sleep(self._period)
                continue
            high_time = self._period * duty
            low_time = self._period * (1.0 - duty)
            self._gpio.write(True)
            time.sleep(high_time)
            self._gpio.write(False)
            time.sleep(low_time)

    def close(self):
        self.stop()
        self._gpio.close()


# ============================================================
# ArduPilot Rover 模式编号 (4.x固件)
# ============================================================
ROVER_MODES = {
    0: "MANUAL",
    1: "ACRO",
    2: "LEARNING",
    3: "STEERING",
    4: "HOLD",
    5: "LOITER",
    6: "FOLLOW",
    7: "SIMPLE",
    8: "DOCK",
    10: "AUTO",
    11: "RTL",
    12: "SMART_RTL",
    15: "GUIDED",
}


# ============================================================
# 投料控制器主类
# ============================================================
class FeederController:
    def __init__(self, config):
        self.cfg = config
        self.running = False

        # 飞控状态
        self.flight_mode = None
        self.ground_speed = 0.0
        self.current_waypoint = 0
        self.armed = False
        self.last_heartbeat = 0.0

        # 投料状态
        self.feeder_on = False
        self.current_duty = 0.0
        self.feeder_start_time = 0.0

        # 日志
        self._setup_logging()

        # GPIO初始化
        gpio_cfg = config["gpio"]
        self.log.info(f"初始化GPIO: PWM={gpio_cfg['pwm_pin']}, "
                       f"EN={gpio_cfg['enable_pin']}, DIR={gpio_cfg['direction_pin']}")

        self.pwm = SoftwarePWM(gpio_cfg["pwm_pin"], freq=config["feeder"]["pwm_freq"])
        self.enable_gpio = GPIO(gpio_cfg["enable_pin"], "out")
        self.direction_gpio = GPIO(gpio_cfg["direction_pin"], "out")

        # 方向固定正转
        self.direction_gpio.write(True)
        # 初始停止
        self.enable_gpio.write(False)
        self.pwm.set_duty(0.0)
        self.pwm.start()

        # MAVLink连接
        self.master = None

    def _setup_logging(self):
        log_cfg = self.cfg["logging"]
        self.log = logging.getLogger("feeder")
        self.log.setLevel(getattr(logging, log_cfg["level"]))
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        # 文件日志
        fh = logging.FileHandler(log_cfg["file"], encoding="utf-8")
        fh.setFormatter(formatter)
        self.log.addHandler(fh)
        # 控制台输出 (systemd journal)
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(formatter)
        self.log.addHandler(ch)

    def connect_mavlink(self):
        """连接本地mavlink-router的UDP端点"""
        conn_str = self.cfg["mavlink"]["connection"]
        self.log.info(f"连接MAVLink: {conn_str}")
        self.master = mavutil.mavlink_connection(conn_str)
        # 等待心跳包, 确认飞控在线
        self.log.info("等待飞控心跳包...")
        try:
            self.master.wait_heartbeat(timeout=10)
            self.log.info(f"飞控已连接: SYSID={self.master.target_system}")
            return True
        except Exception as e:
            self.log.error(f"等待心跳超时: {e}")
            return False

    def _process_message(self, msg):
        """处理MAVLink消息"""
        msg_type = msg.get_type()

        if msg_type == "HEARTBEAT":
            self.flight_mode = msg.custom_mode
            self.armed = (msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED) != 0
            self.last_heartbeat = time.time()
            mode_name = ROVER_MODES.get(self.flight_mode, f"UNKNOWN({self.flight_mode})")
            self.log.debug(f"模式: {mode_name}, 解锁: {self.armed}")

        elif msg_type == "VFR_HUD":
            self.ground_speed = msg.groundspeed
            self.log.debug(f"地速: {self.ground_speed:.2f} m/s")

        elif msg_type == "MISSION_CURRENT":
            self.current_waypoint = msg.seq
            self.log.debug(f"当前航点: {self.current_waypoint}")

    def _should_feed(self):
        """
        判断是否应该开启投料.
        条件:
          1. 飞控已解锁
          2. 飞行模式在自动投料列表中 (AUTO/GUIDED)
          3. 船速 > 最低速度阈值
          4. 当前航点 >= 起始航点 (跳过出发段)
        """
        auto_cfg = self.cfg["auto_feed"]

        if not self.armed:
            return False, "未解锁"

        if self.flight_mode is None:
            return False, "模式未知"

        if self.flight_mode in auto_cfg["stop_modes"]:
            return False, f"模式{ROVER_MODES.get(self.flight_mode, self.flight_mode)}禁止投料"

        if self.flight_mode not in auto_cfg["auto_modes"]:
            return False, f"模式{ROVER_MODES.get(self.flight_mode, self.flight_mode)}非自动模式"

        if self.ground_speed < auto_cfg["min_speed"]:
            return False, f"船速{self.ground_speed:.2f}低于阈值{auto_cfg['min_speed']}"

        if self.current_waypoint < auto_cfg["start_waypoint"]:
            return False, f"航点{self.current_waypoint}未到起始航点"

        return True, "正常投料"

    def _calc_duty(self):
        """
        根据船速计算PWM占空比 (速度补偿).
        船速越快 -> 占空比越高 -> 投料量越大, 保证单位面积投料均匀.
        """
        feeder_cfg = self.cfg["feeder"]
        target_speed = feeder_cfg["target_speed"]

        if target_speed <= 0:
            return feeder_cfg["base_duty"]

        # 速度补偿系数 = 当前速度 / 目标速度
        speed_factor = self.ground_speed / target_speed
        duty = feeder_cfg["base_duty"] * speed_factor

        # 限制范围
        duty = max(feeder_cfg["min_duty"], min(feeder_cfg["max_duty"], duty))
        return duty

    def _start_feeder(self):
        """启动投料电机"""
        if self.feeder_on:
            return
        feeder_cfg = self.cfg["feeder"]
        self.log.info("启动投料电机")
        self.enable_gpio.write(True)
        # 预热: 先以最小占空比运转, 避免堵转
        self.pwm.set_duty(feeder_cfg["min_duty"])
        self.feeder_start_time = time.time()
        self.feeder_on = True

    def _stop_feeder(self):
        """停止投料电机"""
        if not self.feeder_on:
            return
        self.log.info("停止投料电机")
        self.pwm.set_duty(0.0)
        self.enable_gpio.write(False)
        self.feeder_on = False
        self.current_duty = 0.0

    def _update_feeder(self):
        """更新投料状态和速度"""
        should_feed, reason = self._should_feed()

        if should_feed:
            if not self.feeder_on:
                self._start_feeder()
            # 预热期过后再调速
            elapsed = time.time() - self.feeder_start_time
            if elapsed >= self.cfg["feeder"]["warmup_time"]:
                duty = self._calc_duty()
                if abs(duty - self.current_duty) > 0.01:
                    self.pwm.set_duty(duty)
                    self.current_duty = duty
                    self.log.debug(
                        f"投料: 速度={self.ground_speed:.2f}m/s, "
                        f"占空比={duty:.2f}, 航点={self.current_waypoint}"
                    )
        else:
            if self.feeder_on:
                self.log.info(f"停止投料: {reason}")
                self._stop_feeder()

    def run(self):
        """主循环"""
        self.running = True
        self.log.info("投料控制器启动")

        # 连接MAVLink (带重连)
        while self.running and not self.connect_mavlink():
            self.log.warning("MAVLink连接失败, 5秒后重试...")
            time.sleep(5)

        if not self.running:
            return

        self.log.info("进入主循环")
        last_log = 0.0

        try:
            while self.running:
                # 非阻塞接收MAVLink消息
                msg = self.master.recv_msg()
                if msg:
                    self._process_message(msg)

                # 更新投料状态 (每100ms)
                self._update_feeder()

                # 心跳超时检测
                if time.time() - self.last_heartbeat > 5.0 and self.last_heartbeat > 0:
                    self.log.warning("飞控心跳超时, 停止投料")
                    self._stop_feeder()
                    self.armed = False

                # 状态日志 (每5秒)
                if time.time() - last_log > 5.0:
                    mode_name = ROVER_MODES.get(self.flight_mode, "?")
                    self.log.info(
                        f"状态: 模式={mode_name}, 解锁={self.armed}, "
                        f"速度={self.ground_speed:.2f}m/s, 航点={self.current_waypoint}, "
                        f"投料={'ON' if self.feeder_on else 'OFF'}, "
                        f"占空比={self.current_duty:.2f}"
                    )
                    last_log = time.time()

                time.sleep(0.05)  # 20Hz循环

        except KeyboardInterrupt:
            self.log.info("收到中断信号")
        finally:
            self.shutdown()

    def shutdown(self):
        """优雅关闭"""
        self.running = False
        self.log.info("关闭投料控制器")
        self._stop_feeder()
        self.pwm.close()
        self.enable_gpio.close()
        self.direction_gpio.close()
        if self.master:
            self.master.close()
        self.log.info("投料控制器已关闭")


# ============================================================
# 信号处理
# ============================================================
controller = None


def signal_handler(signum, frame):
    global controller
    if controller:
        controller.running = False


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    config = load_config()
    controller = FeederController(config)
    controller.run()
