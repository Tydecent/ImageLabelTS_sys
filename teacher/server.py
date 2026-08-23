#!/usr/bin/env python3
"""
教师端标注任务服务器
"""

import os
import json
import hashlib
import secrets
import fcntl
import time
import logging
import logging.handlers
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from io import BytesIO
from contextlib import contextmanager

import bcrypt
from flask import Flask, request, jsonify, g, send_file, abort
from werkzeug.utils import secure_filename
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor
from psycopg2 import sql
from functools import wraps
from psycopg2.errors import SerializationFailure
import psycopg2.extensions
import uuid

# ---------------------------------------------------------------------------
# 配置（通过环境变量或默认值）
# ---------------------------------------------------------------------------
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "teacher_db")
DB_USER = os.getenv("DB_USER", "teacher")
DB_PASSWORD = os.getenv("DB_PASSWORD", "secret")
DATABASE_URI = f"dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD} host={DB_HOST} port={DB_PORT}"

BASE_DIR = Path(__file__).resolve().parent
IMAGES_DIR = BASE_DIR / "Images"
UPLOADS_DIR = BASE_DIR / "results"
STUDENTS_FILE = BASE_DIR / "students.json"
ASSIGNMENTS_FILE = BASE_DIR / "assignments.json"
LOGS_DIR = BASE_DIR / "logs"

MAX_CONTENT_LENGTH = 2 * 1024 * 1024
ALLOWED_EXTENSIONS = {".json"}

# 日志配置
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024)))  # 默认 10MB
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "10"))  # 保留 10 个备份文件

pool = None

# ---------------------------------------------------------------------------
# 日志配置
# ---------------------------------------------------------------------------
def setup_logging(app):
    """配置应用日志，写入文件（RotatingFileHandler）并输出到控制台。

    使用文件日志可以确保在 gunicorn 多 worker 进程下，每个 worker 都能
    将日志写入同一组文件，避免仅 Master 进程有日志的问题。
    """
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    # 通用格式：时间、级别、进程/线程、日志器名、消息
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(process)d:%(thread)d] %(name)s - %(message)s"
    )
    console_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
    )

    # 应用日志（业务逻辑、错误等）
    app_log_path = LOGS_DIR / "app.log"
    app_handler = logging.handlers.RotatingFileHandler(
        app_log_path,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    app_handler.setFormatter(file_formatter)
    app_handler.setLevel(LOG_LEVEL)

    # 访问日志（记录每个 HTTP 请求）
    access_log_path = LOGS_DIR / "access.log"
    access_handler = logging.handlers.RotatingFileHandler(
        access_log_path,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    access_handler.setFormatter(file_formatter)
    access_handler.setLevel(logging.INFO)

    # 控制台输出（便于开发调试）
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(LOG_LEVEL)

    # 配置 Flask 应用日志器
    app.logger.setLevel(LOG_LEVEL)
    app.logger.handlers.clear()
    app.logger.addHandler(app_handler)
    app.logger.addHandler(console_handler)
    app.logger.propagate = False

    # 配置 werkzeug 访问日志（gunicorn 下默认不输出，这里显式接管）
    werkzeug_logger = logging.getLogger("werkzeug")
    werkzeug_logger.setLevel(logging.INFO)
    werkzeug_logger.handlers.clear()
    werkzeug_logger.addHandler(access_handler)
    werkzeug_logger.addHandler(console_handler)
    werkzeug_logger.propagate = False

    # 配置 gunicorn 错误日志（若在 gunicorn 下运行）
    gunicorn_error_logger = logging.getLogger("gunicorn.error")
    gunicorn_error_logger.setLevel(LOG_LEVEL)
    gunicorn_error_logger.handlers.clear()
    gunicorn_error_logger.addHandler(app_handler)
    gunicorn_error_logger.addHandler(console_handler)
    gunicorn_error_logger.propagate = False

    # 配置 gunicorn 访问日志（若在 gunicorn 下运行）
    gunicorn_access_logger = logging.getLogger("gunicorn.access")
    gunicorn_access_logger.setLevel(logging.INFO)
    gunicorn_access_logger.handlers.clear()
    gunicorn_access_logger.addHandler(access_handler)
    gunicorn_access_logger.addHandler(console_handler)
    gunicorn_access_logger.propagate = False

    app.logger.info(
        f"日志系统初始化完成：级别={LOG_LEVEL}，应用日志={app_log_path}，"
        f"访问日志={access_log_path}"
    )

# ---------------------------------------------------------------------------
# 初始化辅助函数
# ---------------------------------------------------------------------------
def load_json_file(path, description):
    if not path.exists():
        raise SystemExit(f"致命错误：缺少文件 {path} ({description})")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as e:
        raise SystemExit(f"致命错误：解析 {path} 失败 ({description}): {e}")

def init_db_pool():
    global pool
    try:
        pool = ThreadedConnectionPool(
            minconn=2,
            maxconn=10,
            dsn=DATABASE_URI,
            cursor_factory=RealDictCursor,
        )
    except Exception as e:
        raise SystemExit(f"无法连接数据库: {e}")

@contextmanager
def get_db_connection():
    conn = pool.getconn()
    try:
        yield conn
    finally:
        pool.putconn(conn)

def init_db_schema(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS students (
                name VARCHAR(255) PRIMARY KEY,
                password_hash VARCHAR(255) NOT NULL
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tokens (
                token VARCHAR(255) PRIMARY KEY,
                name VARCHAR(255) NOT NULL UNIQUE REFERENCES students(name) ON DELETE CASCADE,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS assignments (
                name VARCHAR(255) NOT NULL REFERENCES students(name) ON DELETE CASCADE,
                image_filename VARCHAR(255) NOT NULL,
                PRIMARY KEY (name, image_filename)
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS uploads (
                name VARCHAR(255) NOT NULL REFERENCES students(name) ON DELETE CASCADE,
                image_basename VARCHAR(255) NOT NULL,
                hash VARCHAR(32) NOT NULL,
                last_upload TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (name, image_basename)
            );
        """)
    conn.commit()

def sync_students_and_assignments(conn):
    students_data = load_json_file(STUDENTS_FILE, "学生列表")
    assignments_data = load_json_file(ASSIGNMENTS_FILE, "任务分配")

    with conn.cursor() as cur:
        for stu in students_data:
            cur.execute("""
                INSERT INTO students (name, password_hash)
                VALUES (%(name)s, %(password_hash)s)
                ON CONFLICT (name) DO UPDATE SET password_hash = EXCLUDED.password_hash;
            """, stu)

        cur.execute("DELETE FROM assignments;")
        for student_name, images in assignments_data.items():
            for img in images:
                cur.execute(
                    "INSERT INTO assignments (name, image_filename) VALUES (%s, %s);",
                    (student_name, img)
                )
    conn.commit()

import time
from functools import wraps
from psycopg2.errors import SerializationFailure

def retry_on_serialization(max_retries=3):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return f(*args, **kwargs)
                except SerializationFailure as e:
                    if attempt == max_retries - 1:
                        raise
                    time.sleep(0.1 * (2 ** attempt))
                    # 视图已经回滚，无需额外操作，继续重试
                    continue
            return None
        return wrapper
    return decorator

# ---------------------------------------------------------------------------
# Flask 应用
# ---------------------------------------------------------------------------
def create_app():
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

    # 初始化日志系统（必须在任何日志调用之前）
    setup_logging(app)

    init_db_pool()

    # ---------- 多进程安全的初始化（文件锁 + 一次性标记） ----------
    init_lock_path = BASE_DIR / ".init.lock"
    with open(init_lock_path, "w") as lock_fd:
        fcntl.lockf(lock_fd, fcntl.LOCK_EX)
        try:
            with get_db_connection() as conn:
                init_db_schema(conn)
                cur = conn.cursor()
                cur.execute(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_name = 'init_completed';"
                )
                if cur.fetchone() is None:
                    # 使用事务原子化执行同步 + 创建标记表
                    with conn:
                        sync_students_and_assignments(conn)  # 内部包含 commit
                        cur.execute("CREATE TABLE init_completed (done BOOLEAN);")
                        cur.execute("INSERT INTO init_completed VALUES (TRUE);")
                        conn.commit()  # 确保全部成功
                else:
                    # 已初始化，但清理残留临时文件（每次启动执行）
                    if UPLOADS_DIR.exists():
                        for tmp_file in UPLOADS_DIR.glob("**/.tmp_*.json"):
                            try:
                                tmp_file.unlink()
                                app.logger.info(f"清理残留临时文件: {tmp_file}")
                            except Exception as e:
                                app.logger.warning(f"清理临时文件失败: {tmp_file}, {e}")

        except Exception as e:
            app.logger.critical(f"初始化致命错误，服务启动失败: {e}")
            # 强制退出，避免处于半初始化状态运行
            os._exit(1)  # 或 raise SystemExit
        finally:
            fcntl.lockf(lock_fd, fcntl.LOCK_UN)

    # ---------- 请求钩子 ----------
    @app.before_request
    def before_request():
        g.db_conn = pool.getconn()
        g.request_start_time = time.time()
        g.student_name = None

    @app.teardown_request
    def teardown_request(exc=None):
        conn = g.pop("db_conn", None)
        if conn is not None:
            pool.putconn(conn)

    # ---------- 访问日志（记录每个请求的详细信息） ----------
    @app.after_request
    def log_request(response):
        duration_ms = (time.time() - g.get("request_start_time", time.time())) * 1000
        student = g.get("student_name", None)
        access_logger = logging.getLogger("werkzeug")
        access_logger.info(
            f"{request.remote_addr} - \"{request.method} {request.path}\" "
            f"{response.status_code} {duration_ms:.1f}ms "
            f"student={student or '-'} "
            f"ua={request.user_agent.string[:80] if request.user_agent else '-'}"
        )
        return response

    # ---------- 辅助装饰器 ----------
    def login_required(f):
        from functools import wraps
        @wraps(f)
        def decorated(*args, **kwargs):
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                abort(401, description="缺少或无效的令牌")
            token = auth_header[7:]
            cur = g.db_conn.cursor()
            cur.execute("SELECT name FROM tokens WHERE token = %s;", (token,))
            row = cur.fetchone()
            if row is None:
                abort(401, description="无效的令牌")
            g.student_name = row["name"]
            return f(*args, **kwargs)
        return decorated

    # -----------------------------------------------------------------------
    # 1. 学生登录（修复事务处理）
    # -----------------------------------------------------------------------
    @app.route("/login", methods=["POST"])
    def login():
        data = request.get_json(silent=True)
        if not data or "name" not in data or "password" not in data:
            app.logger.warning(f"登录失败：请求体缺少 name/password 字段，IP={request.remote_addr}")
            abort(400, description="请求体必须包含 name 和 password 字段")

        student_name = data["name"]
        password = data["password"]

        cur = g.db_conn.cursor()
        cur.execute("SELECT password_hash FROM students WHERE name = %s;", (student_name,))
        row = cur.fetchone()
        if row is None:
            app.logger.warning(f"登录失败：学生 '{student_name}' 不存在，IP={request.remote_addr}")
            abort(401, description="姓名或密码错误")

        if not bcrypt.checkpw(password.encode("utf-8"), row["password_hash"].encode("utf-8")):
            app.logger.warning(f"登录失败：学生 '{student_name}' 密码错误，IP={request.remote_addr}")
            abort(401, description="姓名或密码错误")

        new_token = secrets.token_urlsafe(32)
        
        with g.db_conn:
            cur.execute("""
                INSERT INTO tokens (token, name) 
                VALUES (%s, %s)
                ON CONFLICT (name) DO UPDATE SET token = EXCLUDED.token;
            """, (new_token, student_name))

        cur.execute("SELECT COUNT(*) AS cnt FROM assignments WHERE name = %s;", (student_name,))
        task_count = cur.fetchone()["cnt"]

        app.logger.info(f"学生 '{student_name}' 登录成功，任务数={task_count}，IP={request.remote_addr}")

        return jsonify({
            "status": "ok",
            "token": new_token,
            "task_count": task_count,
        })

    # -----------------------------------------------------------------------
    # 2. 拉取任务包（显式可重复读事务）
    # -----------------------------------------------------------------------
    @app.route("/pull", methods=["GET"])
    @login_required
    @retry_on_serialization(max_retries=3)
    def pull():
        student = g.student_name
        conn = g.db_conn

        # 清除任何残留事务，确保连接处于空闲状态
        conn.rollback()
        # 设置事务隔离级别为 REPEATABLE READ（必须在事务外执行）
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_REPEATABLE_READ)
        cur = conn.cursor()

        try:
            # 1. 查询分配图片列表
            cur.execute("SELECT image_filename FROM assignments WHERE name = %s;", (student,))
            assignments = [row["image_filename"] for row in cur.fetchall()]
            if not assignments:
                conn.rollback()
                app.logger.warning(f"学生 '{student}' 拉取任务失败：暂无分配图片")
                abort(404, description="该学生暂无分配图片")

            # 2. 查询已上传的标注文件基名
            cur.execute("SELECT image_basename FROM uploads WHERE name = %s;", (student,))
            uploaded_set = {row["image_basename"] for row in cur.fetchall()}
            conn.commit()   # 只读事务提交，释放快照
        except Exception:
            conn.rollback()
            raise
        finally:
            # 恢复默认隔离级别（若连接会被复用），避免影响后续请求
            # 若每个请求使用独立连接，可省略此步骤
            conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_READ_COMMITTED)

        # 3. 内存打包（无数据库操作）
        buffer = BytesIO()
        packed_images = 0
        packed_annotations = 0
        with ZipFile(buffer, "w", ZIP_DEFLATED) as zf:
            for img_filename in assignments:
                img_path = IMAGES_DIR / img_filename
                if img_path.is_file():
                    zf.write(img_path, img_filename)
                    packed_images += 1
                else:
                    app.logger.warning(f"学生 '{student}' 拉取任务：图片缺失 {img_path}")

                base = Path(img_filename).stem
                if base in uploaded_set:
                    json_path = UPLOADS_DIR / student / f"{base}.json"
                    if json_path.is_file():
                        zf.write(json_path, f"{base}.json")
                        packed_annotations += 1
                    else:
                        app.logger.warning(f"学生 '{student}' 拉取任务：标注文件缺失 {json_path}")

        buffer.seek(0)
        app.logger.info(
            f"学生 '{student}' 拉取任务包成功：图片={packed_images}，"
            f"标注={packed_annotations}，总任务={len(assignments)}"
        )
        return send_file(
            buffer,
            mimetype="application/zip",
            as_attachment=True,
            download_name=f"{student}_task.zip"
        )

    # -----------------------------------------------------------------------
    # 3. 上传标注文件（修复：先写数据库，后写文件）
    # -----------------------------------------------------------------------
    @app.route("/push", methods=["POST"])
    @login_required
    @retry_on_serialization(max_retries=3)
    def push():
        student = g.student_name
        if "file" not in request.files:
            app.logger.warning(f"学生 '{student}' 上传失败：缺少文件字段 'file'")
            abort(400, description="缺少文件字段 'file'")

        file = request.files["file"]
        if not file.filename:
            app.logger.warning(f"学生 '{student}' 上传失败：未选择文件")
            abort(400, description="未选择文件")
        if not file.filename.lower().endswith(".json"):
            app.logger.warning(f"学生 '{student}' 上传失败：非 JSON 文件 '{file.filename}'")
            abort(400, description="只允许上传 .json 文件")

        original_name = Path(file.filename).stem
        if not original_name:
            app.logger.warning(f"学生 '{student}' 上传失败：无效的文件名")
            abort(400, description="无效的文件名")
        safe_basename = secure_filename(original_name)
        if safe_basename != original_name:
            app.logger.warning(f"学生 '{student}' 上传失败：文件名含非法字符 '{original_name}'")
            abort(400, description="文件名包含非法字符")

        # 读取并校验内容
        file_content = file.read()
        try:
            json.loads(file_content)
        except json.JSONDecodeError:
            app.logger.warning(f"学生 '{student}' 上传失败：'{safe_basename}' 内容不是有效 JSON")
            abort(400, description="文件内容不是有效的 JSON")
        file_hash = hashlib.md5(file_content).hexdigest()

        student_dir = UPLOADS_DIR / student
        student_dir.mkdir(parents=True, exist_ok=True)

        tmp_path = student_dir / f".tmp_{safe_basename}_{uuid.uuid4().hex}.json"
        target_path = student_dir / f"{safe_basename}.json"
        lock_path = student_dir / f"{safe_basename}.lock"

        # 1. 写入临时文件（锁外）
        try:
            with open(tmp_path, "wb") as tmp_f:
                tmp_f.write(file_content)
                tmp_f.flush()
                os.fsync(tmp_f.fileno())
        except Exception as e:
            if tmp_path.exists():
                tmp_path.unlink()
            app.logger.error(f"学生 '{student}' 上传失败：临时文件写入错误 {e}")
            abort(500, description=f"临时文件写入失败: {e}")

        # 2. 获取文件锁
        with open(lock_path, "w") as lock_fd:
            fcntl.lockf(lock_fd, fcntl.LOCK_EX)
            try:
                old_content = None
                if target_path.exists():
                    with open(target_path, "rb") as f:
                        old_content = f.read()

                # 在锁内再次验证任务归属
                cur = g.db_conn.cursor()
                cur.execute(
                    "SELECT 1 FROM assignments WHERE name = %s AND image_filename LIKE %s;",
                    (student, f"{safe_basename}.%")
                )
                if cur.fetchone() is None:
                    if tmp_path.exists():
                        tmp_path.unlink()
                    app.logger.warning(
                        f"学生 '{student}' 上传失败：文件名 '{safe_basename}' 与该学生任务不匹配"
                    )
                    abort(403, description=f"文件名 '{safe_basename}' 与该学生任务不匹配")

                # 3. 原子替换目标文件
                try:
                    os.replace(tmp_path, target_path)
                except Exception as replace_err:
                    if tmp_path.exists():
                        tmp_path.unlink()
                    app.logger.error(f"学生 '{student}' 上传失败：文件替换错误 {replace_err}")
                    abort(500, description=f"文件替换失败: {replace_err}")

                # 4. 数据库操作（先清除残留事务，设置隔离级别）
                conn = g.db_conn
                conn.rollback()  # 清除可能残留的事务
                conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_REPEATABLE_READ)
                try:
                    cur = conn.cursor()  # 重新获取游标（或继续使用已有，但确保隔离级别已设置）
                    # 直接执行插入（无需显式 BEGIN，因为隔离级别已设置，且 autocommit=False）
                    cur.execute("""
                        INSERT INTO uploads (name, image_basename, hash, last_upload)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (name, image_basename)
                        DO UPDATE SET hash = EXCLUDED.hash, last_upload = EXCLUDED.last_upload;
                    """, (student, safe_basename, file_hash, datetime.now(timezone.utc)))
                    conn.commit()
                except Exception as db_err:
                    conn.rollback()
                    # 数据库失败，回滚文件到旧状态
                    if old_content is not None:
                        with open(target_path, "wb") as f:
                            f.write(old_content)
                    else:
                        if target_path.exists():
                            target_path.unlink()
                    if tmp_path.exists():
                        tmp_path.unlink()
                    app.logger.error(
                        f"学生 '{student}' 上传失败：数据库写入错误 {db_err}，已回滚文件"
                    )
                    raise
                finally:
                    # 恢复默认隔离级别
                    conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_READ_COMMITTED)

            except Exception:
                if tmp_path.exists():
                    tmp_path.unlink()
                raise
            finally:
                fcntl.lockf(lock_fd, fcntl.LOCK_UN)

        app.logger.info(
            f"学生 '{student}' 上传成功：文件 '{safe_basename}.json'，"
            f"大小={len(file_content)}B，MD5={file_hash}"
        )
        return jsonify({"status": "ok", "message": "上传成功"})

    # -----------------------------------------------------------------------
    # 4. 查询任务状态（显式可重复读事务）
    # -----------------------------------------------------------------------
    @app.route("/status", methods=["GET"])
    @login_required
    def status():
        student = g.student_name
        conn = g.db_conn

        conn.rollback()
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_REPEATABLE_READ)
        cur = conn.cursor()

        try:
            cur.execute("SELECT image_filename FROM assignments WHERE name = %s;", (student,))
            assigned_rows = cur.fetchall()
            assigned_images = [r["image_filename"] for r in assigned_rows]

            cur.execute("SELECT image_basename, hash, last_upload FROM uploads WHERE name = %s;", (student,))
            upload_rows = cur.fetchall()
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_READ_COMMITTED)

        uploaded_map = {r["image_basename"]: r for r in upload_rows}
        uploaded_count = 0
        uploaded_details = {}
        for img in assigned_images:
            base = Path(img).stem
            if base in uploaded_map:
                uploaded_count += 1
                last_up = uploaded_map[base]["last_upload"]
                if isinstance(last_up, datetime):
                    last_up_str = last_up.isoformat()
                else:
                    last_up_str = str(last_up)
                uploaded_details[base] = {
                    "hash": uploaded_map[base]["hash"],
                    "last_upload": last_up_str,
                }

        total = len(assigned_images)
        app.logger.info(
            f"学生 '{student}' 查询状态：已上传={uploaded_count}，"
            f"未上传={total - uploaded_count}，总任务={total}"
        )
        return jsonify({
            "uploaded": uploaded_count,
            "unuploaded": total - uploaded_count,
            "total": total,
            "assigned_images": assigned_images,
            "uploaded_details": uploaded_details,
        })

    # -----------------------------------------------------------------------
    # 5. 教师端概览（显式可重复读事务）
    # -----------------------------------------------------------------------
    @app.route("/api/overview", methods=["GET"])
    def overview():
        conn = g.db_conn

        conn.rollback()
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_REPEATABLE_READ)
        cur = conn.cursor()

        try:
            cur.execute("SELECT name FROM students;")
            all_students = [row["name"] for row in cur.fetchall()]

            result_students = []
            total_all = 0
            uploaded_all = 0

            for stu in all_students:
                cur.execute("SELECT image_filename FROM assignments WHERE name = %s;", (stu,))
                assigned = [r["image_filename"] for r in cur.fetchall()]
                total_cnt = len(assigned)

                cur.execute("SELECT image_basename, last_upload FROM uploads WHERE name = %s;", (stu,))
                upload_rows = {r["image_basename"]: r["last_upload"] for r in cur.fetchall()}

                uploaded_basenames = []
                last_push = None
                for img in assigned:
                    base = Path(img).stem
                    if base in upload_rows:
                        uploaded_basenames.append(base)
                        ts = upload_rows[base]
                        if last_push is None or (ts is not None and ts > last_push):
                            last_push = ts

                total_all += total_cnt
                uploaded_all += len(uploaded_basenames)

                result_students.append({
                    "name": stu,
                    "total": total_cnt,
                    "uploaded": len(uploaded_basenames),
                    "images": assigned,
                    "uploaded_images": uploaded_basenames,
                    "last_push": last_push.isoformat() if isinstance(last_push, datetime) else None,
                })

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_READ_COMMITTED)

        app.logger.info(
            f"教师端概览查询：学生数={len(result_students)}，"
            f"总任务={total_all}，已上传={uploaded_all}"
        )
        return jsonify({
            "students": result_students,
            "total_overall": {
                "total": total_all,
                "uploaded": uploaded_all,
            }
        })

    # -----------------------------------------------------------------------
    # 错误处理
    # -----------------------------------------------------------------------
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"status": "error", "message": e.description}), 400

    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify({"status": "error", "message": e.description}), 401

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify({"status": "error", "message": e.description}), 403

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"status": "error", "message": e.description}), 404

    @app.errorhandler(500)
    def internal_error(e):
        app.logger.error(f"服务器内部错误: {e}")
        return jsonify({"status": "error", "message": "服务器内部错误"}), 500

    return app

# ---------------------------------------------------------------------------
# 启动入口
# ---------------------------------------------------------------------------
app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=12010, debug=False)