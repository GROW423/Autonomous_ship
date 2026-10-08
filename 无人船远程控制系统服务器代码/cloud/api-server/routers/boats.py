"""
无人船管理路由 - CRUD + 实时状态 + 搜索 + 区域筛选 + 三级权限 + 多用户绑定
权限:
  - admin(总管理员): 看/操作所有船
  - regional_admin(地方管理员): 看/操作自己负责区域的船
  - user(普通用户): 看/操作自己绑定的船 (owner或viewer)
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
import redis
import json
import secrets
import string

from database import get_db
from models import User, Boat, Region, BoatBinding
from schemas import BoatCreate, BoatUpdate, BoatResponse, BoatStatus, BoatResponseWithRole
from auth import get_current_user
from config import settings
from routers.bindings import get_user_binding, generate_bind_code

router = APIRouter(prefix="/api/boats", tags=["无人船"])

# Redis客户端 (读取实时状态)
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)


def _get_visible_boats_query(db: Session, user: User):
    """根据用户角色返回可见船的查询对象 (三级权限 + 绑定关系)"""
    query = db.query(Boat).filter(Boat.is_active == True)

    if user.role == "admin" or user.is_admin:
        # 总管理员: 所有船
        return query
    elif user.role == "regional_admin" and user.region_id:
        # 地方管理员: 自己负责区域的船
        return query.filter(Boat.region_id == user.region_id)
    else:
        # 普通用户: 自己绑定的船 (通过boat_bindings表关联)
        bound_boat_ids = db.query(BoatBinding.boat_id).filter(
            BoatBinding.user_id == user.id
        ).subquery()
        return query.filter(Boat.id.in_(bound_boat_ids))


def _get_user_boat(db: Session, boat_id: int, user: User) -> Boat:
    """获取用户有权限的船 (三级权限校验)"""
    query = _get_visible_boats_query(db, user)
    boat = query.filter(Boat.id == boat_id).first()
    if not boat:
        raise HTTPException(status_code=404, detail="船不存在或无权限")
    return boat


def _enrich_boat_with_region(boat: Boat, db: Session) -> dict:
    """给船对象附加region_name"""
    result = {c.name: getattr(boat, c.name) for c in boat.__table__.columns}
    if boat.region_id:
        region = db.query(Region).filter(Region.id == boat.region_id).first()
        result["region_name"] = region.name if region else None
    else:
        result["region_name"] = None
    return result


def _read_boat_status(boat_key: str) -> dict:
    """从Redis读取船的实时状态"""
    data = redis_client.hgetall(f"boat:{boat_key}:status")
    result = {}
    for k, v in data.items():
        try:
            result[k] = json.loads(v)
        except (json.JSONDecodeError, TypeError):
            try:
                result[k] = float(v) if "." in v else int(v)
            except (ValueError, TypeError):
                result[k] = v
    return result


@router.get("", response_model=List[BoatResponse])
def list_boats(
    search: Optional[str] = Query(None, description="按船名或ICCID模糊搜索"),
    region_id: Optional[int] = Query(None, description="按区域ID筛选"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户有权限的船列表 (支持模糊搜索+区域筛选)"""
    query = _get_visible_boats_query(db, current_user)

    # 区域筛选
    if region_id:
        query = query.filter(Boat.region_id == region_id)

    # 模糊搜索 (船名或ICCID, 不区分大小写)
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Boat.name.ilike(search_pattern),
                Boat.iccid.ilike(search_pattern),
            )
        )

    boats = query.order_by(Boat.created_at.desc()).all()

    # 附加region_name
    result = []
    for boat in boats:
        result.append(_enrich_boat_with_region(boat, db))
    return result


@router.post("", response_model=BoatResponse, status_code=201)
def create_boat(
    boat_data: BoatCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """添加一艘新船"""
    # 检查ICCID是否已被使用 (ICCID是全球唯一标识)
    if boat_data.iccid:
        existing = db.query(Boat).filter(Boat.iccid == boat_data.iccid).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"ICCID {boat_data.iccid} 已被使用")

    # 区域权限校验: 普通用户只能把船加到自己名下, 地方管理员只能加到自己区域
    region_id = boat_data.region_id
    if current_user.role == "regional_admin" and current_user.region_id:
        # 地方管理员: 船的区域必须是自己负责的区域
        region_id = current_user.region_id
    elif current_user.role not in ("admin",) and not current_user.is_admin:
        # 普通用户: 不能指定区域(船归属自己, 区域可选)
        pass

    boat = Boat(
        owner_id=current_user.id,
        user_id=current_user.id,  # 兼容旧字段
        name=boat_data.name,
        mavlink_sys_id=boat_data.mavlink_sys_id,
        boat_key="",  # 占位, commit后基于id生成
        iccid=boat_data.iccid,
        bind_code=generate_bind_code(),
        bind_enabled=True,
        region_id=region_id,
        description=boat_data.description,
        home_lat=boat_data.home_lat,
        home_lon=boat_data.home_lon,
    )
    db.add(boat)
    db.commit()
    db.refresh(boat)

    # 基于数据库主键生成全局唯一boat_key
    boat.boat_key = f"boat_{boat.id}"
    db.commit()
    db.refresh(boat)

    # 创建owner绑定关系
    owner_binding = BoatBinding(
        user_id=current_user.id,
        boat_id=boat.id,
        role="owner",
    )
    db.add(owner_binding)
    db.commit()

    return _enrich_boat_with_region(boat, db)


@router.get("/{boat_id}", response_model=BoatResponse)
def get_boat(
    boat_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取船的基本信息"""
    boat = _get_user_boat(db, boat_id, current_user)
    return _enrich_boat_with_region(boat, db)


@router.put("/{boat_id}", response_model=BoatResponse)
def update_boat(
    boat_id: int,
    boat_data: BoatUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新船信息"""
    boat = _get_user_boat(db, boat_id, current_user)

    # 地方管理员不能把船移出自己区域
    update_data = boat_data.model_dump(exclude_unset=True)
    if current_user.role == "regional_admin" and current_user.region_id:
        if "region_id" in update_data and update_data["region_id"] != current_user.region_id:
            raise HTTPException(status_code=403, detail="地方管理员只能管理自己区域的船")

    for field, value in update_data.items():
        setattr(boat, field, value)
    db.commit()
    db.refresh(boat)
    return _enrich_boat_with_region(boat, db)


@router.delete("/{boat_id}", status_code=204)
def delete_boat(
    boat_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除船 (软删除)"""
    boat = _get_user_boat(db, boat_id, current_user)
    boat.is_active = False
    db.commit()


@router.get("/{boat_id}/status", response_model=BoatStatus)
def get_boat_status(
    boat_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取船的实时状态 (从Redis)"""
    boat = _get_user_boat(db, boat_id, current_user)
    status_data = _read_boat_status(boat.boat_key)

    # 判断在线状态
    updated_at = status_data.get("_updated_at")
    online = False
    if updated_at:
        import time
        online = (time.time() - float(updated_at)) < 10  # 10秒内有更新算在线

    return BoatStatus(
        boat_id=boat.boat_key,
        online=online,
        lat=status_data.get("lat"),
        lon=status_data.get("lon"),
        heading=status_data.get("heading"),
        groundspeed=status_data.get("groundspeed"),
        battery_voltage=status_data.get("battery_voltage"),
        battery_current=status_data.get("battery_current"),
        battery_remaining=status_data.get("battery_remaining"),
        flight_mode=status_data.get("flight_mode"),
        armed=status_data.get("armed"),
        current_waypoint=status_data.get("current_waypoint"),
        feed_level=status_data.get("feed_level"),
        cellular_csq=status_data.get("cellular_csq"),
        box_temperature=status_data.get("box_temperature"),
        gps_fix_type=status_data.get("gps_fix_type"),
        gps_satellites_visible=status_data.get("gps_satellites_visible"),
        last_status_text=status_data.get("last_status_text"),
        updated_at=updated_at,
    )
