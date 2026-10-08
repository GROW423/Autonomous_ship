"""
遥测历史数据路由 - 轨迹回放、历史状态查询
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional
from datetime import datetime, timedelta

from database import get_db
from models import User, Boat, TelemetryHistory
from schemas import TelemetryRecord
from auth import get_current_user

router = APIRouter(prefix="/api/boats/{boat_id}/telemetry", tags=["遥测历史"])


def _get_user_boat(db: Session, boat_id: int, user: User) -> Boat:
    boat = db.query(Boat).filter(Boat.id == boat_id, Boat.user_id == user.id).first()
    if not boat:
        raise HTTPException(status_code=404, detail="船不存在或无权限")
    return boat


@router.get("/history", response_model=List[TelemetryRecord])
def get_telemetry_history(
    boat_id: int,
    start: Optional[datetime] = Query(None, description="开始时间 (ISO格式)"),
    end: Optional[datetime] = Query(None, description="结束时间 (ISO格式)"),
    limit: int = Query(1000, ge=1, le=10000, description="最大返回条数"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取遥测历史数据 (用于轨迹回放)
    默认返回最近24小时数据
    """
    boat = _get_user_boat(db, boat_id, current_user)

    if end is None:
        end = datetime.utcnow()
    if start is None:
        start = end - timedelta(hours=24)

    records = (
        db.query(TelemetryHistory)
        .filter(
            and_(
                TelemetryHistory.boat_id == boat.boat_key,
                TelemetryHistory.timestamp >= start,
                TelemetryHistory.timestamp <= end,
            )
        )
        .order_by(TelemetryHistory.timestamp.asc())
        .limit(limit)
        .all()
    )
    return records


@router.get("/latest", response_model=Optional[TelemetryRecord])
def get_latest_telemetry(
    boat_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取最近一条遥测记录"""
    boat = _get_user_boat(db, boat_id, current_user)
    record = (
        db.query(TelemetryHistory)
        .filter(TelemetryHistory.boat_id == boat.boat_key)
        .order_by(TelemetryHistory.timestamp.desc())
        .first()
    )
    return record


@router.get("/summary")
def get_telemetry_summary(
    boat_id: int,
    hours: int = Query(24, ge=1, le=720, description="统计最近N小时"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取遥测数据统计摘要 (航行时长、里程、平均速度等)"""
    boat = _get_user_boat(db, boat_id, current_user)
    end = datetime.utcnow()
    start = end - timedelta(hours=hours)

    records = (
        db.query(TelemetryHistory)
        .filter(
            and_(
                TelemetryHistory.boat_id == boat.boat_key,
                TelemetryHistory.timestamp >= start,
                TelemetryHistory.timestamp <= end,
                TelemetryHistory.groundspeed > 0.1,  # 只统计移动中的点
            )
        )
        .order_by(TelemetryHistory.timestamp.asc())
        .all()
    )

    if not records:
        return {
            "period_hours": hours,
            "records": 0,
            "total_distance_km": 0,
            "avg_speed": 0,
            "max_speed": 0,
            "active_minutes": 0,
        }

    # 计算里程 (简化: 相邻点距离累加)
    from math import radians, sin, cos, sqrt, atan2
    total_dist = 0.0
    speeds = [r.groundspeed for r in records if r.groundspeed]
    prev = None
    for r in records:
        if prev and r.lat and r.lon and prev.lat and prev.lon:
            # Haversine公式
            R = 6371000  # 地球半径米
            lat1, lon1 = radians(prev.lat), radians(prev.lon)
            lat2, lon2 = radians(r.lat), radians(r.lon)
            dlat, dlon = lat2 - lat1, lon2 - lon1
            a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
            total_dist += R * 2 * atan2(sqrt(a), sqrt(1-a))
        prev = r

    # 活跃时间 (记录数 * 平均间隔, 简化估算)
    if len(records) > 1:
        duration = (records[-1].timestamp - records[0].timestamp).total_seconds()
        active_minutes = duration / 60
    else:
        active_minutes = 0

    return {
        "period_hours": hours,
        "records": len(records),
        "total_distance_km": round(total_dist / 1000, 2),
        "avg_speed": round(sum(speeds) / len(speeds), 2) if speeds else 0,
        "max_speed": round(max(speeds), 2) if speeds else 0,
        "active_minutes": round(active_minutes, 1),
    }
