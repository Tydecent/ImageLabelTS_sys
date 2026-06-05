# 教师端图像标注系统 — 后端服务

基于 FastAPI + SQLAlchemy 2.0 异步模式构建的图像标注任务管理系统，支持最多 15 名标注员、约 1000 张图片（总大小 ≤ 1.5 GB）。

---

## 项目结构

```
app/
├── api/v1/
│   ├── student.py       # 学生端路由：/login /pull /push /status /health
│   ├── teacher.py       # 教师端路由：/api/overview /reassign /api/* 扩展
│   └── websocket.py     # WebSocket：/ws/overview
├── core/
│   ├── config.py        # 环境变量配置（pydantic-settings）
│   ├── database.py      # 异步数据库连接 & 会话
│   └── security.py      # JWT 生成/验证、bcrypt 密码哈希
├── models/
│   ├── student.py       # Student ORM 模型
│   ├── image.py         # Image ORM 模型
│   ├── assignment.py    # Assignment ORM 模型
│   └── annotation.py   # Annotation ORM 模型
├── services/
│   ├── assignment_service.py  # 分配查询 & 标注 upsert
│   ├── zip_service.py         # ZIP 流式打包
│   └── notification.py       # 内存 pub/sub（WebSocket 推送）
└── main.py              # FastAPI 应用工厂 & 启动入口
data/
├── images/              # 原始图片（平铺）
├── annotations/         # 标注 JSON（按学生姓名分目录）
└── exports/             # 临时导出文件
Dockerfile
docker-compose.yml
requirements.txt
```

---

## 快速启动

### 方式一：Docker Compose（推荐）

```bash
# 1. 克隆项目
git clone <repo_url> && cd <repo_dir>

# 2. 修改 JWT_SECRET（务必替换为强随机字符串）
#    编辑 docker-compose.yml 中的 JWT_SECRET 字段

# 3. 将原始图片放入 ./data/images/ 目录

# 4. 构建并启动
docker-compose up -d --build

# 5. 查看日志
docker-compose logs -f
```

服务启动后访问：
- API 文档：http://localhost:12010/docs
- 健康检查：http://localhost:12010/health

### 方式二：本地开发

```bash
# 安装依赖
pip install -r requirements.txt

# 设置环境变量
export JWT_SECRET="your-secret-key"
export DATA_DIR="./data"
export DATABASE_URL="sqlite+aiosqlite:///./data/app.db"

# 启动服务
python -m uvicorn app.main:app --host 0.0.0.0 --port 12010 --reload
```

---

## 环境变量说明

| 变量名 | 必填 | 默认值 | 说明 |
|--------|------|--------|------|
| `JWT_SECRET` | **是** | `change-me-...` | JWT 签名密钥，生产环境必须修改 |
| `DATA_DIR` | 否 | `/data` | 数据根目录 |
| `DATABASE_URL` | 否 | `sqlite+aiosqlite:////data/app.db` | 数据库连接串 |
| `TEACHER_API_KEY` | 否 | `""` | 教师端 API Key，留空不校验 |
| `JWT_EXPIRE_HOURS` | 否 | `8` | JWT 过期时间（小时） |

---

## 初始化学生数据

服务启动后，需要通过数据库脚本导入学生和图片数据。以下是示例 Python 脚本：

```python
"""
init_data.py — 初始化学生账号和图片分配
在容器内或宿主机上运行（确保 DATABASE_URL 指向正确的数据库）
"""
import asyncio
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.config import settings
from app.core.security import hash_password
from app.models import Student, Image, Assignment
from app.core.database import Base

DATABASE_URL = settings.DATABASE_URL
engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession)

# ── 学生名单（姓名: 初始密码） ──
STUDENTS = {
    "张三": "123456",
    "李四": "123456",
    "王五": "123456",
}

# ── 图片目录 ──
IMAGES_DIR = settings.images_dir


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        # 导入图片
        images = []
        for img_path in sorted(IMAGES_DIR.iterdir()):
            if img_path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}:
                img = Image(
                    filename=img_path.name,
                    original_path=str(img_path),
                    file_size=img_path.stat().st_size,
                )
                db.add(img)
                images.append(img)
        await db.flush()

        # 导入学生
        students = []
        for name, pwd in STUDENTS.items():
            stu = Student(name=name, password_hash=hash_password(pwd))
            db.add(stu)
            students.append(stu)
        await db.flush()

        # 均匀分配（轮询）
        for i, img in enumerate(images):
            stu = students[i % len(students)]
            db.add(Assignment(student_id=stu.id, image_id=img.id))

        await db.commit()
        print(f"导入 {len(images)} 张图片，{len(students)} 名学生，分配完成。")


asyncio.run(main())
```

---

## API 端点速览

### 学生端（需要 Bearer Token）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/login` | 登录，获取 JWT token |
| GET  | `/pull` | 下载任务包（ZIP） |
| POST | `/push` | 上传标注 JSON |
| GET  | `/status` | 查询自身任务进度 |
| GET  | `/health` | 健康检查 |

### 教师端（无需认证，可选 X-API-Key）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/overview` | 所有学生进度概览 |
| POST | `/reassign` | 改派图片 |
| GET  | `/api/students/{name}/status` | 查看指定学生状态 |
| GET  | `/api/images` | 所有图片分配情况 |
| GET  | `/api/export/annotations` | 导出全部标注 ZIP |
| GET  | `/api/stats` | 服务运行统计 |
| WS   | `/ws/overview` | 实时推送（WebSocket） |

---

## 文件系统布局

```
/data
├── images/          # 原始图片（平铺存放）
│   ├── cat.jpg
│   └── dog.png
├── annotations/     # 标注 JSON（按学生目录）
│   ├── 张三/
│   │   └── cat.json
│   └── 李四/
│       └── dog.json
└── exports/         # 临时导出（ZIP 等）
```

---

## 注意事项

1. **生产部署前务必修改** `JWT_SECRET` 为强随机字符串（≥32 字节）。
2. **数据持久化**：`./data` 目录通过 Docker volume 挂载，删除容器不会丢失数据。
3. **改派操作**不会自动迁移已上传的标注文件，教师需手动处理旧标注目录。
4. **并发安全**：单 Worker 模式下 SQLite 足够应对 15 名学生的并发场景。
5. **日志**：服务日志输出到 stdout，通过 `docker-compose logs -f` 实时查看。
