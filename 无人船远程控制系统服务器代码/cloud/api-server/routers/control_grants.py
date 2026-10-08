"""
控制授权管理 API
- 共享者申请限时控制权限
- 管理员审批控制申请
- 管理员收回控制权
- 查询当前用户控制权限
"""
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from auth import get_current_user
from models import User, Boat, BoatBinding, BoatControlGrant
from schemas import (
    ControlGrantRequest,
    ControlGrantApproveRequest,
    ControlGrantResponse,
    ControlPermissionResponse,
)
from routers.bindings import get_user_binding, require_owner, require_binding

router = APIRouter(prefix="/api", tags=["控制授权"])


def get_active_grant(db: Session, user_id: int, boat_id: int) -> Optional[BoatControlGrant]:
    """获取用户在该船的有效控制授权"""
    now = datetime.utcnow()
    grant = db.query(BoatControlGrant).filter(
        BoatControlGrant.boat_id == boat_id,
        BoatControlGrant.requester_id == user_id,
        BoatControlGrant.status == "approved",
        BoatControlGrant.start_time <= now,
        BoatControlGrant.end_time > now,
    ).order_by(BoatControlGrant.created_at.desc()).first()
    return grant


def check_control_permission(db: Session, user: User, boat_id: int) -> dict:
    """
    检查用户对该船的控制权限
    返回: {has_control, role, is_owner, active_grant, remaining_seconds, can_apply}
    """
    binding = get_user_binding(db, user.id, boat_id)
    if not binding:
        return {
            "has_control": False,
            "role": "none",
            "is_owner": False,
            "active_grant": None,
            "remaining_seconds": None,
            "can_apply": False,
        }

    if binding.role == "owner":
        return {
            "has_control": True,
            "role": "owner",
            "is_owner": True,
            "active_grant": None,
            "remaining_seconds": None,
            "can_apply": False,
        }

    # viewer
    active_grant = get_active_grant(db, user.id, boat_id)
    if active_grant:
        remaining = int((active_grant.end_time - datetime.utcnow()).total_seconds())
        return {
            "has_control": True,
            "role": "viewer",
            "is_owner": False,
            "active_grant": active_grant,
            "remaining_seconds": max(0, remaining),
            "can_apply": False,
        }
    else:
        # 检查是否有pending的申请
        pending = db.query(BoatControlGrant).filter(
            BoatControlGrant.boat_id == boat_id,
            BoatControlGrant.requester_id == user.id,
            BoatControlGrant.status == "pending",
        ).first()
        return {
            "has_control": False,
            "role": "viewer",
            "is_owner": False,
            "active_grant": None,
            "remaining_seconds": None,
            "can_apply": pending is None,
        }


def require_control_permission(
    boat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    控制权限校验依赖 (用于控制指令接口)
    - owner: 直接放行
    - viewer有有效授权: 放行
    - 其他: 抛403
    返回权限信息字典
    """
    result = check_control_permission(db, current_user, boat_id)
    if not result["has_control"]:
        if result["role"] == "none":
            raise HTTPException(status_code=403, detail="您未绑定该船")
        elif result["can_apply"]:
            raise HTTPException(status_code=403, detail="您没有控制权限，请先申请控制权限")
        else:
            raise HTTPException(status_code=403, detail="您的控制申请正在审批中，请等待管理员处理")
    return result


def grant_to_response(db: Session, grant: BoatControlGrant) -> ControlGrantResponse:
    """将授权记录转为响应对象"""
    boat = db.query(Boat).filter(Boat.id == grant.boat_id).first()
    requester = db.query(User).filter(User.id == grant.requester_id).first()
    granter = db.query(User).filter(User.id == grant.granter_id).first() if grant.granter_id else None

    remaining = None
    if grant.status == "approved" and grant.end_time:
        remaining = int((grant.end_time - datetime.utcnow()).total_seconds())
        if remaining < 0:
            remaining = 0
            # 自动标记为过期
            grant.status = "expired"
            db.commit()

    return ControlGrantResponse(
        id=grant.id,
        boat_id=grant.boat_id,
        boat_name=boat.name if boat else "未知船",
        requester_id=grant.requester_id,
        requester_name=requester.username if requester else "未知用户",
        granter_id=grant.granter_id,
        granter_name=granter.username if granter else None,
        status=grant.status,
        reason=grant.reason,
        reject_reason=grant.reject_reason,
        start_time=grant.start_time,
        end_time=grant.end_time,
        duration_minutes=grant.duration_minutes,
        remaining_seconds=remaining,
        created_at=grant.created_at,
        approved_at=grant.approved_at,
        revoked_at=grant.revoked_at,
    )


# ============================================================
# 申请控制权限
# ============================================================
@router.post("/control-grants", response_model=dict)
def request_control(
    request: ControlGrantRequest,
    boat_id: int = Query(..., description="船ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """共享者申请限时控制权限"""
    binding = require_binding(db, current_user, boat_id)
    if binding.role == "owner":
        raise HTTPException(status_code=400, detail="您是管理员，无需申请控制权限")

    # 检查是否已有有效授权
    active = get_active_grant(db, current_user.id, boat_id)
    if active:
        raise HTTPException(status_code=400, detail="您已有有效的控制权限，无需重复申请")

    # 检查是否有pending的申请
    pending = db.query(BoatControlGrant).filter(
        BoatControlGrant.boat_id == boat_id,
        BoatControlGrant.requester_id == current_user.id,
        BoatControlGrant.status == "pending",
    ).first()
    if pending:
        raise HTTPException(status_code=400, detail="您已有待审批的控制申请，请等待管理员处理")

    new_grant = BoatControlGrant(
        boat_id=boat_id,
        requester_id=current_user.id,
        status="pending",
        reason=request.reason,
        duration_minutes=request.duration_minutes,
    )
    db.add(new_grant)
    db.commit()
    db.refresh(new_grant)

    return {
        "status": "pending",
        "message": "控制权限申请已提交，等待管理员审批",
        "grant_id": new_grant.id,
        "duration_minutes": request.duration_minutes,
    }


# ============================================================
# 查询控制授权列表
# ============================================================
@router.get("/control-grants", response_model=List[ControlGrantResponse])
def list_control_grants(
    boat_id: Optional[int] = Query(None, description="按船ID筛选"),
    status_filter: Optional[str] = Query(None, alias="status", description="按状态筛选"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    获取控制授权列表
    - 管理员：可查看自己管理的船的所有授权
    - 普通用户：只能查看自己的授权记录
    """
    query = db.query(BoatControlGrant)

    owner_boats = db.query(BoatBinding).filter(
        BoatBinding.user_id == current_user.id,
        BoatBinding.role == "owner"
    ).all()
    owner_boat_ids = [b.boat_id for b in owner_boats]

    if boat_id:
        if boat_id not in owner_boat_ids:
            query = query.filter(BoatControlGrant.requester_id == current_user.id)
        query = query.filter(BoatControlGrant.boat_id == boat_id)
    else:
        if owner_boat_ids:
            query = query.filter(
                (BoatControlGrant.boat_id.in_(owner_boat_ids)) |
                (BoatControlGrant.requester_id == current_user.id)
            )
        else:
            query = query.filter(BoatControlGrant.requester_id == current_user.id)

    if status_filter:
        query = query.filter(BoatControlGrant.status == status_filter)

    grants = query.order_by(BoatControlGrant.created_at.desc()).limit(100).all()
    return [grant_to_response(db, g) for g in grants]


# ============================================================
# 审批控制申请
# ============================================================
@router.post("/control-grants/{grant_id}/approve", response_model=dict)
def approve_control_grant(
    grant_id: int,
    request: ControlGrantApproveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """管理员同意控制申请"""
    grant = db.query(BoatControlGrant).filter(BoatControlGrant.id == grant_id).first()
    if not grant:
        raise HTTPException(status_code=404, detail="授权申请不存在")
    if grant.status != "pending":
        raise HTTPException(status_code=400, detail=f"该申请状态为{grant.status}，不能审批")

    require_owner(db, current_user, grant.boat_id)

    duration = request.duration_minutes or grant.duration_minutes or 60
    now = datetime.utcnow()
    grant.status = "approved"
    grant.granter_id = current_user.id
    grant.start_time = now
    grant.end_time = now + timedelta(minutes=duration)
    grant.duration_minutes = duration
    grant.approved_at = now
    db.commit()

    requester = db.query(User).filter(User.id == grant.requester_id).first()
    return {
        "status": "approved",
        "message": f"已同意【{requester.username if requester else grant.requester_id}】的控制申请，有效期{duration}分钟",
        "grant_id": grant.id,
        "duration_minutes": duration,
        "end_time": grant.end_time.isoformat(),
    }


@router.post("/control-grants/{grant_id}/reject", response_model=dict)
def reject_control_grant(
    grant_id: int,
    request: ControlGrantApproveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """管理员拒绝控制申请"""
    grant = db.query(BoatControlGrant).filter(BoatControlGrant.id == grant_id).first()
    if not grant:
        raise HTTPException(status_code=404, detail="授权申请不存在")
    if grant.status != "pending":
        raise HTTPException(status_code=400, detail=f"该申请状态为{grant.status}，不能审批")

    require_owner(db, current_user, grant.boat_id)

    grant.status = "rejected"
    grant.reject_reason = request.reject_reason
    grant.granter_id = current_user.id
    grant.approved_at = datetime.utcnow()
    db.commit()

    return {"status": "rejected", "message": "已拒绝该控制申请"}


# ============================================================
# 收回控制权
# ============================================================
@router.post("/control-grants/{grant_id}/revoke", response_model=dict)
def revoke_control_grant(
    grant_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """管理员收回控制权"""
    grant = db.query(BoatControlGrant).filter(BoatControlGrant.id == grant_id).first()
    if not grant:
        raise HTTPException(status_code=404, detail="授权记录不存在")
    if grant.status != "approved":
        raise HTTPException(status_code=400, detail=f"该授权状态为{grant.status}，不能收回")

    require_owner(db, current_user, grant.boat_id)

    grant.status = "revoked"
    grant.revoked_at = datetime.utcnow()
    db.commit()

    requester = db.query(User).filter(User.id == grant.requester_id).first()
    return {
        "status": "revoked",
        "message": f"已收回【{requester.username if requester else grant.requester_id}】的控制权",
    }


# ============================================================
# 查询当前用户控制权限
# ============================================================
@router.get("/boats/{boat_id}/control-permission", response_model=ControlPermissionResponse)
def get_control_permission(
    boat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询当前用户对该船的控制权限"""
    result = check_control_permission(db, current_user, boat_id)

    active_grant_response = None
    if result["active_grant"]:
        active_grant_response = grant_to_response(db, result["active_grant"])

    return ControlPermissionResponse(
        boat_id=boat_id,
        role=result["role"],
        has_control=result["has_control"],
        is_owner=result["is_owner"],
        active_grant=active_grant_response,
        remaining_seconds=result["remaining_seconds"],
        can_apply=result["can_apply"],
    )
