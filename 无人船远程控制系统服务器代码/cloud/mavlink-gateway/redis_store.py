"""
Redis状态存储
- 每艘船的实时状态存在 Redis Hash: boat:{boat_id}:status
- 船端连接管理: boat:{boat_id}:connection (在线状态)
- 指令通道: Pub/Sub channel "command:{boat_id}"
"""
import json
import time
import redis
from config import config


class RedisStore:
    def __init__(self):
        self.client = redis.from_url(config.REDIS_URL, decode_responses=True)
        self.client.ping()

    # ============================================================
    # 船实时状态
    # ============================================================
    def update_status(self, boat_id: str, status: dict):
        """更新船的实时状态 (写入Redis Hash)"""
        key = f"boat:{boat_id}:status"
        # 增加更新时间戳
        status["_updated_at"] = time.time()
        # 只更新非None字段
        pipe = self.client.pipeline()
        for k, v in status.items():
            if v is not None:
                if isinstance(v, (dict, list)):
                    v = json.dumps(v)
                elif isinstance(v, bool):
                    v = 1 if v else 0
                pipe.hset(key, k, v)
        pipe.execute()

    def get_status(self, boat_id: str) -> dict:
        """获取船的实时状态"""
        key = f"boat:{boat_id}:status"
        data = self.client.hgetall(key)
        result = {}
        for k, v in data.items():
            try:
                result[k] = json.loads(v)
            except (json.JSONDecodeError, TypeError):
                result[k] = v
        return result

    def is_online(self, boat_id: str) -> bool:
        """检查船是否在线"""
        key = f"boat:{boat_id}:status"
        updated = self.client.hget(key, "_updated_at")
        if not updated:
            return False
        return (time.time() - float(updated)) < config.BOAT_HEARTBEAT_TIMEOUT

    def set_online(self, boat_id: str, online: bool):
        """设置船在线状态"""
        key = f"boat:{boat_id}:status"
        self.client.hset(key, "online", "true" if online else "false")
        if online:
            self.client.hset(key, "_connected_at", time.time())

    # ============================================================
    # 指令转发 (Pub/Sub)
    # ============================================================
    def publish_command(self, boat_id: str, command: dict):
        """API下发指令到指定船 (通过Pub/Sub)"""
        channel = f"command:{boat_id}"
        self.client.publish(channel, json.dumps(command))

    def subscribe_commands(self, boat_id: str):
        """订阅指定船的指令 (返回pubsub对象)"""
        pubsub = self.client.pubsub()
        pubsub.subscribe(f"command:{boat_id}")
        return pubsub

    # ============================================================
    # 船列表 (用于网关内部管理连接)
    # ============================================================
    def register_boat(self, boat_id: str, remote_addr: str):
        """注册船端连接"""
        self.client.sadd("boats:connected", boat_id)
        self.client.hset(f"boat:{boat_id}:connection", "remote_addr", remote_addr)
        self.client.hset(f"boat:{boat_id}:connection", "connected_at", time.time())

    def unregister_boat(self, boat_id: str):
        """注销船端连接"""
        self.client.srem("boats:connected", boat_id)
        self.set_online(boat_id, False)

    def get_connected_boats(self) -> set:
        """获取当前在线的船ID集合"""
        return self.client.smembers("boats:connected")
