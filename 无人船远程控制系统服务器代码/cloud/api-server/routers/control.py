"""
控制指令路由 - 遥控船 (模式切换、返航、手动控制、投料开关)
权限:
  - owner(管理员): 可直接控制
  - viewer(共享者): 需有有效控制授权才能控制
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import redis
import json
import time

from database import get_db
from models import User, Boat
from schemas import ControlCommand, CommandResponse
from auth import get_current_user
from config import settings
from routers.control_grants import require_control_permission

router = APIRouter(prefix="/api/boats/{boat_id}/control", tags=["控制指令"])

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)


def _get_boat(db: Session, boat_id: int) -> Boat:
    boat = db.query(Boat).filter(Boat.id == boat_id).first()
    if not boat:
        raise HTTPException(status_code=404, detail="船不存在")
    return boat


def _check_online(boat_key: str) -> bool:
    """检查船是否在线"""
    updated = redis_client.hget(f"boat:{boat_key}:status", "_updated_at")
    if not updated:
        return False
    return (time.time() - float(updated)) < 10


def _send_command(boat_key: str, command: dict):
    """发送指令到MAVLink网关 (通过Redis Pub/Sub)"""
    redis_client.publish(f"command:{boat_key}", json.dumps(command))


@router.post("", response_model=CommandResponse)
def send_command(
    boat_id: int,
    command: ControlCommand,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    permission: dict = Depends(require_control_permission),
):
    """
    发送通用控制指令
    type:
      - set_mode: 切换模式 (custom_mode: 0=MANUAL,10=AUTO,11=RTL,15=GUIDED)
      - arm_disarm: 解锁/上锁 (arm: true/false)
      - rtl: 返航
      - mission_start: 开始执行当前任务
      - do_set_servo: 设置舵机/PWM (channel, pwm)
      - manual_control: 手动控制 (x方向, y油门)
    """
    boat = _get_boat(db, boat_id)

    if not _check_online(boat.boat_key):
        raise HTTPException(status_code=400, detail="船不在线, 无法发送指令")

    cmd_dict = command.model_dump(exclude_none=True)
    _send_command(boat.boat_key, cmd_dict)

    type_desc = {
        "set_mode": f"切换模式到 {command.custom_mode}",
        "arm_disarm": "解锁" if command.arm else "上锁",
        "rtl": "返航",
        "mission_start": "开始执行任务",
        "do_set_servo": f"设置通道{command.channel} PWM={command.pwm}",
        "manual_control": f"手动控制 x={command.x} y={command.y}",
    }.get(command.type, command.type)

    return CommandResponse(success=True, message=f"指令已发送: {type_desc}")


@router.post("/rtl", response_model=CommandResponse)
def return_to_launch(
    boat_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    permission: dict = Depends(require_control_permission),
):
    """一键返航"""
    boat = _get_boat(db, boat_id)
    if not _check_online(boat.boat_key):
        raise HTTPException(status_code=400, detail="船不在线")
    _send_command(boat.boat_key, {"type": "rtl"})
    return CommandResponse(success=True, message="返航指令已发送")


@router.post("/start_auto", response_model=CommandResponse)
def start_auto_mode(
    boat_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    permission: dict = Depends(require_control_permission),
):
    """切换到AUTO模式 (开始自动航行)"""
    boat = _get_boat(db, boat_id)
    if not _check_online(boat.boat_key):
        raise HTTPException(status_code=400, detail="船不在线")
    _send_command(boat.boat_key, {"type": "set_mode", "custom_mode": 10})
    return CommandResponse(success=True, message="已切换到AUTO模式")


@router.post("/stop", response_model=CommandResponse)
def emergency_stop(
    boat_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    permission: dict = Depends(require_control_permission),
):
    """紧急停车 (切换到HOLD模式)"""
    boat = _get_boat(db, boat_id)
    if not _check_online(boat.boat_key):
        raise HTTPException(status_code=400, detail="船不在线")
    _send_command(boat.boat_key, {"type": "set_mode", "custom_mode": 4})  # HOLD
    return CommandResponse(success=True, message="紧急停车指令已发送 (HOLD模式)")


@router.post("/feed/on", response_model=CommandResponse)
def feed_on(
    boat_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    permission: dict = Depends(require_control_permission),
):
    """手动开启投料 (通过舵机通道)"""
    boat = _get_boat(db, boat_id)
    if not _check_online(boat.boat_key):
        raise HTTPException(status_code=400, detail="船不在线")
    # 注意: 如果投料由香橙派独立控制, 这个命令可能无效
    # 这里假设投料电机接在飞控的通道8上
    _send_command(boat.boat_key, {"type": "do_set_servo", "channel": 8, "pwm": 2000})
    return CommandResponse(success=True, message="投料已开启")


@router.post("/feed/off", response_model=CommandResponse)
def feed_off(
    boat_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    permission: dict = Depends(require_control_permission),
):
    """手动关闭投料"""
    boat = _get_boat(db, boat_id)
    if not _check_online(boat.boat_key):
        raise HTTPException(status_code=400, detail="船不在线")
    _send_command(boat.boat_key, {"type": "do_set_servo", "channel": 8, "pwm": 1000})
    return CommandResponse(success=True, message="投料已关闭")
