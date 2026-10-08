"""
WebSocket实时推送 - 船状态1Hz推送给前端
"""
import json
import time
import asyncio
from typing import Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from database import SessionLocal
from models import User, Boat
from config import settings
import redis

router = APIRouter()
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)


class ConnectionManager:
    """管理所有WebSocket连接"""
    def __init__(self):
        # user_id -> set of WebSocket connections
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            if user_id not in self.active_connections:
                self.active_connections[user_id] = set()
            self.active_connections[user_id].add(websocket)

    async def disconnect(self, user_id: int, websocket: WebSocket):
        async with self._lock:
            if user_id in self.active_connections:
                self.active_connections[user_id].discard(websocket)
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]

    async def send_to_user(self, user_id: int, message: dict):
        if user_id not in self.active_connections:
            return
        dead_connections = []
        for ws in self.active_connections[user_id]:
            try:
                await ws.send_json(message)
            except Exception:
                dead_connections.append(ws)
        for ws in dead_connections:
            await self.disconnect(user_id, ws)

    def get_user_boats(self, user_id: int) -> list:
        """从数据库获取用户的所有船key"""
        db = SessionLocal()
        try:
            boats = db.query(Boat.boat_key).filter(Boat.user_id == user_id).all()
            return [b[0] for b in boats]
        finally:
            db.close()


manager = ConnectionManager()


def _read_boat_status(boat_key: str) -> dict:
    """从Redis读取船状态"""
    data = redis_client.hgetall(f"boat:{boat_key}:status")
    result = {"boat_id": boat_key}
    for k, v in data.items():
        if k.startswith("_"):
            result[k] = v
            continue
        try:
            result[k] = json.loads(v)
        except (json.JSONDecodeError, TypeError):
            try:
                result[k] = float(v) if "." in v else int(v)
            except (ValueError, TypeError):
                result[k] = v
    # 在线判断
    updated = result.get("_updated_at")
    result["online"] = bool(updated and (time.time() - float(updated)) < 10)
    return result


async def broadcast_loop():
    """后台循环: 每秒推送所有用户的船状态"""
    while True:
        try:
            user_ids = list(manager.active_connections.keys())
            for user_id in user_ids:
                boat_keys = manager.get_user_boats(user_id)
                statuses = []
                for bk in boat_keys:
                    statuses.append(_read_boat_status(bk))
                if statuses:
                    await manager.send_to_user(user_id, {
                        "type": "boat_statuses",
                        "data": statuses,
                        "timestamp": time.time(),
                    })
        except Exception as e:
            print(f"[WebSocket] 广播异常: {e}", flush=True)
        await asyncio.sleep(1.0)  # 1Hz


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    """
    WebSocket连接
    前端: new WebSocket("ws://host/ws?token=JWT_TOKEN")
    """
    # 验证token
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = int(payload.get("sub"))
    except (JWTError, ValueError, TypeError):
        await websocket.close(code=4401, reason="认证失败")
        return

    # 验证用户存在
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            await websocket.close(code=4401, reason="用户不存在或已禁用")
            return
    finally:
        db.close()

    await manager.connect(user_id, websocket)
    print(f"[WebSocket] 用户{user_id}已连接", flush=True)

    try:
        # 发送初始状态
        boat_keys = manager.get_user_boats(user_id)
        statuses = [_read_boat_status(bk) for bk in boat_keys]
        await websocket.send_json({
            "type": "boat_statuses",
            "data": statuses,
            "timestamp": time.time(),
        })

        # 保持连接, 接收前端消息
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                # 前端可以发送ping, 服务端回pong
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong", "timestamp": time.time()})
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(user_id, websocket)
        print(f"[WebSocket] 用户{user_id}已断开", flush=True)
