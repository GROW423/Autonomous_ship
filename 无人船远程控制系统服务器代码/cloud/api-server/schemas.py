"""
Pydantic Schemas (请求/响应数据验证)
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ============================================================
# 用户
# ============================================================
class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    email: Optional[str] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: Optional[str]
    full_name: Optional[str]
    phone: Optional[str]
    role: str = "user"
    region_id: Optional[int] = None
    region_name: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserCreateAdmin(BaseModel):
    """管理员创建用户 (可指定角色和区域)"""
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    email: Optional[str] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    role: str = Field(default="user", description="admin/regional_admin/user")
    region_id: Optional[int] = Field(None, description="地方管理员负责的区域ID")


class UserUpdate(BaseModel):
    """管理员更新用户信息"""
    email: Optional[str] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    region_id: Optional[int] = None
    is_active: Optional[bool] = None


class PasswordReset(BaseModel):
    """重置密码"""
    new_password: str = Field(min_length=6, max_length=128)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ============================================================
# 区域
# ============================================================
class RegionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    description: Optional[str] = None


class RegionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class RegionResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================
# 航点
# ============================================================
class Waypoint(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    alt: float = 0.0
    speed: float = 1.5  # m/s
    action: Optional[str] = None  # "feed_start", "feed_stop", None


# ============================================================
# 无人船
# ============================================================
class BoatCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    mavlink_sys_id: int = Field(default=1, ge=1, le=255, description="MAVLink系统ID, 多船可重复, 默认1")
    iccid: str = Field(min_length=15, max_length=32, description="4G物联网卡ICCID, 全球唯一, 用于船身份识别")
    region_id: Optional[int] = Field(None, description="所属区域ID")
    description: Optional[str] = None
    home_lat: Optional[float] = None
    home_lon: Optional[float] = None


class BoatUpdate(BaseModel):
    name: Optional[str] = None
    region_id: Optional[int] = None
    description: Optional[str] = None
    home_lat: Optional[float] = None
    home_lon: Optional[float] = None
    is_active: Optional[bool] = None


class BoatResponse(BaseModel):
    id: int
    name: str
    mavlink_sys_id: int
    boat_key: str
    iccid: Optional[str]
    region_id: Optional[int]
    region_name: Optional[str] = None
    description: Optional[str]
    home_lat: Optional[float]
    home_lon: Optional[float]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class BoatStatus(BaseModel):
    """船的实时状态 (从Redis读取)"""
    boat_id: str
    online: bool = False
    lat: Optional[float] = None
    lon: Optional[float] = None
    heading: Optional[float] = None
    groundspeed: Optional[float] = None
    battery_voltage: Optional[float] = None
    battery_current: Optional[float] = None
    battery_remaining: Optional[int] = None
    flight_mode: Optional[str] = None
    armed: Optional[bool] = None
    current_waypoint: Optional[int] = None
    feed_level: Optional[float] = None
    cellular_csq: Optional[int] = None
    box_temperature: Optional[float] = None
    gps_fix_type: Optional[str] = None
    gps_satellites_visible: Optional[int] = None
    last_status_text: Optional[str] = None
    updated_at: Optional[float] = None


# ============================================================
# 任务
# ============================================================
class MissionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: Optional[str] = None
    waypoints: List[Waypoint]


class MissionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    waypoints: Optional[List[Waypoint]] = None


class MissionResponse(BaseModel):
    id: int
    boat_id: int
    name: str
    description: Optional[str]
    waypoints: List[Waypoint]
    status: str
    created_at: datetime
    updated_at: Optional[datetime]
    executed_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


# ============================================================
# 控制指令
# ============================================================
class ControlCommand(BaseModel):
    """控制指令 (下发到船端)"""
    type: str = Field(description="指令类型: set_mode/arm_disarm/rtl/mission_start/do_set_servo/manual_control")
    # 通用参数
    custom_mode: Optional[int] = Field(None, description="飞行模式: 0=MANUAL,10=AUTO,11=RTL,15=GUIDED")
    arm: Optional[bool] = None
    channel: Optional[int] = None
    pwm: Optional[int] = None
    x: Optional[int] = Field(None, description="手动控制方向 -1000~1000")
    y: Optional[int] = Field(None, description="手动控制油门 -1000~1000")


class CommandResponse(BaseModel):
    success: bool
    message: str


# ============================================================
# 遥测历史
# ============================================================
class TelemetryRecord(BaseModel):
    timestamp: datetime
    lat: Optional[float]
    lon: Optional[float]
    heading: Optional[float]
    groundspeed: Optional[float]
    battery_remaining: Optional[int]
    flight_mode: Optional[str]
    current_waypoint: Optional[int]
    feed_level: Optional[float]

    class Config:
        from_attributes = True


# ============================================================
# 船绑定关系
# ============================================================
class BoatBindRequest(BaseModel):
    """绑定船请求 (输入ICCID或绑定码)"""
    iccid: Optional[str] = Field(None, description="4G物联网卡ICCID")
    bind_code: Optional[str] = Field(None, description="船绑定码")


class BoatBindingResponse(BaseModel):
    """绑定关系响应"""
    id: int
    user_id: int
    boat_id: int
    role: str  # owner / viewer
    alias: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class BoatMemberResponse(BaseModel):
    """船成员响应 (含用户信息)"""
    binding_id: int
    user_id: int
    username: str
    full_name: Optional[str] = None
    role: str  # owner / viewer
    is_owner: bool
    created_at: datetime
    last_active_at: Optional[datetime] = None


class BoatBindRequestResponse(BaseModel):
    """绑定申请响应"""
    id: int
    boat_id: int
    boat_name: str
    requester_id: int
    requester_name: str
    status: str  # pending / approved / rejected / cancelled / expired
    reject_reason: Optional[str] = None
    created_at: datetime
    processed_at: Optional[datetime] = None


class BindRequestAction(BaseModel):
    """审批绑定申请"""
    reject_reason: Optional[str] = Field(None, max_length=256)


class TransferOwnerRequest(BaseModel):
    """转移管理员请求"""
    new_owner_id: int = Field(description="新的管理员用户ID")
    password: str = Field(description="当前管理员密码（用于二次确认）")


class BoatResponseWithRole(BoatResponse):
    """船响应 (含当前用户角色)"""
    role: Optional[str] = None  # 当前用户在该船的角色 owner/viewer/None
    is_owner: bool = False
    bind_code: Optional[str] = None
    bind_enabled: bool = True
    owner_id: Optional[int] = None
    owner_name: Optional[str] = None


# ============================================================
# 控制授权
# ============================================================
class ControlGrantRequest(BaseModel):
    """申请控制权限"""
    reason: Optional[str] = Field(None, max_length=256, description="申请原因")
    duration_minutes: int = Field(default=60, ge=5, le=1440, description="申请时长(分钟), 5-1440")


class ControlGrantApproveRequest(BaseModel):
    """审批控制申请"""
    duration_minutes: Optional[int] = Field(None, ge=5, le=1440, description="实际授权时长(分钟), 不填则用申请时长")
    reject_reason: Optional[str] = Field(None, max_length=256)


class ControlGrantResponse(BaseModel):
    """控制授权响应"""
    id: int
    boat_id: int
    boat_name: str
    requester_id: int
    requester_name: str
    granter_id: Optional[int] = None
    granter_name: Optional[str] = None
    status: str  # pending / approved / rejected / expired / revoked
    reason: Optional[str] = None
    reject_reason: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    remaining_seconds: Optional[int] = None
    created_at: datetime
    approved_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None


class ControlPermissionResponse(BaseModel):
    """当前用户控制权限查询响应"""
    boat_id: int
    role: str  # owner / viewer / none
    has_control: bool
    is_owner: bool
    active_grant: Optional[ControlGrantResponse] = None
    remaining_seconds: Optional[int] = None
    can_apply: bool  # 是否可以申请控制（viewer且无有效授权时为true）
