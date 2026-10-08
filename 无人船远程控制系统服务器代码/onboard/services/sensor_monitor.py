#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
无人船传感器监控与上报系统
============================
功能:
  1. 读取料位传感器 (JSN-SR04T防水超声波), 换算饲料余量百分比
  2. 读取4G模块信号强度 (AT+CSQ)
  3. 读取箱内温度 (CPU温度作为参考, 或外接DS18B20)
  4. 通过MAVLink NAMED_VALUE_FLOAT消息上报自定义数据
  5. 异常状态通过STATUSTEXT告警上报

硬件接线:
  JSN-SR04T (料位传感器, 安装在料斗顶部):
    VCC  -> 5V
    Trig -> GPIO20 (Physical pin 38)
    Echo -> GPIO21 (Physical pin 40)
    GND  -> GND

  4G模块 (移远EC200S):
    AT指令端口 -> /dev/ttyUSB2 (通常)

上报的MAVLink自定义数据 (NAMED_VALUE_FLOAT):
  feed_lvl   - 饲料余量百分比 (0-100)
  feed_dist  - 料位传感器原始距离 (cm)
  4g_csq     - 4G信号强度 (0-31, 99=无信号)
  box_temp   - 箱内温度 (℃)

运行: /opt/usv/venv/bin/python /opt/usv/services/sensor_monitor.py
"""

import os
import sys
import time
import signal
import logging
import threading
from pathlib import Path

import yaml
import serial
from periphery import GPIO

from pymavlink import mavutil

# ============================================================
# 配置
# ============================================================
CONFIG_PATH = os.environ.get(
    "SENSOR_CONFIG", "/opt/usv/config/sensor_config.yaml"
)

# 默认配置 (如果配置文件不存在则使用)
DEFAULT_CONFIG = {
    "mavlink": {
        "connection": "udp:127.0.0.1:14550",
        "source_system": 1,
        "source_component": 1,
    },
    "ultrasonic": {
        "trig_pin": 20,
        "echo_pin": 21,
        # 料斗参数 (用于距离->余量百分比换算)
        "hopper_full_cm": 5.0,    # 满料时传感器到料面距离
        "hopper_empty_cm": 50.0,   # 空料时传感器到料底距离
        "timeout_ms": 50,           # 超声波超时
    },
    "cellular": {
        "at_port": "/dev/ttyUSB2",
        "baud": 115200,
        "enabled": True,
    },
    "temperature": {
        # 使用CPU温度作为箱内参考 (路径根据系统调整)
        "cpu_temp_path": "/sys/class/thermal/thermal_zone0/temp",
        "enabled": True,
    },
    "report": {
        "interval_sec": 2.0,  # 上报间隔
    },
    "logging": {
        "level": "INFO",
        "file": "/opt/usv/logs/sensor.log",
    },
}


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return DEFAULT_CONFIG


# ============================================================
# 超声波测距 (JSN-SR04T)
# ============================================================
class UltrasonicSensor:
    """JSN-SR04T防水超声波测距传感器"""

    SOUND_SPEED = 343.0  # m/s, 20℃空气中声速

    def __init__(self, trig_pin, echo_pin, timeout_ms=50):
        self.trig = GPIO(trig_pin, "out")
        self.echo = GPIO(echo_pin, "in")
        self.timeout = timeout_ms / 1000.0
        self.trig.write(False)
        time.sleep(0.05)  # 传感器稳定

    def read_distance_cm(self):
        """
        读取距离 (cm).
        返回: 距离值, 失败返回None
        """
        # 发送10us触发脉冲
        self.trig.write(False)
        time.sleep(0.002)
        self.trig.write(True)
        time.sleep(0.00001)  # 10us
        self.trig.write(False)

        # 等待回波高电平开始
        start_time = time.perf_counter()
        while not self.echo.read():
            if time.perf_counter() - start_time > self.timeout:
                return None

        # 测量高电平持续时间
        pulse_start = time.perf_counter()
        while self.echo.read():
            if time.perf_counter() - pulse_start > self.timeout:
                return None
        pulse_end = time.perf_counter()

        pulse_duration = pulse_end - pulse_start
        # 距离 = 时间 * 声速 / 2 (往返)
        distance_m = pulse_duration * self.SOUND_SPEED / 2.0
        distance_cm = distance_m * 100.0
        return distance_cm

    def read_distance_avg(self, samples=3):
        """多次测量取平均, 过滤异常值"""
        distances = []
        for _ in range(samples):
            d = self.read_distance_cm()
            if d is not None and 2.0 < d < 400.0:
                distances.append(d)
            time.sleep(0.02)
        if not distances:
            return None
        return sum(distances) / len(distances)

    def close(self):
        self.trig.close()
        self.echo.close()


# ============================================================
# 4G信号读取
# ============================================================
class CellularMonitor:
    """通过AT指令读取4G模块信号强度"""

    def __init__(self, port, baud=115200):
        self.port = port
        self.baud = baud
        self.ser = None

    def connect(self):
        try:
            self.ser = serial.Serial(
                self.port, self.baud, timeout=1, write_timeout=1
            )
            time.sleep(0.5)
            # 测试AT
            self.ser.write(b"AT\r")
            resp = self.ser.read(100).decode("ascii", errors="ignore")
            if "OK" in resp:
                return True
            return False
        except Exception as e:
            logging.getLogger("sensor").warning(f"4G模块连接失败: {e}")
            return False

    def read_signal(self):
        """
        读取信号强度 CSQ.
        返回: 0-31 (信号强度), 99=未知/无信号, 失败返回None
        """
        if not self.ser or not self.ser.is_open:
            if not self.connect():
                return None
        try:
            self.ser.reset_input_buffer()
            self.ser.write(b"AT+CSQ\r")
            time.sleep(0.3)
            resp = self.ser.read(200).decode("ascii", errors="ignore")
            # 响应格式: +CSQ: 24,99
            if "+CSQ:" in resp:
                parts = resp.split("+CSQ:")[1].split(",")
                csq = int(parts[0].strip())
                return csq
            return None
        except Exception as e:
            logging.getLogger("sensor").debug(f"读取4G信号失败: {e}")
            # 尝试重连
            try:
                if self.ser:
                    self.ser.close()
            except Exception:
                pass
            self.ser = None
            return None

    def close(self):
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass


# ============================================================
# 温度读取
# ============================================================
def read_cpu_temp(path):
    """读取CPU温度作为箱内参考 (返回℃)"""
    try:
        with open(path, "r") as f:
            raw = f.read().strip()
            return int(raw) / 1000.0
    except Exception:
        return None


# ============================================================
# 传感器监控主类
# ============================================================
class SensorMonitor:
    def __init__(self, config):
        self.cfg = config
        self.running = False

        # 日志
        self._setup_logging()

        # 传感器初始化
        us_cfg = config["ultrasonic"]
        self.log.info(f"初始化超声波传感器: TRIG={us_cfg['trig_pin']}, "
                       f"ECHO={us_cfg['echo_pin']}")
        self.ultrasonic = UltrasonicSensor(
            us_cfg["trig_pin"], us_cfg["echo_pin"], us_cfg["timeout_ms"]
        )

        # 4G监控
        self.cellular = None
        if config["cellular"]["enabled"]:
            self.cellular = CellularMonitor(
                config["cellular"]["at_port"],
                config["cellular"]["baud"],
            )

        # MAVLink连接
        self.master = None

        # 缓存的传感器数据
        self.data = {
            "feed_level": 0.0,
            "feed_distance": 0.0,
            "4g_csq": 99,
            "box_temp": 0.0,
        }

    def _setup_logging(self):
        log_cfg = self.cfg["logging"]
        self.log = logging.getLogger("sensor")
        self.log.setLevel(getattr(logging, log_cfg["level"]))
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        fh = logging.FileHandler(log_cfg["file"], encoding="utf-8")
        fh.setFormatter(formatter)
        self.log.addHandler(fh)
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(formatter)
        self.log.addHandler(ch)

    def connect_mavlink(self):
        conn_str = self.cfg["mavlink"]["connection"]
        self.log.info(f"连接MAVLink: {conn_str}")
        self.master = mavutil.mavlink_connection(conn_str)
        try:
            self.master.wait_heartbeat(timeout=10)
            self.log.info(f"MAVLink已连接: SYSID={self.master.target_system}")
            return True
        except Exception as e:
            self.log.error(f"等待心跳超时: {e}")
            return False

    def _distance_to_feed_level(self, distance_cm):
        """
        将超声波距离换算为饲料余量百分比.
        距离越小 -> 料越满 -> 百分比越高.
        """
        us_cfg = self.cfg["ultrasonic"]
        full = us_cfg["hopper_full_cm"]
        empty = us_cfg["hopper_empty_cm"]

        if distance_cm <= full:
            return 100.0
        if distance_cm >= empty:
            return 0.0
        # 线性插值
        level = (empty - distance_cm) / (empty - full) * 100.0
        return max(0.0, min(100.0, level))

    def _read_all_sensors(self):
        """读取所有传感器数据"""
        # 料位
        dist = self.ultrasonic.read_distance_avg(samples=3)
        if dist is not None:
            self.data["feed_distance"] = dist
            self.data["feed_level"] = self._distance_to_feed_level(dist)
        else:
            self.log.warning("料位传感器读取失败")

        # 4G信号
        if self.cellular:
            csq = self.cellular.read_signal()
            if csq is not None:
                self.data["4g_csq"] = csq

        # 温度
        if self.cfg["temperature"]["enabled"]:
            temp = read_cpu_temp(self.cfg["temperature"]["cpu_temp_path"])
            if temp is not None:
                self.data["box_temp"] = temp

    def _report_mavlink(self):
        """通过MAVLink NAMED_VALUE_FLOAT上报数据"""
        if not self.master:
            return

        src_sys = self.cfg["mavlink"]["source_system"]
        src_comp = self.cfg["mavlink"]["source_component"]

        # 上报饲料余量
        self.master.mav.named_value_float_send(
            int(time.time()),  # time_boot_ms (用时间戳)
            b"feed_lvl",
            self.data["feed_level"],
        )

        # 上报料位距离
        self.master.mav.named_value_float_send(
            int(time.time()),
            b"feed_dist",
            self.data["feed_distance"],
        )

        # 上报4G信号
        self.master.mav.named_value_float_send(
            int(time.time()),
            b"4g_csq",
            float(self.data["4g_csq"]),
        )

        # 上报温度
        self.master.mav.named_value_float_send(
            int(time.time()),
            b"box_temp",
            self.data["box_temp"],
        )

    def _check_alerts(self):
        """检查异常状态, 通过STATUSTEXT告警"""
        if not self.master:
            return

        # 饲料不足告警 (<20%)
        if self.data["feed_level"] < 20.0 and self.data["feed_level"] > 0:
            self._send_status(f"WARNING: 饲料余量不足 {self.data['feed_level']:.0f}%",
                              severity=mavutil.mavlink.MAV_SEVERITY_WARNING)

        # 4G弱信号告警 (<=5)
        if 0 <= self.data["4g_csq"] <= 5:
            self._send_status(f"WARNING: 4G信号弱 CSQ={self.data['4g_csq']}",
                              severity=mavutil.mavlink.MAV_SEVERITY_WARNING)

        # 高温告警 (>60℃)
        if self.data["box_temp"] > 60.0:
            self._send_status(f"CRITICAL: 箱内温度过高 {self.data['box_temp']:.1f}℃",
                              severity=mavutil.mavlink.MAV_SEVERITY_CRITICAL)

    def _send_status(self, text, severity=mavutil.mavlink.MAV_SEVERITY_INFO):
        """发送STATUSTEXT消息"""
        if not self.master:
            return
        self.master.mav.statustext_send(
            severity,
            text.encode("utf-8")[:50],
        )
        self.log.info(f"STATUSTEXT: {text}")

    def run(self):
        """主循环"""
        self.running = True
        self.log.info("传感器监控启动")

        # 连接MAVLink
        while self.running and not self.connect_mavlink():
            self.log.warning("MAVLink连接失败, 5秒后重试...")
            time.sleep(5)

        if not self.running:
            return

        self._send_status("Sensor monitor online",
                          severity=mavutil.mavlink.MAV_SEVERITY_INFO)

        interval = self.cfg["report"]["interval_sec"]
        last_report = 0.0
        last_alert = 0.0

        try:
            while self.running:
                now = time.time()

                # 读取传感器
                self._read_all_sensors()

                # 周期上报
                if now - last_report >= interval:
                    self._report_mavlink()
                    self.log.info(
                        f"上报: 料位={self.data['feed_level']:.0f}% "
                        f"({self.data['feed_distance']:.1f}cm), "
                        f"4G CSQ={self.data['4g_csq']}, "
                        f"温度={self.data['box_temp']:.1f}℃"
                    )
                    last_report = now

                # 告警检查 (每30秒)
                if now - last_alert >= 30.0:
                    self._check_alerts()
                    last_alert = now

                time.sleep(1.0)

        except KeyboardInterrupt:
            self.log.info("收到中断信号")
        finally:
            self.shutdown()

    def shutdown(self):
        self.running = False
        self.log.info("关闭传感器监控")
        self.ultrasonic.close()
        if self.cellular:
            self.cellular.close()
        if self.master:
            self.master.close()
        self.log.info("传感器监控已关闭")


# ============================================================
# 入口
# ============================================================
monitor = None


def signal_handler(signum, frame):
    global monitor
    if monitor:
        monitor.running = False


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    config = load_config()
    monitor = SensorMonitor(config)
    monitor.run()
