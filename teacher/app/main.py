"""
FastAPI 应用工厂与启动入口

功能：
- 注册所有路由（学生端 / 教师端 / WebSocket）
- lifespan 事件：初始化数据库、创建数据目录
- 统一异常处理（保持与 API 手册一致的响应格式）
- 结构化日志配置
"""
import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.v1 import student as student_router
from app.api.v1 import teacher as teacher_router
from app.api.v1 import websocket as ws_router
from app.core.config import settings
from app.core.database import init_db

# ─── 日志配置 ────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ─── lifespan 事件 ────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭生命周期"""
    logger.info("服务启动中...")

    # 创建数据目录
    settings.images_dir.mkdir(parents=True, exist_ok=True)
    settings.annotations_dir.mkdir(parents=True, exist_ok=True)
    settings.exports_dir.mkdir(parents=True, exist_ok=True)

    # 初始化数据库
    await init_db()
    logger.info("数据库初始化完成")

    # 记录服务启动时间（供 /api/stats 使用）
    teacher_router.service_start_time = datetime.now(timezone.utc)

    logger.info(
        "服务已就绪，监听端口 %d，数据目录 %s",
        settings.PORT,
        settings.DATA_DIR,
    )

    yield

    logger.info("服务关闭")


# ─── FastAPI 应用实例 ─────────────────────────────────────────────────────────

app = FastAPI(
    title="教师端图像标注系统",
    description="为最多 15 名标注员提供任务分发、标注上传和进度监控服务",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ─── 统一异常处理 ─────────────────────────────────────────────────────────────

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """400 参数校验失败"""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"status": "error", "message": str(exc.errors())},
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"status": "error", "message": "资源不存在"},
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    logger.exception("服务器内部错误：%s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"status": "error", "message": "服务器内部错误"},
    )


# ─── 注册路由 ─────────────────────────────────────────────────────────────────

# 学生端：/login, /pull, /push, /status, /health
app.include_router(student_router.router)

# 教师端：/reassign（顶层，无 /api 前缀）
app.include_router(teacher_router.router_top)

# 教师端扩展：/api/overview, /api/students/..., /api/images, /api/export/..., /api/stats
app.include_router(teacher_router.router_api)

# WebSocket：/ws/overview
app.include_router(ws_router.router)


# ─── 直接运行入口 ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=False,
        log_level="info",
    )
