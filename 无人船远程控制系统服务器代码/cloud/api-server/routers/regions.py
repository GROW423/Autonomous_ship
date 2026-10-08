"""
区域管理路由 - CRUD
总管理员可管理所有区域, 地方管理员和普通用户只读
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from models import User, Region
from schemas import RegionCreate, RegionUpdate, RegionResponse
from auth import get_current_user

router = APIRouter(prefix="/api/regions", tags=["区域管理"])


def _check_admin(user: User):
    """检查是否为总管理员"""
    if user.role != "admin" and not user.is_admin:
        raise HTTPException(status_code=403, detail="仅总管理员可操作区域")


@router.get("", response_model=List[RegionResponse])
def list_regions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取所有区域列表 (所有登录用户可读)"""
    regions = db.query(Region).filter(Region.is_active == True).order_by(Region.name).all()
    return regions


@router.post("", response_model=RegionResponse, status_code=201)
def create_region(
    region_data: RegionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建新区域 (仅总管理员)"""
    _check_admin(current_user)

    existing = db.query(Region).filter(Region.name == region_data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"区域「{region_data.name}」已存在")

    region = Region(
        name=region_data.name,
        description=region_data.description,
    )
    db.add(region)
    db.commit()
    db.refresh(region)
    return region


@router.put("/{region_id}", response_model=RegionResponse)
def update_region(
    region_id: int,
    region_data: RegionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新区域 (仅总管理员)"""
    _check_admin(current_user)

    region = db.query(Region).filter(Region.id == region_id).first()
    if not region:
        raise HTTPException(status_code=404, detail="区域不存在")

    for field, value in region_data.model_dump(exclude_unset=True).items():
        setattr(region, field, value)
    db.commit()
    db.refresh(region)
    return region


@router.delete("/{region_id}", status_code=204)
def delete_region(
    region_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除区域 (仅总管理员, 软删除)"""
    _check_admin(current_user)

    region = db.query(Region).filter(Region.id == region_id).first()
    if not region:
        raise HTTPException(status_code=404, detail="区域不存在")

    region.is_active = False
    db.commit()
