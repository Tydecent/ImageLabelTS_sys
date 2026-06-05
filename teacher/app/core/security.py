"""
安全模块：JWT 生成/验证、密码哈希、认证依赖
直接使用 bcrypt 4.x 库，避免 passlib 兼容性问题
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_db

logger = logging.getLogger(__name__)


# ─── 密码工具 ───────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """将明文密码哈希为 bcrypt 散列值"""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """验证明文密码与哈希是否匹配"""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ─── JWT 工具 ────────────────────────────────────────────────────────────────

def create_access_token(subject: str) -> str:
    """
    生成 JWT 访问令牌
    :param subject: 学生姓名（sub 字段）
    """
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRE_HOURS)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Optional[str]:
    """
    解码 JWT 令牌，返回 sub（学生姓名），失败返回 None
    """
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        return payload.get("sub")
    except JWTError:
        return None


# ─── FastAPI 依赖 ─────────────────────────────────────────────────────────────

async def get_current_student(
    authorization: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """
    依赖注入：从 Authorization: Bearer <token> 中解析并返回当前学生 ORM 对象
    """
    # 延迟导入避免循环依赖
    from app.models.student import Student

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少或无效的令牌",
        )

    token = authorization.removeprefix("Bearer ").strip()
    name = decode_token(token)
    if not name:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少或无效的令牌",
        )

    result = await db.execute(select(Student).where(Student.name == name))
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少或无效的令牌",
        )

    return student


def check_teacher_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    """
    可选的教师端 API Key 校验依赖。
    若环境变量 TEACHER_API_KEY 非空，则要求请求头 X-API-Key 匹配。
    """
    if settings.TEACHER_API_KEY:
        if x_api_key != settings.TEACHER_API_KEY:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的教师 API Key",
            )
