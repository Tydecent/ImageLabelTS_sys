"""
分配服务：封装学生-图片分配相关的数据库查询逻辑
"""
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.assignment import Assignment
from app.models.annotation import Annotation
from app.models.image import Image
from app.models.student import Student

logger = logging.getLogger(__name__)


async def get_student_assignments(
    db: AsyncSession, student: Student
) -> list[Assignment]:
    """
    查询学生的所有分配记录（含关联图片和标注）
    """
    result = await db.execute(
        select(Assignment)
        .where(Assignment.student_id == student.id)
        .options(
            selectinload(Assignment.image),
            selectinload(Assignment.annotation),
        )
    )
    return result.scalars().all()


async def get_assignment_by_student_and_image(
    db: AsyncSession, student_id: int, image_id: int
) -> Assignment | None:
    """按学生 ID 和图片 ID 查询分配记录"""
    result = await db.execute(
        select(Assignment).where(
            Assignment.student_id == student_id,
            Assignment.image_id == image_id,
        )
    )
    return result.scalar_one_or_none()


async def compute_md5(file_path: Path) -> str:
    """同步计算文件 MD5（文件较小，可在协程中直接调用）"""
    h = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


async def upsert_annotation(
    db: AsyncSession,
    assignment: Assignment,
    file_path: Path,
    file_hash: str,
) -> Annotation:
    """
    插入或更新 Annotation 记录
    """
    now = datetime.now(timezone.utc)

    if assignment.annotation:
        # 更新已有记录
        ann = assignment.annotation
        ann.file_path = str(file_path)
        ann.file_hash = file_hash
        ann.last_modified = now
        logger.info("更新标注记录 assignment_id=%d hash=%s", assignment.id, file_hash)
    else:
        # 新建记录
        ann = Annotation(
            assignment_id=assignment.id,
            file_path=str(file_path),
            file_hash=file_hash,
            uploaded_at=now,
            last_modified=now,
        )
        db.add(ann)
        logger.info("新建标注记录 assignment_id=%d hash=%s", assignment.id, file_hash)

    await db.flush()  # 获取 ID 但不提交，由外层会话统一提交
    return ann


async def get_all_students_overview(db: AsyncSession) -> list[dict]:
    """
    聚合查询所有学生的任务进度，返回结构化列表
    """
    # 查询所有学生
    students_result = await db.execute(
        select(Student).options(
            selectinload(Student.assignments).selectinload(Assignment.image),
            selectinload(Student.assignments).selectinload(Assignment.annotation),
        )
    )
    students = students_result.scalars().all()

    overview = []
    for stu in students:
        assignments = stu.assignments
        images = [a.image.filename for a in assignments if a.image]
        uploaded_images = [
            Path(a.image.filename).stem
            for a in assignments
            if a.annotation and a.image
        ]

        # 最后推送时间：取该学生所有标注的最新 last_modified
        last_push = None
        for a in assignments:
            if a.annotation:
                lm = a.annotation.last_modified
                if last_push is None or lm > last_push:
                    last_push = lm

        overview.append(
            {
                "name": stu.name,
                "total": len(assignments),
                "uploaded": len(uploaded_images),
                "images": images,
                "uploaded_images": uploaded_images,
                "last_push": last_push.isoformat() if last_push else None,
            }
        )

    return overview
