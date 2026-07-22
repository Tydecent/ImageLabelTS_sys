#!/usr/bin/env python3
"""
新批次初始化脚本（支持自动建库和建表）

用法：
  python init_new_batch.py --force --init-schema   # 强制清空数据，缺失表则自动创建
"""

import os
import sys
import json
import random
import shutil
import argparse
from pathlib import Path
from typing import List, Dict

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import OperationalError, ProgrammingError

# ---------- 配置 ----------
BASE_DIR = Path(__file__).resolve().parent
IMAGES_DIR = BASE_DIR / "Images"
STUDENTS_FILE = BASE_DIR / "students.json"
ASSIGNMENTS_FILE = BASE_DIR / "assignments.json"
UPLOADS_DIR = BASE_DIR / "results"

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "teacher_db")
DB_USER = os.getenv("DB_USER", "teacher")
DB_PASSWORD = os.getenv("DB_PASSWORD", "secret")
MAINTENANCE_DB = os.getenv("MAINTENANCE_DB", "postgres")

IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}

# 建表 DDL（请根据你的实际表结构修改！）
CREATE_TABLES_SQL = """
-- 学生表（记录学生姓名和密码哈希）
CREATE TABLE IF NOT EXISTS students (
    name TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL
);

-- 令牌表（登录令牌管理）
CREATE TABLE IF NOT EXISTS tokens (
    token TEXT PRIMARY KEY,
    student_name TEXT REFERENCES students(name) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT now()
);

-- 作业分配表（学生-图片映射）
CREATE TABLE IF NOT EXISTS assignments (
    student_name TEXT REFERENCES students(name) ON DELETE CASCADE,
    image_name TEXT NOT NULL,
    PRIMARY KEY (student_name, image_name)
);

-- 上传记录表（标注结果）
CREATE TABLE IF NOT EXISTS uploads (
    id SERIAL PRIMARY KEY,
    student_name TEXT REFERENCES students(name) ON DELETE CASCADE,
    image_name TEXT NOT NULL,
    result JSONB,
    uploaded_at TIMESTAMP DEFAULT now()
);

-- 初始化完成标记（供教学端使用）
CREATE TABLE IF NOT EXISTS init_completed (
    initialized BOOLEAN DEFAULT false
);
"""


# ---------- 工具函数 ----------
def load_students(path: Path) -> list:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("students.json 必须是一个数组")
    names = [item['name'] for item in data if 'name' in item]
    if not names:
        raise ValueError("学生列表为空")
    return names


def collect_images(image_dir: Path) -> list:
    if not image_dir.is_dir():
        raise FileNotFoundError(f"图片目录不存在: {image_dir}")
    files = []
    for entry in image_dir.iterdir():
        if entry.is_file() and entry.suffix.lower() in IMAGE_EXTENSIONS:
            files.append(entry.name)
    return files


def distribute_images(images: list, students: list) -> Dict[str, list]:
    random.shuffle(images)
    n_students = len(students)
    n_images = len(images)
    base, remainder = divmod(n_images, n_students)
    assignment = {name: [] for name in students}
    idx = 0
    for i, name in enumerate(students):
        count = base + (1 if i < remainder else 0)
        assignment[name] = images[idx:idx + count]
        idx += count
    return assignment


def get_db_connection(dbname=None):
    if dbname is None:
        dbname = DB_NAME
    dsn = f"dbname={dbname} user={DB_USER} password={DB_PASSWORD} host={DB_HOST} port={DB_PORT}"
    return psycopg2.connect(dsn, cursor_factory=RealDictCursor)


def ensure_database():
    """确保目标数据库存在，否则创建"""
    try:
        conn = get_db_connection()
        conn.close()
        print(f"数据库 '{DB_NAME}' 已存在。")
    except OperationalError as e:
        if "does not exist" in str(e) or getattr(e, 'pgcode', None) == '3D000':
            print(f"数据库 '{DB_NAME}' 不存在，创建中...")
            conn = get_db_connection(dbname=MAINTENANCE_DB)
            conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
            with conn.cursor() as cur:
                cur.execute(f'CREATE DATABASE "{DB_NAME}"')
            conn.close()
            print("数据库创建成功。")
        else:
            raise


def init_schema():
    """创建缺失的表结构（如果表已存在则跳过）"""
    ensure_database()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(CREATE_TABLES_SQL)
        conn.commit()
        print("表结构检查/创建完成。")
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


def clear_database():
    """清空所有业务表数据，保留表结构"""
    ensure_database()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 检查核心表是否存在
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'students'
                )
            """)
            table_exists = cur.fetchone()['exists']
            if not table_exists:
                raise ProgrammingError("核心表 'students' 不存在")

            cur.execute("TRUNCATE TABLE students, tokens, assignments, uploads, init_completed CASCADE;")
        conn.commit()
        print("数据库已清空。")
    except ProgrammingError as e:
        if "does not exist" in str(e):
            raise RuntimeError("数据库表结构缺失，请使用 --init-schema 参数创建表") from e
        raise
    finally:
        conn.close()


def clear_uploads():
    if UPLOADS_DIR.exists():
        shutil.rmtree(UPLOADS_DIR)
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        print("上传目录已清理。")


def main():
    parser = argparse.ArgumentParser(description="初始化新批次数据")
    parser.add_argument("--force", action="store_true",
                        help="跳过确认，直接执行清空操作")
    parser.add_argument("--keep-uploads", action="store_true",
                        help="保留上传目录（默认为清空）")
    parser.add_argument("--init-schema", action="store_true",
                        help="自动创建缺失的表结构（使用内置 DDL）")
    args = parser.parse_args()

    # 如果需要初始化表结构
    if args.init_schema:
        try:
            init_schema()
        except Exception as e:
            print(f"✗ 初始化表结构失败: {e}")
            sys.exit(1)

    # 加载学生
    try:
        students = load_students(STUDENTS_FILE)
        print(f"✓ 已加载 {len(students)} 名学生")
    except Exception as e:
        print(f"✗ 加载学生数据失败: {e}")
        sys.exit(1)

    # 扫描图片
    try:
        images = collect_images(IMAGES_DIR)
        print(f"✓ 找到 {len(images)} 张图片")
    except Exception as e:
        print(f"✗ 扫描图片失败: {e}")
        sys.exit(1)

    # 分配
    assignment = distribute_images(images, students)
    with open(ASSIGNMENTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(assignment, f, ensure_ascii=False, indent=2)
    print("✓ 分配结果已写入 assignments.json")

    print("\n分配明细：")
    for name, imgs in assignment.items():
        print(f"  {name}: {len(imgs)} 张")

    if not args.force:
        confirm = input("\n⚠️  此操作将清空数据库和上传目录中的全部旧数据，是否继续？(y/N): ")
        if confirm.strip().lower() != 'y':
            print("已取消。")
            sys.exit(0)

    # 清空数据库
    try:
        clear_database()
    except Exception as e:
        print(f"✗ 清空数据库失败: {e}")
        sys.exit(1)

    if not args.keep_uploads:
        try:
            clear_uploads()
        except Exception as e:
            print(f"✗ 清理上传目录失败: {e}")
            sys.exit(1)

    print("\n初始化完成！请重启教学端服务使新配置生效。")


if __name__ == "__main__":
    main()