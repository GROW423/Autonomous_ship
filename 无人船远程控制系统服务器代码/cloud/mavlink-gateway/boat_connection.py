"""
单船连接处理器
每艘船一个独立线程, 负责:
  1. 接收MAVLink消息 -> 解析 -> 更新Redis实时状态
  2. 批量写入PostgreSQL历史数据
  3. 订阅Redis指令通道 -> 转发MAVLink指令给船
  4. 心跳超时检测
"""
import socket
import time
import json
import threading
import logging
from pymavlink import mavutil

from config import config
from mavlink_parser import MavlinkParser
from redis_store import RedisStore
from db_writer import DbWriter


class SocketMavlink(mavutil.mavfile):
    """包装已有socket的MAVLink连接类 (pymavlink 2.4.49)"""
    def __init__(self, sock, address, source_system=255, source_component=0):
        self._sock = sock
        mavutil.mavfile.__init__(
            self, sock.fileno(), address,
            source_system=source_system,
            source_component=source_component,
        )

    def recv(self, n=None):
        if n is None:
            n = self.mav.bytes_needed()
        try:
            return self._sock.recv(n)
        except socket.error:
            return b''

    def write(self, buf):
        try:
            self._sock.send(buf)
        except socket.error:
            pass


class BoatConnection(threading.Thread):
    def __init__(self, conn: socket.socket, addr, redis_store: RedisStore, db_writer: DbWriter):
        super().__init__(daemon=True)
        self.conn = conn
        self.addr = addr
        self.redis = redis_store
        self.db = db_writer
        self.running = False

        # 船的标识 (从第一个HEARTBEAT的sys_id获取)
        self.boat_id = None
        self.mav = None

        # 合并的实时状态 (所有消息解析后合并到这里)
        self.status = {}
        self._last_status_write = 0
        self._last_heartbeat = 0

        # 指令订阅
        self._command_pubsub = None

        self.log = logging.getLogger(f"boat-{addr[0]}")

    def run(self):
        self.running = True
        self.log.info(f"船端连接: {self.addr}")

        try:
            # 设置socket超时, 便于循环检查running
            self.conn.settimeout(1.0)

            # 用SocketMavlink包装已有socket (pymavlink 2.4.49)
            self.mav = SocketMavlink(
                self.conn,
                f"{self.addr[0]}:{self.addr[1]}",
                source_system=255,  # 地面站/云平台ID
                source_component=0,
            )

            # 启动指令转发线程
            cmd_thread = threading.Thread(target=self._command_loop, daemon=True)
            cmd_thread.start()

            # 主循环: 接收MAVLink消息
            while self.running:
                try:
                    msg = self.mav.recv_msg()
                except socket.timeout:
                    # 检查心跳超时
                    self._check_heartbeat_timeout()
                    continue
                except Exception as e:
                    self.log.warning(f"接收消息异常: {e}")
                    break

                if msg is None:
                    continue

                self._handle_message(msg)

        except Exception as e:
            self.log.error(f"连接异常: {e}")
        finally:
            self._cleanup()

    def _handle_message(self, msg):
        """处理单条MAVLink消息"""
        msg_type = msg.get_type()

        # 第一条HEARTBEAT: 建立临时标识 (基于sys_id), 等待ICCID上报后替换为正式boat_key
        if msg_type == "HEARTBEAT" and self.boat_id is None:
            temp_id = f"boat_{msg.get_srcSystem()}"
            self.boat_id = temp_id
            self.log = logging.getLogger(f"boat-{self.boat_id}")
            self.log.info(f"船端连接建立(临时标识): {self.boat_id}, 来自 {self.addr}, 等待ICCID上报...")
            self.redis.register_boat(self.boat_id, f"{self.addr[0]}:{self.addr[1]}")
            self.redis.set_online(self.boat_id, True)
            # 订阅该船的指令通道 (临时)
            self._command_pubsub = self.redis.subscribe_commands(self.boat_id)

        # 解析STATUSTEXT中的船身份上报 (ICCID)
        if msg_type == "STATUSTEXT":
            try:
                text = msg.text.decode() if isinstance(msg.text, bytes) else str(msg.text)
                if text.startswith("BOAT_ID:"):
                    iccid = text.split("BOAT_ID:", 1)[1].strip()
                    self._identify_boat_by_iccid(iccid)
            except Exception as e:
                self.log.debug(f"解析STATUSTEXT失败: {e}")

        # 解析消息
        parsed = MavlinkParser.parse(msg)
        if parsed:
            self.status.update(parsed)

        # 心跳更新
        if msg_type == "HEARTBEAT":
            self._last_heartbeat = time.time()

        # 定时写入Redis实时状态 (限频)
        now = time.time()
        if now - self._last_status_write >= config.STATUS_WRITE_INTERVAL:
            if self.boat_id:
                self.redis.update_status(self.boat_id, self.status)
                # 写入历史数据
                self.db.add_record(self.boat_id, self.status)
            self._last_status_write = now

    def _identify_boat_by_iccid(self, iccid: str):
        """通过ICCID查询数据库, 将临时boat_id替换为正式boat_key"""
        if not iccid:
            return

        # 查询数据库得到正式boat_key
        official_boat_key = self.db.lookup_boat_by_iccid(iccid)
        if not official_boat_key:
            self.log.warning(f"ICCID {iccid} 未在数据库注册, 保持临时标识")
            return

        # 如果boat_key变化, 重新注册
        if official_boat_key != self.boat_id:
            old_id = self.boat_id
            # 注销旧的临时标识
            try:
                self.redis.unregister_boat(old_id)
            except Exception:
                pass

            # 切换到正式标识
            self.boat_id = official_boat_key
            self.log = logging.getLogger(f"boat-{self.boat_id}")
            self.log.info(f"船身份确认: ICCID={iccid} -> boat_key={official_boat_key} (原临时标识: {old_id})")
            self.redis.register_boat(self.boat_id, f"{self.addr[0]}:{self.addr[1]}")
            self.redis.set_online(self.boat_id, True)

            # 重新订阅正式标识的指令通道
            try:
                if self._command_pubsub:
                    self._command_pubsub.unsubscribe()
                    self._command_pubsub.close()
            except Exception:
                pass
            self._command_pubsub = self.redis.subscribe_commands(self.boat_id)

    def _command_loop(self):
        """指令转发线程: 从Redis Pub/Sub接收API下发的指令, 转发给船"""
        while self.running:
            if not self._command_pubsub:
                time.sleep(0.5)
                continue
            try:
                message = self._command_pubsub.get_message(timeout=1.0)
                if message and message["type"] == "message":
                    cmd = json.loads(message["data"])
                    self._send_command(cmd)
            except Exception as e:
                self.log.debug(f"指令订阅异常: {e}")
                time.sleep(0.5)

    def _send_command(self, cmd: dict):
        """发送MAVLink指令给船"""
        if not self.mav or not self.boat_id:
            self.log.warning("MAVLink未就绪, 忽略指令")
            return

        cmd_type = cmd.get("type")
        self.log.info(f"收到指令: {cmd_type}")

        try:
            if cmd_type == "set_mode":
                # 切换飞行模式
                custom_mode = cmd.get("custom_mode", 0)  # 10=AUTO, 11=RTL, 0=MANUAL
                self.mav.mav.set_mode_send(
                    self.mav.target_system,
                    mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                    custom_mode,
                )
                self.log.info(f"切换模式: custom_mode={custom_mode}")

            elif cmd_type == "arm_disarm":
                # 解锁/上锁
                arm = cmd.get("arm", True)
                self.mav.mav.command_long_send(
                    self.mav.target_system,
                    self.mav.target_component,
                    mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                    0,
                    1 if arm else 0,  # param1: 1=arm, 0=disarm
                    0, 0, 0, 0, 0, 0,
                )

            elif cmd_type == "mission_upload":
                # 上传航点任务
                waypoints = cmd.get("waypoints", [])
                self._upload_mission(waypoints)

            elif cmd_type == "mission_start":
                # 开始执行任务 (从第0个航点)
                self.mav.mav.mission_set_current_send(
                    self.mav.target_system,
                    self.mav.target_component,
                    0,
                )
                # 切换到AUTO模式
                self.mav.mav.set_mode_send(
                    self.mav.target_system,
                    mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                    10,  # AUTO
                )

            elif cmd_type == "rtl":
                # 返航
                self.mav.mav.set_mode_send(
                    self.mav.target_system,
                    mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                    11,  # RTL
                )

            elif cmd_type == "do_set_servo":
                # 设置舵机/PWM输出 (投料开关等)
                channel = cmd.get("channel", 8)
                pwm = cmd.get("pwm", 1500)
                self.mav.mav.command_long_send(
                    self.mav.target_system,
                    self.mav.target_component,
                    mavutil.mavlink.MAV_CMD_DO_SET_SERVO,
                    0,
                    channel,
                    pwm,
                    0, 0, 0, 0, 0,
                )

            elif cmd_type == "manual_control":
                # 手动控制 (油门/方向)
                x = cmd.get("x", 0)  # 方向 (-1000 to 1000)
                y = cmd.get("y", 0)  # 油门 (-1000 to 1000)
                self.mav.mav.manual_control_send(
                    self.mav.target_system,
                    x, y, 0, 0, 0,
                )

            else:
                self.log.warning(f"未知指令类型: {cmd_type}")

        except Exception as e:
            self.log.error(f"发送指令失败: {e}")

    def _upload_mission(self, waypoints: list):
        """
        上传航点任务到飞控
        waypoints: [{lat, lon, alt, speed}, ...]
        """
        if not waypoints:
            self.log.warning("航点列表为空")
            return

        target_sys = self.mav.target_system
        target_comp = self.mav.target_component
        count = len(waypoints)

        self.log.info(f"上传航点任务: {count}个航点")

        # 1. 发送任务数量
        self.mav.mav.mission_count_send(target_sys, target_comp, count)

        # 2. 等待飞控请求每个航点, 逐个发送
        #    (简化处理: 直接发送, 不严格等待REQUEST)
        for i, wp in enumerate(waypoints):
            lat = int(wp["lat"] * 1e7)
            lon = int(wp["lon"] * 1e7)
            alt = float(wp.get("alt", 0.0))
            speed = float(wp.get("speed", 1.5))

            # MAV_CMD_NAV_WAYPOINT = 16
            self.mav.mav.mission_item_send(
                target_sys, target_comp,
                i,                    # seq
                mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                0, 0,                 # current, autocontinue
                0,                    # param1: hold time
                speed,                # param2: accept radius (m) - 借用传速度
                0,                    # param3: pass radius
                0,                    # param4: yaw
                lat, lon, alt,
            )
            time.sleep(0.05)  # 避免发送过快

        self.log.info("航点上传完成")

    def _check_heartbeat_timeout(self):
        """检查心跳超时"""
        if self.boat_id and self._last_heartbeat > 0:
            if time.time() - self._last_heartbeat > config.BOAT_HEARTBEAT_TIMEOUT:
                self.log.warning("心跳超时, 标记离线")
                self.redis.set_online(self.boat_id, False)
                self._last_heartbeat = 0  # 避免重复标记

    def _cleanup(self):
        """清理资源"""
        self.running = False
        if self.boat_id:
            self.log.info(f"船端断开: {self.boat_id}")
            self.redis.unregister_boat(self.boat_id)
        if self._command_pubsub:
            try:
                self._command_pubsub.close()
            except Exception:
                pass
        try:
            self.conn.close()
        except Exception:
            pass
