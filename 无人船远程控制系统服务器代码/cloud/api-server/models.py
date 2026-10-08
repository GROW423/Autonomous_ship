"""
数据库模型 (SQLAlchemy ORM)
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class Region(Base):
    """区域表 (用于船的分类和地方管理员权限划分)"""
    __tablename__ = "regions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(64), unique=True, nullable=False, index=True)  # 如"广州南沙", "珠海", "台山"
    description = Column(String(256))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    boats = relationship("Boat", back_populates="region")
    regional_admins = relationship("User", back_populates="managed_region")


class User(Base):
    """用户表"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    email = Column(String(128), unique=True, index=True)
    hashed_password = Column(String(256), nullable=False)
    full_name = Column(String(64))
    phone = Column(String(20))
    # 用户角色: admin(总管理员,看所有船), regional_admin(地方管理员,看负责区域的船), user(普通用户,看自己的船)
    role = Column(String(32), default="user", nullable=False, index=True)
    # 地方管理员负责的区域ID (仅regional_admin有效)
    region_id = Column(Integer, ForeignKey("regions.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)  # 兼容旧字段, role=admin时为True
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 我管理的船 (作为owner)
    owned_boats = relationship("Boat", back_populates="owner", foreign_keys="Boat.owner_id", cascade="all, delete-orphan")
    # 我的船绑定关系 (包括owner和viewer)
    boat_bindings = relationship("BoatBinding", back_populates="user", cascade="all, delete-orphan")
    managed_region = relationship("Region", back_populates="regional_admins")


class Boat(Base):
    """无人船表 (多租户: 每艘船有一个管理员(owner), 可被多个用户绑定)"""
    __tablename__ = "boats"

    id = Column(Integer, primary_key=True, index=True)
    # 管理员用户ID (第一个绑定该船的用户, 可转移)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # 兼容旧字段: user_id = owner_id (后续可删除)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # 所属区域ID (可选, 用于分类和地方管理员权限)
    region_id = Column(Integer, ForeignKey("regions.id"), nullable=True, index=True)
    name = Column(String(64), nullable=False)
    # 船的MAVLink系统ID (1-255), 仅单条连接内有效, 多船可重复, 不做唯一约束
    mavlink_sys_id = Column(Integer, nullable=False, default=1)
    # 船在Redis中的唯一标识: boat_{id} (基于数据库主键, 全局唯一)
    boat_key = Column(String(64), unique=True, nullable=False)
    # 4G物联网卡ICCID (20位, 全球唯一, 作为船的硬件唯一标识)
    iccid = Column(String(32), unique=True, index=True)
    # 绑定码 (6位随机码, 用于用户绑定船, 可生成二维码)
    bind_code = Column(String(32), unique=True, index=True)
    # 是否允许被绑定 (管理员可关闭, 关闭后其他人无法提交绑定申请)
    bind_enabled = Column(Boolean, default=True)
    # 船型号/描述
    description = Column(String(256))
    # 停泊点坐标
    home_lat = Column(Float)
    home_lon = Column(Float)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", back_populates="owned_boats", foreign_keys=[owner_id])
    region = relationship("Region", back_populates="boats")
    missions = relationship("Mission", back_populates="boat", cascade="all, delete-orphan")
    bindings = relationship("BoatBinding", back_populates="boat", cascade="all, delete-orphan")
    bind_requests = relationship("BoatBindRequest", back_populates="boat", cascade="all, delete-orphan")
    control_grants = relationship("BoatControlGrant", back_populates="boat", cascade="all, delete-orphan")


class BoatBinding(Base):
    """船绑定关系表 (多对多: 一个用户可绑定多艘船, 一艘船可被多个用户绑定)"""
    __tablename__ = "boat_bindings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    boat_id = Column(Integer, ForeignKey("boats.id"), nullable=False, index=True)
    # 角色: owner(管理员, 第一个绑定者) / viewer(共享者)
    role = Column(String(20), nullable=False, default="viewer", index=True)
    # 用户给船起的别名 (可选)
    alias = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="boat_bindings")
    boat = relationship("Boat", back_populates="bindings")

    __table_args__ = (
        # 同一用户不能重复绑定同一艘船
        UniqueConstraint('user_id', 'boat_id', name='uq_user_boat'),
    )


class BoatBindRequest(Base):
    """船绑定申请表 (后续用户绑定需管理员审批)"""
    __tablename__ = "boat_bind_requests"

    id = Column(Integer, primary_key=True, index=True)
    boat_id = Column(Integer, ForeignKey("boats.id"), nullable=False, index=True)
    # 申请者用户ID
    requester_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # 状态: pending(待审批) / approved(已通过) / rejected(已拒绝) / cancelled(已取消) / expired(已过期)
    status = Column(String(20), nullable=False, default="pending", index=True)
    # 拒绝原因
    reject_reason = Column(String(256))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # 处理时间
    processed_at = Column(DateTime(timezone=True))
    # 处理者 (管理员)
    processed_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    boat = relationship("Boat", back_populates="bind_requests")
    requester = relationship("User", foreign_keys=[requester_id])


class BoatControlGrant(Base):
    """船控制授权表 (共享者申请限时控制权限, 管理员审批)"""
    __tablename__ = "boat_control_grants"

    id = Column(Integer, primary_key=True, index=True)
    boat_id = Column(Integer, ForeignKey("boats.id"), nullable=False, index=True)
    # 申请者用户ID (共享者)
    requester_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # 授权者用户ID (管理员)
    granter_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    # 状态: pending(待审批) / approved(已授权) / rejected(已拒绝) / expired(已过期) / revoked(已收回)
    status = Column(String(20), nullable=False, default="pending", index=True)
    # 申请原因
    reason = Column(String(256))
    # 拒绝原因
    reject_reason = Column(String(256))
    # 授权开始时间
    start_time = Column(DateTime(timezone=True))
    # 授权结束时间
    end_time = Column(DateTime(timezone=True))
    # 授权时长(分钟)
    duration_minutes = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    approved_at = Column(DateTime(timezone=True))
    revoked_at = Column(DateTime(timezone=True))

    boat = relationship("Boat", back_populates="control_grants")
    requester = relationship("User", foreign_keys=[requester_id])
    granter = relationship("User", foreign_keys=[granter_id])


class Mission(Base):
    """任务表 (航路点集合)"""
    __tablename__ = "missions"

    id = Column(Integer, primary_key=True, index=True)
    boat_id = Column(Integer, ForeignKey("boats.id"), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    description = Column(String(512))
    # 航点列表: [{lat, lon, alt, speed, action}, ...]
    waypoints = Column(JSON, nullable=False)
    # 任务状态: draft, uploaded, executing, completed, aborted
    status = Column(String(32), default="draft")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    # 执行统计
    executed_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))

    boat = relationship("Boat", back_populates="missions")


class TelemetryHistory(Base):
    """遥测历史表 (与mavlink-gateway创建的表对应)"""
    __tablename__ = "telemetry_history"

    id = Column(Integer, primary_key=True)
    boat_id = Column(String(64), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    lat = Column(Float)
    lon = Column(Float)
    heading = Column(Float)
    groundspeed = Column(Float)
    battery_voltage = Column(Float)
    battery_current = Column(Float)
    battery_remaining = Column(Integer)
    flight_mode = Column(String(32))
    armed = Column(Boolean)
    current_waypoint = Column(Integer)
    feed_level = Column(Float)
    cellular_csq = Column(Integer)
    box_temperature = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
