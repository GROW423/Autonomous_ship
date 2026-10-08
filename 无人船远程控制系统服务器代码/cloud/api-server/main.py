"""
无人船云平台 FastAPI 入口
"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import engine, Base
from websocket import router as ws_router, broadcast_loop

# 导入路由
from routers import auth, boats, missions, telemetry, control, regions, users, bindings, control_grants


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期: 启动时建表+启动WebSocket广播"""
    # 创建数据库表
    Base.metadata.create_all(bind=engine)
    # 启动WebSocket广播循环
    task = asyncio.create_task(broadcast_loop())
    yield
    task.cancel()


app = FastAPI(
    title="无人船远程控制系统 API",
    description="基于ArduPilot的无人船远程投喂控制系统云平台",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
origins = settings.CORS_ORIGINS.split(",") if settings.CORS_ORIGINS != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router)
app.include_router(boats.router)
app.include_router(regions.router)
app.include_router(users.router)
app.include_router(missions.router)
app.include_router(telemetry.router)
app.include_router(control.router)
app.include_router(bindings.router)
app.include_router(control_grants.router)
app.include_router(ws_router)


@app.get("/", tags=["系统"])
def root():
    return {
        "name": "无人船远程控制系统 API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health", tags=["系统"])
def health():
    """健康检查"""
    return {"status": "ok"}
