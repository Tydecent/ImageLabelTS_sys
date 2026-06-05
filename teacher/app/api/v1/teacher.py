"""
教师端 API 路由：
  GET  /api/overview               — 所有学生进度概览（无需认证）
  POST /reassign                   — 改派图片（无需认证，可选 X-API-Key）
  GET  /api/students/{name}/status — 教师查看指定学生状态
  GET  /api/images                 — 所有图片分配情况
  GET  /api/export/annotations     — 导出全部标注 ZIP
  GET  /api/stats                  — 服务运行统计
"""
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.security import check_teacher_api_key, get_current_student
from app.models.assignment import Assignment
from app.models.image import Image
from app.models.student import Student
from app.services.assignment_service import (
    get_all_students_overview,
    get_assignment_by_student_and_image,
    get_student_assignments,
)
from app.services.zip_service import build_all_annotations_zip

logger = logging.getLogger(__name__)

# 学生路由（带 /api 前缀的教师扩展接口）
router_api = APIRouter(prefix="/api")
# 顶层路由（/reassign 不带 /api 前缀）
router_top = APIRouter()

# 服务启动时间（由 main.py lifespan 注入）
service_start_time: datetime = datetime.now(timezone.utc)


# ─── 5. 教师概览 ──────────────────────────────────────────────────────────────

@router_api.get("/overview")
async def overview(db: AsyncSession = Depends(get_db)):
    """
    GET /api/overview — 无需认证
    返回所有学生任务进度和全局统计
    """
    students_data = await get_all_students_overview(db)

    total_overall = sum(s["total"] for s in students_data)
    uploaded_overall = sum(s["uploaded"] for s in students_data)

    return {
        "students": students_data,
        "total_overall": {
            "total": total_overall,
            "uploaded": uploaded_overall,
        },
    }


# ─── 6. 改派图片 ──────────────────────────────────────────────────────────────

@router_top.post("/reassign")
async def reassign(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(check_teacher_api_key),
):
    """
    POST /reassign
    请求体: {"image": "cat.jpg", "from_student": "张三", "to_student": "李四"}
    """
    image_name: str = payload.get("image", "").strip()
    from_name: str = payload.get("from_student", "").strip()
    to_name: str = payload.get("to_student", "").strip()

    if not all([image_name, from_name, to_name]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="缺少必要字段：image, from_student, to_student",
        )

    # 查找图片记录
    img_result = await db.execute(
        select(Image).where(Image.filename == image_name)
    )
    image = img_result.scalar_one_or_none()
    if not image:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"图片 '{image_name}' 不存在",
        )

    # 查找来源学生
    from_result = await db.execute(
        select(Student).where(Student.name == from_name)
    )
    from_student = from_result.scalar_one_or_none()
    if not from_student:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"学生 '{from_name}' 不存在",
        )

    # 查找目标学生
    to_result = await db.execute(
        select(Student).where(Student.name == to_name)
    )
    to_student = to_result.scalar_one_or_none()
    if not to_student:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"学生 '{to_name}' 不存在",
        )

    # 查找分配记录（需要 from_student 拥有该图片）
    assignment = await get_assignment_by_student_and_image(
        db, from_student.id, image.id
    )
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"学生 '{from_name}' 未分配图片 '{image_name}'",
        )

    # 检查目标学生是否已有该图片
    existing = await get_assignment_by_student_and_image(
        db, to_student.id, image.id
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"学生 '{to_name}' 已分配了图片 '{image_name}'",
        )

    # 检查原学生是否已上传标注（提前加载 annotation）
    await db.refresh(assignment, ["annotation"])
    warning = None
    stem = Path(image_name).stem
    if assignment.annotation:
        warning = (
            f"学生 {from_name} 已为该图片上传标注文件 ({stem}.json)，"
            f"文件仍保留在其目录下，请手动处理"
        )

    # 在事务中更新分配（改变 student_id）
    assignment.student_id = to_student.id
    await db.commit()

    logger.info("改派图片 %s：%s -> %s", image_name, from_name, to_name)

    response: dict = {
        "status": "ok",
        "message": f"已将 '{image_name}' 从 {from_name} 改派给 {to_name}",
    }
    if warning:
        response["warning"] = warning

    return response


# ─── 扩展：教师查看指定学生状态 ───────────────────────────────────────────────

@router_api.get("/students/{name}/status")
async def teacher_student_status(
    name: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(check_teacher_api_key),
):
    """GET /api/students/{name}/status — 教师查看指定学生状态（格式同 /status）"""
    result = await db.execute(select(Student).where(Student.name == name))
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"学生 '{name}' 不存在",
        )

    assignments = await get_student_assignments(db, student)

    assigned_images = [a.image.filename for a in assignments if a.image]
    uploaded_details = {}
    uploaded_count = 0

    for a in assignments:
        if a.annotation and a.image:
            stem = Path(a.image.filename).stem
            uploaded_details[stem] = {
                "hash": a.annotation.file_hash,
                "last_upload": a.annotation.last_modified.isoformat(),
            }
            uploaded_count += 1

    total = len(assignments)
    return {
        "uploaded": uploaded_count,
        "unuploaded": total - uploaded_count,
        "total": total,
        "assigned_images": assigned_images,
        "uploaded_details": uploaded_details,
    }


# ─── 扩展：所有图片分配情况 ───────────────────────────────────────────────────

@router_api.get("/images")
async def list_images(db: AsyncSession = Depends(get_db)):
    """
    GET /api/images
    返回所有图片的分配情况：文件名、分配给谁、是否已标注、标注哈希、上传时间
    """
    result = await db.execute(
        select(Image).options(
            selectinload(Image.assignments).selectinload(Assignment.student),
            selectinload(Image.assignments).selectinload(Assignment.annotation),
        )
    )
    images = result.scalars().all()

    items = []
    for img in images:
        assignment = img.assignments[0] if img.assignments else None
        items.append(
            {
                "filename": img.filename,
                "assigned_to": assignment.student.name if assignment else None,
                "annotated": bool(assignment and assignment.annotation),
                "hash": (
                    assignment.annotation.file_hash
                    if assignment and assignment.annotation
                    else None
                ),
                "uploaded_at": (
                    assignment.annotation.last_modified.isoformat()
                    if assignment and assignment.annotation
                    else None
                ),
            }
        )

    return {"images": items, "total": len(items)}


# ─── 扩展：导出全部标注 ZIP ────────────────────────────────────────────────────

@router_api.get("/export/annotations")
async def export_annotations():
    """
    GET /api/export/annotations
    流式下载所有已上传标注，按学生目录组织
    """
    logger.info("教师请求导出全部标注文件")
    return StreamingResponse(
        build_all_annotations_zip(settings.annotations_dir),
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="all_annotations.zip"'
        },
    )


# ─── 扩展：服务运行统计 ────────────────────────────────────────────────────────

@router_api.get("/stats")
async def stats(db: AsyncSession = Depends(get_db)):
    """
    GET /api/stats
    服务运行统计：学生总数、图片总数、已标注数、磁盘使用量、启动时间
    """
    from sqlalchemy import func
    from app.models.annotation import Annotation

    # 学生总数
    student_count_res = await db.execute(
        select(func.count()).select_from(Student)
    )
    student_count = student_count_res.scalar()

    # 图片总数
    image_count_res = await db.execute(
        select(func.count()).select_from(Image)
    )
    image_count = image_count_res.scalar()

    # 已标注数
    annotated_count_res = await db.execute(
        select(func.count()).select_from(Annotation)
    )
    annotated_count = annotated_count_res.scalar()

    # 磁盘使用量（/data 目录）
    try:
        usage = shutil.disk_usage(settings.DATA_DIR)
        disk_used_bytes = (
            sum(
                f.stat().st_size
                for f in Path(settings.DATA_DIR).rglob("*")
                if f.is_file()
            )
        )
    except Exception:
        disk_used_bytes = 0

    uptime_seconds = (
        datetime.now(timezone.utc) - service_start_time
    ).total_seconds()

    return {
        "students": student_count,
        "images": image_count,
        "annotated": annotated_count,
        "disk_used_bytes": disk_used_bytes,
        "start_time": service_start_time.isoformat(),
        "uptime_seconds": int(uptime_seconds),
    }
