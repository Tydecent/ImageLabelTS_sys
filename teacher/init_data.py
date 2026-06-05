"""
init_data.py — 初始化学生账号、图片记录和分配关系
使用方式：
  # 本地运行
  DATA_DIR=./data DATABASE_URL="sqlite+aiosqlite:///./data/app.db" python init_data.py

  # Docker 容器内运行
  docker exec -it annotation-server python /app/init_data.py
"""
import asyncio
import os
import sys
from pathlib import Path

# 确保 app 包可被找到
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.models.student import Student
from app.models.image import Image
from app.models.assignment import Assignment
from app.core.database import Base

# ────────────────────────────────────────────────────────────────────────────
# ★ 在此处修改学生名单和初始密码
STUDENTS: dict[str, str] = {
    "张三": "123456",
    "李四": "123456",
    "王五": "123456",
    # 继续添加最多 15 名学生...
}

# ★ 图片目录（默认从 DATA_DIR/images 读取）
IMAGES_DIR: Path = settings.images_dir
# ────────────────────────────────────────────────────────────────────────────

# 支持的图片扩展名
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}


async def main() -> None:
    engine = create_async_engine(settings.DATABASE_URL)
    AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # 创建所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✓ 数据库表已就绪")

    async with AsyncSessionLocal() as db:
        # ── 导入图片 ──
        image_files = sorted(
            f for f in IMAGES_DIR.iterdir()
            if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
        )
        if not image_files:
            print(f"⚠ 图片目录 {IMAGES_DIR} 中未找到图片，请先将图片放入该目录")

        new_images: list[Image] = []
        skip_images = 0
        for img_path in image_files:
            existing = await db.execute(select(Image).where(Image.filename == img_path.name))
            if existing.scalar_one_or_none():
                skip_images += 1
                continue
            img = Image(
                filename=img_path.name,
                original_path=str(img_path),
                file_size=img_path.stat().st_size,
            )
            db.add(img)
            new_images.append(img)

        if new_images:
            await db.flush()
        print(f"✓ 导入图片：新增 {len(new_images)} 张，跳过已存在 {skip_images} 张")

        # ── 导入学生 ──
        students: list[Student] = []
        new_students = 0
        for name, password in STUDENTS.items():
            existing = await db.execute(select(Student).where(Student.name == name))
            stu = existing.scalar_one_or_none()
            if stu:
                students.append(stu)
            else:
                stu = Student(name=name, password_hash=hash_password(password))
                db.add(stu)
                students.append(stu)
                new_students += 1

        if new_students:
            await db.flush()
        print(f"✓ 导入学生：新增 {new_students} 名，跳过已存在 {len(STUDENTS) - new_students} 名")

        # ── 查询所有图片（含已存在的） ──
        all_images_result = await db.execute(select(Image))
        all_images: list[Image] = all_images_result.scalars().all()

        if not all_images or not students:
            print("⚠ 图片或学生列表为空，跳过分配")
            await db.commit()
            return

        # ── 均匀分配（轮询） ──
        new_assignments = 0
        skip_assignments = 0
        for i, img in enumerate(all_images):
            stu = students[i % len(students)]
            existing = await db.execute(
                select(Assignment).where(
                    Assignment.student_id == stu.id,
                    Assignment.image_id == img.id,
                )
            )
            if existing.scalar_one_or_none():
                skip_assignments += 1
                continue
            db.add(Assignment(student_id=stu.id, image_id=img.id))
            new_assignments += 1

        await db.commit()
        print(f"✓ 分配关系：新增 {new_assignments} 条，跳过已存在 {skip_assignments} 条")
        print()
        print("════════════════════════════════")
        print("  初始化完成，服务已可正常使用  ")
        print("════════════════════════════════")
        print(f"  学生数: {len(students)}")
        print(f"  图片数: {len(all_images)}")
        print(f"  平均每人: {len(all_images) // len(students)} 张")


if __name__ == "__main__":
    asyncio.run(main())
