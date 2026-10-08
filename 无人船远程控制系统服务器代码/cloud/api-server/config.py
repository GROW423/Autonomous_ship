"""
FastAPI后端配置
"""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 数据库
    DATABASE_URL: str = os.environ.get(
        "DATABASE_URL", "postgresql://usv:usv_secret@localhost:5432/usv"
    )

    # Redis
    REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    # JWT
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev_secret_key_change_in_production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

    # CORS
    CORS_ORIGINS: str = os.environ.get("CORS_ORIGINS", "*")

    # MediaMTX
    MEDIAMTX_WEBRTC_URL: str = os.environ.get("MEDIAMTX_WEBRTC_URL", "http://localhost:8889")

    # 日志
    LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")

    class Config:
        env_file = ".env"


settings = Settings()
