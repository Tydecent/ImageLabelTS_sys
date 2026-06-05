"""
Assignment ORM 模型（学生-图片分配关系）
"""
from datetime import datetime, timezone
from sqlalchemy import ForeignKey, DateTime, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Assignment(Base):
    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    image_id: Mapped[int] = mapped_column(ForeignKey("images.id"), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # 关系
    student: Mapped["Student"] = relationship(  # noqa: F821
        "Student", back_populates="assignments"
    )
    image: Mapped["Image"] = relationship(  # noqa: F821
        "Image", back_populates="assignments"
    )
    annotation: Mapped["Annotation"] = relationship(  # noqa: F821
        "Annotation", back_populates="assignment", uselist=False, lazy="select"
    )

    __table_args__ = (
        UniqueConstraint("student_id", "image_id", name="uq_assignment_student_image"),
        Index("ix_assignments_student_id", "student_id"),
        Index("ix_assignments_image_id", "image_id"),
    )
