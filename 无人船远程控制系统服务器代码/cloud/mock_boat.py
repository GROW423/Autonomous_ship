#!/usr/bin/env python3
"""
无人船模拟数据生成器
连接到云平台MAVLink网关，发送模拟的飞控数据，用于前端测试
用法: python mock_boat.py [--host 127.0.0.1] [--port 5760] [--iccid TESTICCID001]
"""
import socket
import time
import math
import argparse
import sys
from pymavlink import mavutil


class MockBoat:
    def __init__(self, host="127.0.0.1", port=5760, iccid="TESTICCID001", sys_id=1):
        self.host = host
        self.port = port
        self.iccid = iccid
        self.sys_id = sys_id
        self.mav = None
        self.running = False

        # 模拟船的初始位置 (广州南沙附近)
        self.base_lat = 22.8037  # 纬度
        self.base_lon = 113.5333  # 经度
        self.heading = 90.0  # 初始航向 (东)
        self.speed = 1.5  # 速度 m/s
        self.waypoint_index = 0

        # 模拟状态
        self.battery_voltage = 24.5  # V
        self.battery_current = 15.0  # A
        self.battery_remaining = 85  # %
        self.feed_level = 92  # 饲料余量 %
        self.cellular_csq = 18  # 4G信号
        self.box_temp = 35.5  # 箱内温度
        self.flight_mode = 10  # AUTO
        self.armed = True
        self.satellites = 14

        # 矩形巡逻路径 (相对base的偏移, 单位: 度)
        self.path = [
            (0.001, 0.0),    # 东
            (0.001, 0.001),  # 东北
            (0.0, 0.001),    # 北
            (0.0, 0.0),      # 返回起点
        ]
        self.target_wp = 0
        self.lat = self.base_lat
        self.lon = self.base_lon

    def connect(self):
        """连接到MAVLink网关"""
        print(f"[连接] 正在连接到 {self.host}:{self.port} ...")
        while True:
            try:
                # 使用pymavlink的TCP客户端方式 (pymavlink 2.4.49)
                self.mav = mavutil.mavlink_connection(
                    f"tcp:{self.host}:{self.port}",
                    source_system=self.sys_id,
                    source_component=1,
                )
                print(f"[连接] 已连接到 {self.host}:{self.port}")
                print(f"[身份] sys_id={self.sys_id}, ICCID={self.iccid}")
                return True
            except Exception as e:
                print(f"[连接] 失败: {e}, 3秒后重试...")
                time.sleep(3)

    def send_heartbeat(self):
        """发送心跳包"""
        self.mav.mav.heartbeat_send(
            type=mavutil.mavlink.MAV_TYPE_SURFACE_BOAT,  # 水面船
            autopilot=mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA,
            base_mode=(mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED if self.armed else 0) |
                       mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            custom_mode=self.flight_mode,
            system_status=mavutil.mavlink.MAV_STATE_ACTIVE,
        )

    def send_identity(self):
        """发送船身份信息 (ICCID)"""
        text = f"BOAT_ID:{self.iccid}"
        self.mav.mav.statustext_send(
            severity=mavutil.mavlink.MAV_SEVERITY_INFO,
            text=text.encode("utf-8") + b"\x00" * (50 - len(text)),
        )
        print(f"[身份] 上报ICCID: {self.iccid}")

    def send_global_position(self):
        """发送全局位置"""
        lat_int = int(self.lat * 1e7)
        lon_int = int(self.lon * 1e7)
        heading_cd = int(self.heading * 100)

        # 计算速度分量
        vx = int(self.speed * math.cos(math.radians(self.heading)) * 100)
        vy = int(self.speed * math.sin(math.radians(self.heading)) * 100)

        self.mav.mav.global_position_int_send(
            time_boot_ms=int(time.time() * 1000) % 4294967295,
            lat=lat_int,
            lon=lon_int,
            alt=0,
            relative_alt=0,
            vx=vx,
            vy=vy,
            vz=0,
            hdg=heading_cd,
        )

    def send_sys_status(self):
        """发送系统状态 (电池)"""
        voltage_mv = int(self.battery_voltage * 1000)
        current_ca = int(self.battery_current * 100)

        self.mav.mav.sys_status_send(
            onboard_control_sensors_present=0b11111111111111111111111111111111,
            onboard_control_sensors_enabled=0b11111111111111111111111111111111,
            onboard_control_sensors_health=0b11111111111111111111111111111111,
            load=15,
            voltage_battery=voltage_mv,
            current_battery=current_ca,
            battery_remaining=int(self.battery_remaining),
            drop_rate_comm=0,
            errors_comm=0,
            errors_count1=0,
            errors_count2=0,
            errors_count3=0,
            errors_count4=0,
        )

    def send_vfr_hud(self):
        """发送VFR HUD (速度、航向、油门)"""
        self.mav.mav.vfr_hud_send(
            airspeed=self.speed,
            groundspeed=self.speed,
            heading=int(self.heading),
            throttle=65,
            alt=0.0,
            climb=0.0,
        )

    def send_gps_raw_int(self):
        """发送GPS原始数据"""
        self.mav.mav.gps_raw_int_send(
            time_usec=int(time.time() * 1e6),
            fix_type=3,  # 3D_FIX
            lat=int(self.lat * 1e7),
            lon=int(self.lon * 1e7),
            alt=0,
            eph=100,  # HDOP 1.0
            epv=100,
            vel=int(self.speed * 100),
            cog=int(self.heading * 100),
            satellites_visible=self.satellites,
        )

    def send_attitude(self):
        """发送姿态"""
        self.mav.mav.attitude_send(
            time_boot_ms=int(time.time() * 1000) % 4294967295,
            roll=0.02,
            pitch=0.01,
            yaw=math.radians(self.heading),
            rollspeed=0.001,
            pitchspeed=0.001,
            yawspeed=0.005,
        )

    def send_named_value(self, name, value):
        """发送自定义浮点值 (料位、4G信号、温度)"""
        name_bytes = name.encode("utf-8")[:10]
        name_bytes = name_bytes + b"\x00" * (10 - len(name_bytes))
        self.mav.mav.named_value_float_send(
            time_boot_ms=int(time.time() * 1000) % 4294967295,
            name=name_bytes,
            value=value,
        )

    def send_mission_current(self):
        """发送当前航点"""
        self.mav.mav.mission_current_send(seq=self.target_wp)

    def update_position(self):
        """更新船的位置 (模拟沿路径移动)"""
        target_lat = self.base_lat + self.path[self.target_wp][0]
        target_lon = self.base_lon + self.path[self.target_wp][1]

        dlat = target_lat - self.lat
        dlon = target_lon - self.lon
        distance = math.sqrt(dlat**2 + dlon**2)

        if distance < 0.0001:
            # 到达目标点, 切换到下一个
            self.target_wp = (self.target_wp + 1) % len(self.path)
            print(f"[导航] 到达航点 {self.target_wp}, 前往下一个")
        else:
            # 向目标点移动
            step = self.speed * 0.1 / 111000  # 100ms移动的距离 (度)
            if step > distance:
                self.lat = target_lat
                self.lon = target_lon
            else:
                self.lat += dlat / distance * step
                self.lon += dlon / distance * step
                self.heading = math.degrees(math.atan2(dlon, dlat))
                if self.heading < 0:
                    self.heading += 360

        # 模拟电池消耗
        self.battery_remaining = max(0, self.battery_remaining - 0.001)
        self.battery_voltage = 22.0 + (self.battery_remaining / 100) * 3.0

        # 模拟饲料消耗
        self.feed_level = max(0, self.feed_level - 0.005)

        # 模拟4G信号波动
        self.cellular_csq = 15 + int(5 * math.sin(time.time() / 10))

    def run(self):
        """主循环"""
        self.connect()
        self.running = True

        # 发送身份信息
        self.send_identity()
        time.sleep(0.5)

        last_heartbeat = 0
        last_position = 0
        last_status = 0
        last_gps = 0
        last_attitude = 0
        last_named = 0
        last_mission = 0
        last_identity = 0

        print("[运行] 开始发送模拟数据...")
        print(f"[运行] 初始位置: {self.lat:.6f}, {self.lon:.6f}")
        print(f"[运行] 按 Ctrl+C 停止")

        try:
            while self.running:
                now = time.time()

                # 心跳 1Hz
                if now - last_heartbeat >= 1.0:
                    self.send_heartbeat()
                    last_heartbeat = now

                # 位置 5Hz
                if now - last_position >= 0.2:
                    self.update_position()
                    self.send_global_position()
                    self.send_vfr_hud()
                    last_position = now

                # 系统状态 1Hz
                if now - last_status >= 1.0:
                    self.send_sys_status()
                    last_status = now

                # GPS 1Hz
                if now - last_gps >= 1.0:
                    self.send_gps_raw_int()
                    last_gps = now

                # 姿态 5Hz
                if now - last_attitude >= 0.2:
                    self.send_attitude()
                    last_attitude = now

                # 自定义值 0.5Hz
                if now - last_named >= 2.0:
                    self.send_named_value("feed_lvl", self.feed_level)
                    self.send_named_value("4g_csq", float(self.cellular_csq))
                    self.send_named_value("box_temp", self.box_temp)
                    last_named = now

                # 当前航点 0.2Hz
                if now - last_mission >= 5.0:
                    self.send_mission_current()
                    last_mission = now

                # 身份信息 每30秒重发一次
                if now - last_identity >= 30.0:
                    self.send_identity()
                    last_identity = now

                # 检查是否有来自网关的指令
                try:
                    msg = self.mav.recv_msg()
                    if msg:
                        msg_type = msg.get_type()
                        if msg_type != "BAD_DATA":
                            print(f"[指令] 收到: {msg_type}")
                except Exception:
                    pass

                time.sleep(0.05)

        except KeyboardInterrupt:
            print("\n[停止] 用户中断")
        except Exception as e:
            import traceback
            print(f"[错误] {e}")
            traceback.print_exc()
        finally:
            self.running = False
            print("[停止] 模拟船已停止")


def main():
    parser = argparse.ArgumentParser(description="无人船模拟数据生成器")
    parser.add_argument("--host", default="127.0.0.1", help="MAVLink网关地址")
    parser.add_argument("--port", type=int, default=5760, help="MAVLink网关端口")
    parser.add_argument("--iccid", default="TESTICCID001", help="模拟船ICCID")
    parser.add_argument("--sys-id", type=int, default=1, help="MAVLink系统ID")
    args = parser.parse_args()

    boat = MockBoat(
        host=args.host,
        port=args.port,
        iccid=args.iccid,
        sys_id=args.sys_id,
    )
    boat.run()


if __name__ == "__main__":
    main()
