"""
MAVLink消息解析器
从原始MAVLink消息中提取关键状态字段
"""
import time


class MavlinkParser:
    """解析MAVLink消息, 返回标准化的状态字典"""

    @staticmethod
    def parse_heartbeat(msg) -> dict:
        """解析心跳包 - 飞行模式、系统状态"""
        mode_map = {
            0: "MANUAL", 1: "ACRO", 2: "LEARNING", 3: "STEERING",
            4: "HOLD", 5: "LOITER", 6: "FOLLOW", 7: "SIMPLE",
            8: "DOCK", 10: "AUTO", 11: "RTL", 12: "SMART_RTL", 15: "GUIDED",
        }
        return {
            "flight_mode": mode_map.get(msg.custom_mode, f"UNKNOWN({msg.custom_mode})"),
            "flight_mode_raw": msg.custom_mode,
            "armed": bool(msg.base_mode & 0x80),  # MAV_MODE_FLAG_SAFETY_ARMED
            "system_status": msg.system_status,
            "mavtype": msg.type,
        }

    @staticmethod
    def parse_global_position(msg) -> dict:
        """解析全局位置 - 经纬度、高度、航向、速度"""
        return {
            "lat": msg.lat / 1e7,           # 度
            "lon": msg.lon / 1e7,           # 度
            "alt": msg.alt / 1000.0,        # 米 (相对海平面)
            "relative_alt": msg.relative_alt / 1000.0,  # 米 (相对起飞点)
            "heading": msg.hdg / 100.0,     # 度 (0-360, 0=北)
            "vx": msg.vx / 100.0,           # m/s
            "vy": msg.vy / 100.0,           # m/s
            "vz": msg.vz / 100.0,           # m/s
        }

    @staticmethod
    def parse_vfr_hud(msg) -> dict:
        """解析VFR HUD - 空速、地速、高度、油门"""
        return {
            "airspeed": msg.airspeed,        # m/s
            "groundspeed": msg.groundspeed,   # m/s
            "heading": msg.heading,           # 度
            "throttle": msg.throttle,         # % (0-100)
            "alt": msg.alt,                   # 米
            "climb": msg.climb,               # m/s
        }

    @staticmethod
    def parse_sys_status(msg) -> dict:
        """解析系统状态 - 电池电压、电流、剩余电量"""
        battery_remaining = msg.battery_remaining  # -1: 不支持, 0-100: 百分比
        return {
            "battery_voltage": msg.voltage_battery / 1000.0 if msg.voltage_battery != 65535 else None,  # V
            "battery_current": msg.current_battery / 100.0 if msg.current_battery != -1 else None,       # A
            "battery_remaining": battery_remaining if battery_remaining != -1 else None,                   # %
            "load": msg.load,                  # % (系统负载)
            "drop_rate_comm": msg.drop_rate_comm,  # 通信丢包率 %
            "errors_count": msg.errors_count,
        }

    @staticmethod
    def parse_mission_current(msg) -> dict:
        """解析当前航点"""
        return {
            "current_waypoint": msg.seq,
        }

    @staticmethod
    def parse_mission_item_reached(msg) -> dict:
        """解析航点到达事件"""
        return {
            "reached_waypoint": msg.seq,
        }

    @staticmethod
    def parse_named_value_float(msg) -> dict:
        """解析自定义浮点值 (船端sensor_monitor上报的料位/4G信号/温度)"""
        name = msg.name.decode("utf-8", errors="ignore").strip("\x00")
        value = msg.value
        # 映射到标准字段名
        field_map = {
            "feed_lvl": "feed_level",       # 饲料余量 %
            "feed_dist": "feed_distance",    # 料位距离 cm
            "4g_csq": "cellular_csq",        # 4G信号
            "box_temp": "box_temperature",   # 箱内温度
        }
        field = field_map.get(name, f"custom_{name}")
        return {field: value}

    @staticmethod
    def parse_status_text(msg) -> dict:
        """解析状态文本 (告警信息)"""
        severity_map = {
            0: "EMERGENCY", 1: "ALERT", 2: "CRITICAL", 3: "ERROR",
            4: "WARNING", 5: "NOTICE", 6: "INFO", 7: "DEBUG",
        }
        text = msg.text.decode("utf-8", errors="ignore").strip("\x00")
        return {
            "last_status_text": text,
            "last_status_severity": severity_map.get(msg.severity, "UNKNOWN"),
            "last_status_time": time.time(),
        }

    @staticmethod
    def parse_gps_raw_int(msg) -> dict:
        """解析GPS原始数据 - 卫星数、定位质量"""
        fix_type_map = {
            0: "NO_FIX", 1: "NO_FIX", 2: "2D_FIX", 3: "3D_FIX",
            4: "DGPS", 5: "RTK_FLOAT", 6: "RTK_FIX",
        }
        return {
            "gps_fix_type": fix_type_map.get(msg.fix_type, "UNKNOWN"),
            "gps_satellites_visible": msg.satellites_visible,
            "gps_hdop": msg.eph / 100.0 if msg.eph != 65535 else None,
        }

    @staticmethod
    def parse_attitude(msg) -> dict:
        """解析姿态 - 横滚、俯仰、偏航"""
        import math
        return {
            "roll": math.degrees(msg.roll),
            "pitch": math.degrees(msg.pitch),
            "yaw": math.degrees(msg.yaw),
        }

    @classmethod
    def parse(cls, msg) -> dict:
        """通用解析入口, 根据消息类型分发"""
        msg_type = msg.get_type()
        parser_map = {
            "HEARTBEAT": cls.parse_heartbeat,
            "GLOBAL_POSITION_INT": cls.parse_global_position,
            "VFR_HUD": cls.parse_vfr_hud,
            "SYS_STATUS": cls.parse_sys_status,
            "MISSION_CURRENT": cls.parse_mission_current,
            "MISSION_ITEM_REACHED": cls.parse_mission_item_reached,
            "NAMED_VALUE_FLOAT": cls.parse_named_value_float,
            "STATUSTEXT": cls.parse_status_text,
            "GPS_RAW_INT": cls.parse_gps_raw_int,
            "ATTITUDE": cls.parse_attitude,
        }
        parser = parser_map.get(msg_type)
        if parser:
            try:
                return parser(msg)
            except Exception as e:
                return {"_parse_error": f"{msg_type}: {e}"}
        return {}
