"""
用户管理路由 - 仅总管理员可访问
功能: 用户列表/创建/编辑/角色分配/区域分配/禁用/重置密码
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional

from database import get_db
from models import User, Region
from schemas import UserCreateAdmin, UserUpdate, UserResponse, PasswordReset
from auth import get_current_user, hash_password

router = APIRouter(prefix="/api/users", tags=["用户管理"])


def _check_admin(user: User):
    """检查是否为总管理员"""
    if user.role != "admin" and not user.is_admin:
        raise HTTPException(status_code=403, detail="仅总管理员可访问用户管理")


def _enrich_user_with_region(user: User, db: Session) -> dict:
    """给用户对象附加region_name"""
    result = {c.name: getattr(user, c.name) for c in user.__table__.columns}
    if user.region_id:
        region = db.query(Region).filter(Region.id == user.region_id).first()
        result["region_name"] = region.name if region else None
    else:
        result["region_name"] = None
    return result


@router.get("", response_model=List[UserResponse])
def list_users(
    search: Optional[str] = Query(None, description="按用户名/姓名/邮箱模糊搜索"),
    role: Optional[str] = Query(None, description="按角色筛选"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取所有用户列表 (仅总管理员)"""
    _check_admin(current_user)

    query = db.query(User)

    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                User.username.ilike(pattern),
                User.full_name.ilike(pattern),
                User.email.ilike(pattern),
            )
        )

    if role:
        query = query.filter(User.role == role)

    users = query.order_by(User.created_at.desc()).all()
    return [_enrich_user_with_region(u, db) for u in users]


@router.post("", response_model=UserResponse, status_code=201)
def create_user(
    user_data: UserCreateAdmin,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建新用户 (仅总管理员)"""
    _check_admin(current_user)

    # 校验角色
    valid_roles = ["admin", "regional_admin", "user"]
    if user_data.role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"无效角色, 可选: {valid_roles}")

    # 地方管理员必须指定区域
    if user_data.role == "regional_admin" and not user_data.region_id:
        raise HTTPException(status_code=400, detail="地方管理员必须指定负责区域")

    # 检查用户名
    existing = db.query(User).filter(User.username == user_data.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")

    if user_data.email:
        existing_email = db.query(User).filter(User.email == user_data.email).first()
        if existing_email:
            raise HTTPException(status_code=400, detail="邮箱已注册")

    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        full_name=user_data.full_name,
        phone=user_data.phone,
        role=user_data.role,
        region_id=user_data.region_id if user_data.role == "regional_admin" else None,
        is_admin=(user_data.role == "admin"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _enrich_user_with_region(user, db)


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取用户详情 (仅总管理员)"""
    _check_admin(current_user)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return _enrich_user_with_region(user, db)


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新用户信息 (仅总管理员)"""
    _check_admin(current_user)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 不能修改自己的角色为非admin (防止把自己降权后锁死)
    if user.id == current_user.id and user_data.role and user_data.role != "admin":
        raise HTTPException(status_code=400, detail="不能修改自己的管理员角色")

    update_data = user_data.model_dump(exclude_unset=True)

    # 如果角色改为regional_admin, 必须有region_id
    if "role" in update_data and update_data["role"] == "regional_admin":
        if not update_data.get("region_id") and not user.region_id:
            raise HTTPException(status_code=400, detail="地方管理员必须指定负责区域")

    # 如果角色不是regional_admin, 清空region_id
    if "role" in update_data and update_data["role"] != "regional_admin":
        update_data["region_id"] = None

    # 同步is_admin字段
    if "role" in update_data:
        update_data["is_admin"] = (update_data["role"] == "admin")

    for field, value in update_data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return _enrich_user_with_region(user, db)


@router.post("/{user_id}/reset-password", status_code=204)
def reset_password(
    user_id: int,
    password_data: PasswordReset,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """重置用户密码 (仅总管理员)"""
    _check_admin(current_user)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.hashed_password = hash_password(password_data.new_password)
    db.commit()


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除用户 (软删除, 仅总管理员)"""
    _check_admin(current_user)

    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除自己")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.is_active = False
    db.commit()
