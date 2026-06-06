"""
Image ORM 模型
"""
from datetime import datetime, timezone
from sqlalchemy import String, BigInteger, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Image(Base):
    __tablename__ = "images"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # 不加 index=True，避免与 __table_args__ 中的 Index 重复定义
    filename: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    original_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, default=0)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # 关系
    assignments: Mapped[list["Assignment"]] = relationship(  # noqa: F821
        "Assignment", back_populates="image", lazy="select"
    )

    __table_args__ = (
        Index("ix_images_filename", "filename"),
    )
