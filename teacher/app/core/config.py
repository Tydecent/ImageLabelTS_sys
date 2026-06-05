"""
配置管理模块
所有敏感信息和路径均从环境变量读取
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # JWT 配置
    JWT_SECRET: str = "change-me-in-production-very-long-secret-key"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 8

    # 数据目录
    DATA_DIR: str = "/data"

    # 数据库
    DATABASE_URL: str = "sqlite+aiosqlite:////data/app.db"

    # 教师端 API Key（可选，留空则不校验）
    TEACHER_API_KEY: str = ""

    # 服务端口
    PORT: int = 12010

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # 忽略未定义的环境变量（如 Docker/系统注入的变量）

    @property
    def images_dir(self) -> Path:
        return Path(self.DATA_DIR) / "images"

    @property
    def annotations_dir(self) -> Path:
        return Path(self.DATA_DIR) / "annotations"

    @property
    def exports_dir(self) -> Path:
        return Path(self.DATA_DIR) / "exports"


# 全局单例
settings = Settings()
