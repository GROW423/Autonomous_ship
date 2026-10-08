#!/usr/bin/env python3
"""
船端身份识别服务
- 通过AT命令读取移远4G模块的ICCID
- 通过MAVLink STATUSTEXT消息上报给云平台网关
- 网关收到ICCID后查询数据库, 映射到正式boat_key
- 每30秒上报一次, 确保连接重建后能重新识别
"""
import time
import logging
import serial
from pymavlink import mavutil

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger('boat_identity')

# ============================================================
# 配置
# ============================================================
# 移远4G模块AT命令串口 (EC200S通常是 /dev/ttyUSB2)
AT_PORT = '/dev/ttyUSB2'
AT_BAUDRATE = 115200

# MAVLink上报地址 (本地mavlink-router的UDP端口)
MAVLINK_UDP_HOST = '127.0.0.1'
MAVLINK_UDP_PORT = 14550

# 上报间隔 (秒)
REPORT_INTERVAL = 30

# 重试间隔 (读取ICCID失败时)
RETRY_INTERVAL = 5


def read_iccid() -> str | None:
    """
    通过AT命令读取移远4G模块的ICCID
    返回20位ICCID字符串, 失败返回None
    """
    try:
        ser = serial.Serial(AT_PORT, AT_BAUDRATE, timeout=3)
        # 先发送AT测试连接
        ser.write(b'AT\r\n')
        time.sleep(0.3)
        ser.read(ser.in_waiting)  # 清空缓冲区

        # 读取ICCID (移远专用命令)
        ser.write(b'AT+QCCID\r\n')
        time.sleep(0.5)
        response = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
        ser.close()

        # 解析响应: +QCCID: 898604A1192070012345
        for line in response.split('\n'):
            line = line.strip()
            if '+QCCID:' in line:
                iccid = line.split('+QCCID:')[1].strip()
                # 移远模块返回的ICCID可能有奇偶位交换, 取原始值即可
                if iccid and len(iccid) >= 15:
                    return iccid

        log.warning(f"QCCID解析失败, 原始响应: {response.strip()}")
        return None

    except serial.SerialException as e:
        log.error(f"串口打开失败 ({AT_PORT}): {e}")
        return None
    except Exception as e:
        log.error(f"读取ICCID异常: {e}")
        return None


def read_iccid_with_retry(max_retries: int = 3) -> str | None:
    """带重试的ICCID读取"""
    for i in range(max_retries):
        iccid = read_iccid()
        if iccid:
            return iccid
        log.info(f"第{i+1}次读取失败, {RETRY_INTERVAL}秒后重试...")
        time.sleep(RETRY_INTERVAL)
    return None


def report_identity(mav, iccid: str):
    """
    通过MAVLink STATUSTEXT消息上报船身份
    格式: BOAT_ID:<ICCID>
    """
    try:
        text = f"BOAT_ID:{iccid}"
        # STATUSTEXT消息最多50字符, BOAT_ID:+20位ICCID=28字符, 没问题
        mav.mav.statustext_send(
            mavutil.mavlink.MAV_SEVERITY_INFO,
            text.encode('utf-8')
        )
        log.info(f"身份上报成功: {text}")
    except Exception as e:
        log.error(f"身份上报失败: {e}")


def main():
    log.info("=" * 50)
    log.info("船端身份识别服务启动")
    log.info(f"AT端口: {AT_PORT}")
    log.info(f"MAVLink上报: {MAVLINK_UDP_HOST}:{MAVLINK_UDP_PORT}")
    log.info("=" * 50)

    # 1. 读取ICCID (启动时读取一次, 带重试)
    iccid = read_iccid_with_retry(max_retries=5)
    if not iccid:
        log.error("无法读取ICCID, 服务退出")
        return

    log.info(f"读取到ICCID: {iccid}")

    # 2. 建立MAVLink连接 (UDP输出到本地mavlink-router)
    try:
        mav = mavutil.mavlink_connection(
            f'udpout:{MAVLINK_UDP_HOST}:{MAVLINK_UDP_PORT}',
            source_system=1,   # 与飞控sys_id一致即可, 网关不依赖这个
            source_component=mavutil.mavlink.MAV_COMP_ID_ONBOARD_COMPUTER,
        )
        log.info("MAVLink UDP连接建立")
    except Exception as e:
        log.error(f"MAVLink连接失败: {e}")
        return

    # 3. 主循环: 定时上报身份
    consecutive_failures = 0
    while True:
        try:
            report_identity(mav, iccid)
            consecutive_failures = 0
        except Exception as e:
            consecutive_failures += 1
            log.error(f"上报异常 ({consecutive_failures}次): {e}")
            # 连续失败超过10次, 重新读取ICCID和重建MAVLink连接
            if consecutive_failures >= 10:
                log.warning("连续失败过多, 重新初始化...")
                try:
                    mav.close()
                except Exception:
                    pass
                iccid = read_iccid_with_retry(max_retries=3) or iccid
                try:
                    mav = mavutil.mavlink_connection(
                        f'udpout:{MAVLINK_UDP_HOST}:{MAVLINK_UDP_PORT}',
                        source_system=1,
                        source_component=mavutil.mavlink.MAV_COMP_ID_ONBOARD_COMPUTER,
                    )
                except Exception as e2:
                    log.error(f"重建MAVLink连接失败: {e2}")
                consecutive_failures = 0

        time.sleep(REPORT_INTERVAL)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        log.info("服务被用户中断")
    except Exception as e:
        log.error(f"服务异常退出: {e}", exc_info=True)
