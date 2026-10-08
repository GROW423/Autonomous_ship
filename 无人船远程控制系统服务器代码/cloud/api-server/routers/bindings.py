"""
船绑定管理 API
- 绑定船（首次自动owner，后续需审批）
- 绑定申请审批
- 成员管理
- 转移管理员
"""
import secrets
import string
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from database import get_db
from auth import get_current_user, verify_password
from models import User, Boat, BoatBinding, BoatBindRequest
from schemas import (
    BoatBindRequest as BoatBindRequestSchema,
    BoatBindingResponse,
    BoatMemberResponse,
    BoatBindRequestResponse,
    BindRequestAction,
    TransferOwnerRequest,
)

router = APIRouter(prefix="/api", tags=["绑定管理"])


def generate_bind_code(length: int = 6) -> str:
    """生成6位绑定码（大写字母+数字）"""
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def get_boat_or_404(db: Session, boat_id: int) -> Boat:
    boat = db.query(Boat).filter(Boat.id == boat_id).first()
    if not boat:
        raise HTTPException(status_code=404, detail="船不存在")
    return boat


def get_user_binding(db: Session, user_id: int, boat_id: int) -> Optional[BoatBinding]:
    """获取用户在该船的绑定关系"""
    return db.query(BoatBinding).filter(
        BoatBinding.user_id == user_id,
        BoatBinding.boat_id == boat_id
    ).first()


def require_owner(db: Session, user: User, boat_id: int) -> BoatBinding:
    """要求用户是该船的管理员，否则抛403"""
    binding = get_user_binding(db, user.id, boat_id)
    if not binding or binding.role != "owner":
        raise HTTPException(status_code=403, detail="您不是该船的管理员，无权操作")
    return binding


def require_binding(db: Session, user: User, boat_id: int) -> BoatBinding:
    """要求用户已绑定该船，否则抛403"""
    binding = get_user_binding(db, user.id, boat_id)
    if not binding:
        raise HTTPException(status_code=403, detail="您未绑定该船")
    return binding


# ============================================================
# 绑定船
# ============================================================
@router.post("/bindings/bind", response_model=dict)
def bind_boat(
    request: BoatBindRequestSchema,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    绑定船
    - 输入ICCID或绑定码
    - 如果船从未被绑定，当前用户自动成为管理员
    - 如果船已有管理员，创建绑定申请，等待管理员审批
    """
    if not request.iccid and not request.bind_code:
        raise HTTPException(status_code=400, detail="请输入ICCID或绑定码")

    # 查找船
    boat = None
    if request.iccid:
        boat = db.query(Boat).filter(Boat.iccid == request.iccid).first()
    if not boat and request.bind_code:
        boat = db.query(Boat).filter(Boat.bind_code == request.bind_code).first()

    if not boat:
        raise HTTPException(status_code=404, detail="未找到该设备，请检查ICCID或绑定码")

    # 检查是否已绑定
    existing = get_user_binding(db, current_user.id, boat.id)
    if existing:
        raise HTTPException(status_code=400, detail="您已绑定该船")

    # 检查船是否允许被绑定
    if not boat.bind_enabled:
        raise HTTPException(status_code=400, detail="该船已关闭绑定功能，请联系管理员")

    # 检查船是否已有管理员
    owner_binding = db.query(BoatBinding).filter(
        BoatBinding.boat_id == boat.id,
        BoatBinding.role == "owner"
    ).first()

    if not owner_binding:
        # 首次绑定，自动成为管理员
        new_binding = BoatBinding(
            user_id=current_user.id,
            boat_id=boat.id,
            role="owner",
        )
        db.add(new_binding)
        boat.owner_id = current_user.id
        # 生成绑定码（如果还没有）
        if not boat.bind_code:
            boat.bind_code = generate_bind_code()
        db.commit()
        db.refresh(new_binding)
        return {
            "status": "bound_as_owner",
            "message": "绑定成功，您是该船的管理员",
            "boat_id": boat.id,
            "boat_name": boat.name,
            "role": "owner",
            "bind_code": boat.bind_code,
        }
    else:
        # 已有管理员，创建绑定申请
        # 检查是否已有pending的申请
        pending_request = db.query(BoatBindRequest).filter(
            BoatBindRequest.boat_id == boat.id,
            BoatBindRequest.requester_id == current_user.id,
            BoatBindRequest.status == "pending"
        ).first()
        if pending_request:
            raise HTTPException(status_code=400, detail="您已有待审批的绑定申请，请等待管理员处理")

        new_request = BoatBindRequest(
            boat_id=boat.id,
            requester_id=current_user.id,
            status="pending",
        )
        db.add(new_request)
        db.commit()
        db.refresh(new_request)
        return {
            "status": "pending_approval",
            "message": "绑定申请已提交，等待管理员审批",
            "request_id": new_request.id,
            "boat_id": boat.id,
            "boat_name": boat.name,
        }


# ============================================================
# 主动解除绑定
# ============================================================
@router.post("/bindings/{binding_id}/unbind")
def unbind_boat(
    binding_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用户主动解除与船的绑定（viewer退出，owner不能直接解绑需先转移）"""
    binding = db.query(BoatBinding).filter(BoatBinding.id == binding_id).first()
    if not binding:
        raise HTTPException(status_code=404, detail="绑定关系不存在")
    if binding.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作他人的绑定关系")
    if binding.role == "owner":
        raise HTTPException(status_code=400, detail="管理员不能直接解绑，请先转移管理员权限")

    boat = get_boat_or_404(db, binding.boat_id)
    db.delete(binding)
    db.commit()
    return {"status": "success", "message": f"已解除与船【{boat.name}】的绑定"}


# ============================================================
# 成员管理
# ============================================================
@router.get("/boats/{boat_id}/members", response_model=List[BoatMemberResponse])
def list_members(
    boat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取船的成员列表（仅管理员可查看）"""
    require_owner(db, current_user, boat_id)
    boat = get_boat_or_404(db, boat_id)

    bindings = db.query(BoatBinding).filter(
        BoatBinding.boat_id == boat_id
    ).order_by(BoatBinding.role.desc(), BoatBinding.created_at.asc()).all()

    result = []
    for b in bindings:
        user = db.query(User).filter(User.id == b.user_id).first()
        result.append(BoatMemberResponse(
            binding_id=b.id,
            user_id=b.user_id,
            username=user.username if user else "未知用户",
            full_name=user.full_name if user else None,
            role=b.role,
            is_owner=(b.role == "owner"),
            created_at=b.created_at,
        ))
    return result


@router.delete("/boats/{boat_id}/members/{user_id}")
def remove_member(
    boat_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """管理员移除某个成员（不能移除自己）"""
    require_owner(db, current_user, boat_id)
    boat = get_boat_or_404(db, boat_id)

    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能移除自己，请先转移管理员权限")

    binding = get_user_binding(db, user_id, boat_id)
    if not binding:
        raise HTTPException(status_code=404, detail="该用户未绑定此船")
    if binding.role == "owner":
        raise HTTPException(status_code=400, detail="不能移除管理员，请先转移管理员权限")

    user = db.query(User).filter(User.id == user_id).first()
    db.delete(binding)
    db.commit()
    return {
        "status": "success",
        "message": f"已移除成员【{user.username if user else user_id}】",
    }


# ============================================================
# 转移管理员
# ============================================================
@router.post("/boats/{boat_id}/transfer-owner")
def transfer_owner(
    boat_id: int,
    request: TransferOwnerRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """转移管理员权限给其他成员（需密码二次确认）"""
    require_owner(db, current_user, boat_id)
    boat = get_boat_or_404(db, boat_id)

    # 验证密码
    if not verify_password(request.password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="密码错误")

    # 新管理员必须是已绑定的viewer
    new_owner_binding = get_user_binding(db, request.new_owner_id, boat_id)
    if not new_owner_binding:
        raise HTTPException(status_code=400, detail="该用户未绑定此船")
    if new_owner_binding.role == "owner":
        raise HTTPException(status_code=400, detail="该用户已经是管理员")

    new_owner = db.query(User).filter(User.id == request.new_owner_id).first()

    # 转移：原owner变viewer，新viewer变owner
    old_owner_binding = get_user_binding(db, current_user.id, boat_id)
    old_owner_binding.role = "viewer"
    new_owner_binding.role = "owner"
    boat.owner_id = request.new_owner_id
    db.commit()

    return {
        "status": "success",
        "message": f"管理员权限已转移给【{new_owner.username if new_owner else request.new_owner_id}】",
        "new_owner_id": request.new_owner_id,
    }


# ============================================================
# 绑定申请审批
# ============================================================
@router.get("/bind-requests", response_model=List[BoatBindRequestResponse])
def list_bind_requests(
    boat_id: Optional[int] = Query(None, description="按船ID筛选"),
    status_filter: Optional[str] = Query(None, alias="status", description="按状态筛选"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    获取绑定申请列表
    - 管理员：可查看自己管理的船的所有申请
    - 普通用户：只能查看自己的申请记录
    """
    query = db.query(BoatBindRequest)

    # 判断用户是否是某船的管理员
    owner_boats = db.query(BoatBinding).filter(
        BoatBinding.user_id == current_user.id,
        BoatBinding.role == "owner"
    ).all()
    owner_boat_ids = [b.boat_id for b in owner_boats]

    if boat_id:
        # 指定了船ID，检查权限
        if boat_id not in owner_boat_ids:
            # 不是管理员，只能看自己的申请
            query = query.filter(BoatBindRequest.requester_id == current_user.id)
        query = query.filter(BoatBindRequest.boat_id == boat_id)
    else:
        if owner_boat_ids:
            # 管理员可看自己管理的船的申请 + 自己的申请
            query = query.filter(
                (BoatBindRequest.boat_id.in_(owner_boat_ids)) |
                (BoatBindRequest.requester_id == current_user.id)
            )
        else:
            # 普通用户只能看自己的申请
            query = query.filter(BoatBindRequest.requester_id == current_user.id)

    if status_filter:
        query = query.filter(BoatBindRequest.status == status_filter)

    requests = query.order_by(BoatBindRequest.created_at.desc()).limit(100).all()

    result = []
    for req in requests:
        boat = db.query(Boat).filter(Boat.id == req.boat_id).first()
        requester = db.query(User).filter(User.id == req.requester_id).first()
        result.append(BoatBindRequestResponse(
            id=req.id,
            boat_id=req.boat_id,
            boat_name=boat.name if boat else "未知船",
            requester_id=req.requester_id,
            requester_name=requester.username if requester else "未知用户",
            status=req.status,
            reject_reason=req.reject_reason,
            created_at=req.created_at,
            processed_at=req.processed_at,
        ))
    return result


@router.post("/bind-requests/{request_id}/approve")
def approve_bind_request(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """管理员同意绑定申请"""
    req = db.query(BoatBindRequest).filter(BoatBindRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="申请不存在")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail=f"该申请状态为{req.status}，不能审批")

    # 检查当前用户是否是该船的管理员
    require_owner(db, current_user, req.boat_id)

    # 检查申请者是否已绑定
    existing = get_user_binding(db, req.requester_id, req.boat_id)
    if existing:
        req.status = "approved"
        req.processed_at = datetime.utcnow()
        req.processed_by = current_user.id
        db.commit()
        return {"status": "success", "message": "该用户已绑定此船"}

    # 创建绑定关系
    new_binding = BoatBinding(
        user_id=req.requester_id,
        boat_id=req.boat_id,
        role="viewer",
    )
    db.add(new_binding)
    req.status = "approved"
    req.processed_at = datetime.utcnow()
    req.processed_by = current_user.id
    db.commit()

    requester = db.query(User).filter(User.id == req.requester_id).first()
    return {
        "status": "success",
        "message": f"已同意【{requester.username if requester else req.requester_id}】的绑定申请",
    }


@router.post("/bind-requests/{request_id}/reject")
def reject_bind_request(
    request_id: int,
    action: BindRequestAction,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """管理员拒绝绑定申请"""
    req = db.query(BoatBindRequest).filter(BoatBindRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="申请不存在")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail=f"该申请状态为{req.status}，不能审批")

    require_owner(db, current_user, req.boat_id)

    req.status = "rejected"
    req.reject_reason = action.reject_reason
    req.processed_at = datetime.utcnow()
    req.processed_by = current_user.id
    db.commit()

    return {"status": "success", "message": "已拒绝该绑定申请"}


@router.post("/bind-requests/{request_id}/cancel")
def cancel_bind_request(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """申请者取消自己的绑定申请"""
    req = db.query(BoatBindRequest).filter(BoatBindRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="申请不存在")
    if req.requester_id != current_user.id:
        raise HTTPException(status_code=403, detail="只能取消自己的申请")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail=f"该申请状态为{req.status}，不能取消")

    req.status = "cancelled"
    req.processed_at = datetime.utcnow()
    db.commit()
    return {"status": "success", "message": "已取消绑定申请"}


# ============================================================
# 船绑定码管理
# ============================================================
@router.post("/boats/{boat_id}/reset-bind-code")
def reset_bind_code(
    boat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """管理员重置船的绑定码"""
    require_owner(db, current_user, boat_id)
    boat = get_boat_or_404(db, boat_id)

    new_code = generate_bind_code()
    # 确保不重复
    while db.query(Boat).filter(Boat.bind_code == new_code).first():
        new_code = generate_bind_code()

    boat.bind_code = new_code
    db.commit()
    return {
        "status": "success",
        "bind_code": new_code,
        "message": "绑定码已重置",
    }


@router.post("/boats/{boat_id}/toggle-bind")
def toggle_bind_enabled(
    boat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """管理员开关船的绑定功能"""
    require_owner(db, current_user, boat_id)
    boat = get_boat_or_404(db, boat_id)

    boat.bind_enabled = not boat.bind_enabled
    db.commit()
    return {
        "status": "success",
        "bind_enabled": boat.bind_enabled,
        "message": f"已{'开启' if boat.bind_enabled else '关闭'}绑定功能",
    }
