# ImageLabelTS 服务端

## 技术栈

- **后端**：Python 3.8+，Flask
- **数据库**：PostgreSQL（推荐 12+）
- **认证**：bcrypt + 随机 Token
- **并发控制**：数据库可重复读隔离级别 + 文件锁（`fcntl`）
- **其他**：`psycopg2`（连接池）、`werkzeug`、`python-dotenv`（可选）

## 环境准备

### 1. 安装 PostgreSQL

确保 PostgreSQL 已安装并运行。创建数据库和用户（示例）：

```sql
CREATE USER teacher WITH PASSWORD 'secret';
CREATE DATABASE teacher_db OWNER teacher;
```

### 2. 克隆项目

```bash
git clone <repository-url>
cd teacher
```

### 3. 创建 Python 虚拟环境

```bash
python3 -m venv venv
source venv/bin/activate   # Linux/Mac
# 或 venv\Scripts\activate  # Windows
```

### 4. 安装依赖

项目依赖如下：
```
Flask
bcrypt
psycopg2-binary
gunicorn
```

安装：
```bash
pip install -r requirements.txt
```

## 配置

项目通过环境变量配置数据库连接，可创建 `.env` 文件或在系统环境中设置：

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `DB_HOST` | `localhost` | 数据库主机 |
| `DB_PORT` | `5432` | 数据库端口 |
| `DB_NAME` | `teacher_db` | 数据库名称 |
| `DB_USER` | `teacher` | 数据库用户 |
| `DB_PASSWORD` | `secret` | 数据库密码 |
| `MAINTENANCE_DB` | `postgres` | 用于创建目标数据库的维护数据库（仅 `init.py` 使用） |

---

## 数据文件准备

项目根目录下需要准备以下文件：

### `students.json`

包含所有学生信息，格式为 JSON 数组，每个元素必须有 `name` 和 `password_hash` 字段：

```json
[
  {
    "name": "张三",
    "password_hash": "$2b$12$..."   // bcrypt 哈希值
  },
  {
    "name": "李四",
    "password_hash": "$2b$12$..."
  }
]
```

> **生成密码哈希**：可使用 Python 交互式生成，例如：
> ```python
> import bcrypt
> password = "123456"
> hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
> print(hashed.decode('utf-8'))
> ```

### `Images/` 目录

存放所有待标注的图片文件（支持 `.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp`, `.webp`）。

### 自动生成的文件

- `assignments.json`：由 `init.py` 生成，记录每个学生分配到的图片列表。
- `results/`：上传目录，按学生名存放标注文件，服务器会自动创建。


## 初始化新批次

使用 `init.py` 脚本完成图片分配、数据库清空和表结构创建。

### 基本用法

```bash
python init.py --force --init-schema
```

- `--force`：跳过确认提示，直接执行清空操作。
- `--init-schema`：自动创建缺失的数据表（使用内置 DDL）。

**执行过程：**
1. 确保目标数据库存在（若不存在则创建）。
2. 创建所有必要的表（如已存在则跳过）。
3. 加载 `students.json` 中的学生列表，扫描 `Images/` 中的图片。
4. 随机打乱图片后均匀分配给每位学生。
5. 将分配结果写入 `assignments.json`。
6. 清空数据库中的业务表（`students`, `tokens`, `assignments`, `uploads`）。
7. 清空 `results/` 上传目录（除非指定 `--keep-uploads`）。

> **注意**：此操作会删除所有旧数据（包括已有标注），请谨慎使用。

---

## 启动服务器

```bash
python server.py
```

默认监听 `0.0.0.0:12010`（可在 `app.run()` 中修改）。

服务器启动时会自动执行以下操作：
- 初始化数据库表结构（若未创建）。
- 同步 `students.json` 和 `assignments.json` 到数据库（若已初始化，则跳过，仅同步数据）。
- 清理残留的临时文件（`.tmp_*.json`）。

**建议使用生产级 WSGI 服务器**（如 `gunicorn`）：
```bash
gunicorn -w 4 -b 0.0.0.0:12010 server:app
```

---

## API 文档

所有接口返回 JSON，错误时包含 `status: "error"` 和 `message` 字段。

### 1. 学生登录

**POST** `/login`

请求体（JSON）：
```json
{
  "name": "张三",
  "password": "123456"
}
```

成功响应：
```json
{
  "status": "ok",
  "token": "随机生成的Bearer令牌",
  "task_count": 10
}
```

后续请求需在 `Authorization` 头中携带 `Bearer <token>`。



### 2. 拉取任务包

**GET** `/pull`

需要认证。返回一个 ZIP 文件，包含该学生的所有图片和已上传的 JSON 标注文件（若存在）。

响应为二进制流，文件名格式为 `<学生名>_task.zip`。



### 3. 上传标注文件

**POST** `/push`

需要认证。表单字段：
- `file`：要上传的 JSON 文件，文件名必须与图片基名一致（例如 `image1.json` 对应 `image1.jpg`）。

文件内容必须是有效的 JSON，大小限制为 2 MB。

成功响应：
```json
{
  "status": "ok",
  "message": "上传成功"
}
```



### 4. 查询个人任务状态

**GET** `/status`

需要认证。返回当前学生的任务完成详情。

响应示例：
```json
{
  "uploaded": 5,
  "unuploaded": 5,
  "total": 10,
  "assigned_images": ["img1.jpg", "img2.jpg", ...],
  "uploaded_details": {
    "img1": {
      "hash": "md5哈希",
      "last_upload": "2026-07-25T12:34:56+00:00"
    }
  }
}
```



### 5. 教师概览

**GET** `/api/overview`

无需认证（可根据需要自行添加安全措施）。返回所有学生的任务统计。

响应结构：
```json
{
  "students": [
    {
      "name": "张三",
      "total": 10,
      "uploaded": 3,
      "images": ["img1.jpg", ...],
      "uploaded_images": ["img1", ...],
      "last_push": "2026-07-25T12:34:56+00:00"
    }
  ],
  "total_overall": {
    "total": 100,
    "uploaded": 30
  }
}
```



## 目录结构

```
/teacher
├── init.py               # 初始化脚本（分配 + 清空 + 建表）
├── server.py             # Flask 主程序
├── students.json         # 学生账号密码（需手动准备）
├── assignments.json      # 分配结果（由 init.py 生成）
├── Images/               # 存放图片文件
├── results/              # 上传的标注文件（按学生子目录存放）
├── .init.lock            # 启动锁文件（防止并发初始化）
└── README.md
```