"""
任务管理路由 - 航路点任务CRUD + 上传到船
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import redis
import json
from datetime import datetime

from database import get_db
from models import User, Boat, Mission
from schemas import MissionCreate, MissionUpdate, MissionResponse, Waypoint
from auth import get_current_user
from config import settings

router = APIRouter(prefix="/api/boats/{boat_id}/missions", tags=["任务管理"])

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)


def _get_user_boat(db: Session, boat_id: int, user: User) -> Boat:
    boat = db.query(Boat).filter(Boat.id == boat_id, Boat.user_id == user.id).first()
    if not boat:
        raise HTTPException(status_code=404, detail="船不存在或无权限")
    return boat


@router.get("", response_model=List[MissionResponse])
def list_missions(boat_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """获取船的所有任务"""
    _get_user_boat(db, boat_id, current_user)
    missions = db.query(Mission).filter(Mission.boat_id == boat_id).order_by(Mission.created_at.desc()).all()
    return missions


@router.post("", response_model=MissionResponse, status_code=201)
def create_mission(boat_id: int, mission_data: MissionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """创建新任务"""
    _get_user_boat(db, boat_id, current_user)
    if not mission_data.waypoints:
        raise HTTPException(status_code=400, detail="航点列表不能为空")

    mission = Mission(
        boat_id=boat_id,
        name=mission_data.name,
        description=mission_data.description,
        waypoints=[wp.model_dump() for wp in mission_data.waypoints],
    )
    db.add(mission)
    db.commit()
    db.refresh(mission)
    return mission


@router.get("/{mission_id}", response_model=MissionResponse)
def get_mission(boat_id: int, mission_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """获取任务详情"""
    _get_user_boat(db, boat_id, current_user)
    mission = db.query(Mission).filter(Mission.id == mission_id, Mission.boat_id == boat_id).first()
    if not mission:
        raise HTTPException(status_code=404, detail="任务不存在")
    return mission


@router.put("/{mission_id}", response_model=MissionResponse)
def update_mission(boat_id: int, mission_id: int, mission_data: MissionUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """更新任务"""
    _get_user_boat(db, boat_id, current_user)
    mission = db.query(Mission).filter(Mission.id == mission_id, Mission.boat_id == boat_id).first()
    if not mission:
        raise HTTPException(status_code=404, detail="任务不存在")

    for field, value in mission_data.model_dump(exclude_unset=True).items():
        if field == "waypoints" and value is not None:
            mission.waypoints = [wp.model_dump() if isinstance(wp, Waypoint) else wp for wp in value]
        else:
            setattr(mission, field, value)
    db.commit()
    db.refresh(mission)
    return mission


@router.delete("/{mission_id}", status_code=204)
def delete_mission(boat_id: int, mission_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """删除任务"""
    _get_user_boat(db, boat_id, current_user)
    mission = db.query(Mission).filter(Mission.id == mission_id, Mission.boat_id == boat_id).first()
    if not mission:
        raise HTTPException(status_code=404, detail="任务不存在")
    db.delete(mission)
    db.commit()


@router.post("/{mission_id}/upload", response_model=dict)
def upload_mission_to_boat(boat_id: int, mission_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    将任务上传到船端 (通过Redis Pub/Sub发给MAVLink网关)
    网关收到后通过MAVLink MISSION_ITEM消息写入飞控
    """
    boat = _get_user_boat(db, boat_id, current_user)
    mission = db.query(Mission).filter(Mission.id == mission_id, Mission.boat_id == boat_id).first()
    if not mission:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 检查船是否在线
    status_key = f"boat:{boat.boat_key}:status"
    updated = redis_client.hget(status_key, "_updated_at")
    import time
    if not updated or (time.time() - float(updated)) > 10:
        raise HTTPException(status_code=400, detail="船不在线, 无法上传任务")

    # 发送指令到MAVLink网关
    command = {
        "type": "mission_upload",
        "waypoints": mission.waypoints,
    }
    redis_client.publish(f"command:{boat.boat_key}", json.dumps(command))

    # 更新任务状态
    mission.status = "uploaded"
    db.commit()

    return {"success": True, "message": f"任务已上传到船 {boat.name}", "mission_id": mission.id}


@router.post("/{mission_id}/execute", response_model=dict)
def execute_mission(boat_id: int, mission_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    开始执行任务 (上传+切换AUTO模式)
    """
    boat = _get_user_boat(db, boat_id, current_user)
    mission = db.query(Mission).filter(Mission.id == mission_id, Mission.boat_id == boat_id).first()
    if not mission:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 检查在线
    status_key = f"boat:{boat.boat_key}:status"
    updated = redis_client.hget(status_key, "_updated_at")
    import time
    if not updated or (time.time() - float(updated)) > 10:
        raise HTTPException(status_code=400, detail="船不在线")

    # 先上传航点
    upload_cmd = {"type": "mission_upload", "waypoints": mission.waypoints}
    redis_client.publish(f"command:{boat.boat_key}", json.dumps(upload_cmd))
    time.sleep(1)  # 等待上传完成

    # 开始执行
    start_cmd = {"type": "mission_start"}
    redis_client.publish(f"command:{boat.boat_key}", json.dumps(start_cmd))

    mission.status = "executing"
    mission.executed_at = datetime.utcnow()
    db.commit()

    return {"success": True, "message": f"任务已开始执行: {mission.name}"}
