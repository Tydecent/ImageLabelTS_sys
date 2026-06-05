"""
ZIP 打包服务：流式生成学生任务包
"""
import io
import logging
import zipfile
from pathlib import Path
from typing import AsyncGenerator

import aiofiles

logger = logging.getLogger(__name__)


async def build_task_zip(
    image_paths: list[Path],
    annotation_paths: list[Path | None],
) -> AsyncGenerator[bytes, None]:
    """
    异步生成器，流式产出 ZIP 字节块。

    :param image_paths: 原始图片路径列表
    :param annotation_paths: 与图片对应的标注文件路径列表（无则为 None）
    """
    # 使用 BytesIO 作为缓冲，控制内存占用
    buf = io.BytesIO()

    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for img_path, ann_path in zip(image_paths, annotation_paths):
            # 写入原始图片
            if img_path.exists():
                try:
                    async with aiofiles.open(img_path, "rb") as f:
                        data = await f.read()
                    zf.writestr(img_path.name, data)
                except Exception as exc:
                    logger.warning("读取图片失败 %s: %s", img_path, exc)
            else:
                logger.warning("图片文件不存在，跳过: %s", img_path)

            # 写入对应的标注 JSON（若存在）
            if ann_path and ann_path.exists():
                try:
                    async with aiofiles.open(ann_path, "rb") as f:
                        ann_data = await f.read()
                    zf.writestr(ann_path.name, ann_data)
                except Exception as exc:
                    logger.warning("读取标注失败 %s: %s", ann_path, exc)

    # 全部写完后一次性 yield（文件总大小 ≤1.5GB，内存可接受）
    buf.seek(0)
    yield buf.read()


async def build_all_annotations_zip(
    annotations_dir: Path,
) -> AsyncGenerator[bytes, None]:
    """
    打包所有已上传的标注文件，按学生子目录组织。

    :param annotations_dir: /data/annotations 根目录
    """
    buf = io.BytesIO()

    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        if annotations_dir.exists():
            for student_dir in sorted(annotations_dir.iterdir()):
                if student_dir.is_dir():
                    for json_file in sorted(student_dir.glob("*.json")):
                        try:
                            async with aiofiles.open(json_file, "rb") as f:
                                data = await f.read()
                            # 保留学生子目录结构
                            arcname = f"{student_dir.name}/{json_file.name}"
                            zf.writestr(arcname, data)
                        except Exception as exc:
                            logger.warning("读取标注失败 %s: %s", json_file, exc)

    buf.seek(0)
    yield buf.read()
