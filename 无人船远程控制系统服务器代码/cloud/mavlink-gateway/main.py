"""
MAVLink Gateway - 船端通信网关主入口
监听TCP端口, 接受每艘船的mavlink-router连接, 解析MAVLink消息,
实时状态写入Redis, 历史数据写入PostgreSQL, 并转发API下发的指令.
"""
import socket
import logging
import signal
import sys

from config import config
from redis_store import RedisStore
from db_writer import DbWriter
from boat_connection import BoatConnection


def setup_logging():
    """配置日志"""
    level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main():
    setup_logging()
    log = logging.getLogger("gateway")

    log.info("=" * 60)
    log.info("无人船 MAVLink 网关启动")
    log.info(f"监听端口: {config.MAVLINK_TCP_PORT}")
    log.info(f"Redis: {config.REDIS_URL}")
    log.info("=" * 60)

    # 初始化Redis和数据库
    try:
        redis_store = RedisStore()
        log.info("Redis连接成功")
    except Exception as e:
        log.error(f"Redis连接失败: {e}")
        sys.exit(1)

    try:
        db_writer = DbWriter()
        log.info("数据库连接成功")
    except Exception as e:
        log.error(f"数据库连接失败: {e}")
        sys.exit(1)

    # 创建TCP socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("0.0.0.0", config.MAVLINK_TCP_PORT))
    server_socket.listen(16)
    server_socket.settimeout(1.0)

    log.info(f"等待船端连接 (端口 {config.MAVLINK_TCP_PORT})...")

    running = True

    def signal_handler(sig, frame):
        nonlocal running
        log.info("收到退出信号, 正在关闭...")
        running = False

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    connections = []

    try:
        while running:
            try:
                conn, addr = server_socket.accept()
            except socket.timeout:
                continue
            except Exception as e:
                if running:
                    log.error(f"接受连接异常: {e}")
                continue

            log.info(f"新连接: {addr}")
            boat = BoatConnection(conn, addr, redis_store, db_writer)
            boat.start()
            connections.append(boat)

            # 清理已结束的连接
            connections = [c for c in connections if c.is_alive()]

    finally:
        log.info("关闭网关...")
        running = False
        for c in connections:
            c.running = False
        server_socket.close()
        db_writer.close()
        log.info("网关已关闭")


if __name__ == "__main__":
    main()
