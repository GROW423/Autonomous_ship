"""
MAVLink网关配置
"""
import os


class Config:
    # MAVLink TCP监听端口 (船端mavlink-router连接这里)
    MAVLINK_TCP_PORT = int(os.environ.get("MAVLINK_TCP_PORT", "5760"))

    # Redis
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    # PostgreSQL
    DATABASE_URL = os.environ.get(
        "DATABASE_URL", "postgresql://usv:usv_secret@localhost:5432/usv"
    )

    # 日志
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

    # 实时状态写入Redis的间隔 (秒) - 限制频率, 避免Redis压力过大
    STATUS_WRITE_INTERVAL = 1.0

    # 历史遥测数据批量写入PostgreSQL的间隔 (秒)
    HISTORY_BATCH_INTERVAL = 5.0

    # 历史遥测数据单条最小间隔 (秒) - 去重, 避免存太密
    HISTORY_MIN_INTERVAL = 2.0

    # 船端心跳超时 (秒) - 超过此时间没有心跳标记为离线
    BOAT_HEARTBEAT_TIMEOUT = 10.0


config = Config()
