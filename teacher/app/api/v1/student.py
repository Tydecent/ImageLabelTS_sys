"""
学生端 API 路由：login / pull / push / status / health
"""
import logging
from pathlib import Path

import aiofiles
import aiofiles.os
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    get_current_student,
    verify_password,
)
from app.models.student import Student
from app.services.assignment_service import (
    compute_md5,
    get_student_assignments,
    upsert_annotation,
)
from app.services.notification import notification_hub
from app.services.zip_service import build_task_zip

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── 1. 学生登录 ─────────────────────────────────────────────────────────────

@router.post("/login")
async def login(payload: dict, db: AsyncSession = Depends(get_db)):
    """
    POST /login
    请求体: {"name": "张三", "password": "123456"}
    返回: {"status": "ok", "token": "...", "task_count": 8}
    """
    name: str = payload.get("name", "").strip()
    password: str = payload.get("password", "")

    if not name or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="姓名和密码不能为空",
        )

    result = await db.execute(select(Student).where(Student.name == name))
    student = result.scalar_one_or_none()

    if not student or not verify_password(password, student.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="姓名或密码错误",
        )

    # 查询任务数量
    assignments = await get_student_assignments(db, student)
    token = create_access_token(student.name)

    logger.info("学生 %s 登录成功，任务数 %d", name, len(assignments))
    return {"status": "ok", "token": token, "task_count": len(assignments)}


# ─── 2. 拉取任务包 ────────────────────────────────────────────────────────────

@router.get("/pull")
async def pull(
    student=Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """
    GET /pull
    流式返回 ZIP：包含该学生所有原始图片 + 已有标注 JSON（若有）
    Content-Disposition: attachment; filename="{学生姓名}_task.zip"
    """
    assignments = await get_student_assignments(db, student)

    if not assignments:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="该学生暂无分配任务",
        )

    image_paths: list[Path] = []
    annotation_paths: list[Path | None] = []

    for assignment in assignments:
        img = assignment.image
        img_path = Path(img.original_path)
        image_paths.append(img_path)

        # 检查标注文件是否存在
        stem = Path(img.filename).stem
        ann_path = settings.annotations_dir / student.name / f"{stem}.json"
        annotation_paths.append(ann_path if ann_path.exists() else None)

    filename = f"{student.name}_task.zip"
    logger.info("学生 %s 拉取任务包，图片数 %d", student.name, len(image_paths))

    return StreamingResponse(
        build_task_zip(image_paths, annotation_paths),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ─── 3. 上传标注文件 ──────────────────────────────────────────────────────────

@router.post("/push")
async def push(
    file: UploadFile = File(...),
    student=Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """
    POST /push
    multipart/form-data，字段名 file
    返回: {"status": "ok"}
    """
    # 校验文件扩展名
    if not file.filename or not file.filename.lower().endswith(".json"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只允许上传 .json 文件",
        )

    # 提取基本名（不含扩展名）
    stem = Path(file.filename).stem

    # 查找该学生是否有匹配图片
    assignments = await get_student_assignments(db, student)
    matched_assignment = None
    for a in assignments:
        if Path(a.image.filename).stem == stem:
            matched_assignment = a
            break

    if not matched_assignment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"文件名 '{stem}' 与该学生任务不匹配",
        )

    # 确保学生标注目录存在
    student_ann_dir = settings.annotations_dir / student.name
    student_ann_dir.mkdir(parents=True, exist_ok=True)

    save_path = student_ann_dir / f"{stem}.json"

    # 异步写入文件（覆盖旧文件）
    content = await file.read()
    async with aiofiles.open(save_path, "wb") as f:
        await f.write(content)

    # 计算 MD5
    file_hash = await compute_md5(save_path)

    # 更新数据库
    await upsert_annotation(db, matched_assignment, save_path, file_hash)
    await db.commit()

    logger.info(
        "学生 %s 上传标注 %s，MD5=%s", student.name, file.filename, file_hash
    )

    # 广播 WebSocket 通知
    updated_assignments = await get_student_assignments(db, student)
    uploaded_count = sum(1 for a in updated_assignments if a.annotation)
    total_count = len(updated_assignments)

    await notification_hub.publish(
        {
            "event": "push",
            "student": student.name,
            "image": f"{stem}.json",
            "uploaded": uploaded_count,
            "total": total_count,
        }
    )

    return {"status": "ok"}


# ─── 4. 查询任务状态 ──────────────────────────────────────────────────────────

@router.get("/status")
async def get_status(
    student=Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """
    GET /status
    返回当前学生自身的任务统计，不暴露他人数据
    """
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
    unuploaded = total - uploaded_count

    return {
        "uploaded": uploaded_count,
        "unuploaded": unuploaded,
        "total": total,
        "assigned_images": assigned_images,
        "uploaded_details": uploaded_details,
    }


# ─── 7. 健康检查 ──────────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    """GET /health — 服务健康检查"""
    return {"status": "ok"}
