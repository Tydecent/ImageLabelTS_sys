#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
学生端命令行工具 – 图片标注任务客户端
用于与教师端 Flask 服务器交互，完成登录、拉取任务、上传 JSON 标注文件。
所有学生数据保存在当前目录下的 .annotator_name 和 ./workshop 文件夹中。
"""

import os
import zipfile
import requests
import click
import json
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
import sys
import threading

# ==================== 配置区 ====================
# 教师服务器的根地址，请根据实际情况修改 IP 和端口
# 加载 config.json 文件
with open('config.json', 'r', encoding='utf-8') as config_file:
    config = json.load(config_file)
    SERVER_URL = config.get("server_url", "http://127.0.0.1:5000")

# 本地工作目录（存放解压后的图片和 JSON 文件）
WORKSPACE_DIR = "./workshop"

# 本地存储学生姓名的隐藏文件
NAME_FILE = ".annotator_name"
# ===============================================


def get_saved_name():
    """从本地文件中读取已保存的学生姓名"""
    if not os.path.exists(NAME_FILE):
        LOGGER.error("错误：尚未登录，请先运行 'client login <姓名>'")
        return None
    with open(NAME_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()


def save_name(name: str):
    """将学生姓名保存到本地文件"""
    with open(NAME_FILE, "w", encoding="utf-8") as f:
        f.write(name.strip())

def setup_logging():
    """配置日志：同时输出到控制台和文件，文件保存在 ./_log/ 目录下"""
    # 参见https://chat.deepseek.com/share/im8qe7wn8s6d7k3mee
    log_dir = "./_log"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"client_{datetime.now().strftime('%Y%m%d')}.log")
    
    # 创建 logger
    logger = logging.getLogger('AnnotatorClient')
    logger.setLevel(logging.DEBUG)
    
    # 文件处理器（按大小轮转，每个最大5MB，保留3个备份）
    file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    
    # 控制台处理器（只输出 INFO 及以上，也可保留）
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger

# 全局 logger 实例
LOGGER = setup_logging()

def global_exception_handler(exc_type, exc_value, exc_tb):
    """捕获未处理的异常，自动上传日志并退出"""
    LOGGER.error("未捕获的异常", exc_info=(exc_type, exc_value, exc_tb))
    upload_log_async(reason="crash")
    # 调用默认的异常处理（可选，打印到 stderr）
    sys.__excepthook__(exc_type, exc_value, exc_tb)

sys.excepthook = global_exception_handler

def upload_log_async(reason="auto"):
    """异步上传当前日志文件到遥测服务器（不阻塞主程序）"""
    if not config.get("telemetry_enabled", False):
        return

    telemetry_url = config.get("telemetry_server_url")
    if not telemetry_url:
        return

    log_dir = "./_log"
    if not os.path.isdir(log_dir):
        return

    # 获取最新的日志文件
    log_files = [f for f in os.listdir(log_dir) if f.endswith('.log')]
    if not log_files:
        return
    latest_log = max(log_files, key=lambda f: os.path.getmtime(os.path.join(log_dir, f)))
    log_path = os.path.join(log_dir, latest_log)

    def _upload():
        try:
            with open(log_path, 'rb') as f:
                files = {'log_file': (latest_log, f, 'text/plain')}
                data = {'client_name': get_saved_name() or 'anonymous', 'reason': reason}
                requests.post(telemetry_url, files=files, data=data, timeout=30, verify=True)
        except Exception:
            pass  # 静默失败，避免干扰主流程

    threading.Thread(target=_upload, daemon=True).start()

@click.group()
def cli():
    """学生端命令行工具 – 用于与教师服务器交互，获取并提交标注任务"""
    pass


@cli.command()
@click.argument("name")
def login(name):
    """登录服务器，检查姓名是否在分配名单中，并获取任务数量"""
    LOGGER.info("登录：姓名：{name}")
    try:
        resp = requests.get(f"{SERVER_URL}/login", params={"name": name}, timeout=10, verify=True)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "ok":
                task_count = data.get("task_count", 0)
                save_name(name)
                LOGGER.info(f"登录成功！姓名：{name}，分配到的图片数量：{task_count}")
            else:
                LOGGER.error(f"登录失败：服务器返回状态异常 {data}")
        else:
            LOGGER.error(f"登录失败：HTTP {resp.status_code} - {resp.text}")
    except Exception as e:
        LOGGER.error(f"登录失败，网络或服务器错误：{e}")


@cli.command()
def pull():
    """从服务器下载分配给当前学生的任务包（原始图片 + 已上传的 JSON），并自动解压到 workspace 目录"""
    LOGGER.info("开始执行PULL")
    name = get_saved_name()
    if not name:
        return

    # 请求下载 ZIP 包
    try:
        resp = requests.get(f"{SERVER_URL}/pull", params={"name": name}, timeout=30, verify=True)
        if resp.status_code != 200:
            LOGGER.error(f"拉取任务失败：HTTP {resp.status_code} - {resp.text}")
            return
    except Exception as e:
        LOGGER.error(f"拉取任务失败，网络异常：{e}")
        return
    
    # 获取包大小（优先使用 Content-Length，否则用实际内容长度）
    content_length = resp.headers.get('content-length')
    zip_content = resp.content
    actual_size = len(zip_content)
    size_info = f"{actual_size} bytes" + (f" (Content-Length: {content_length})" if content_length else "")
    LOGGER.info(f"下载任务包大小：{size_info}")

    # 保存 ZIP 到临时文件（直接用名字命名）
    zip_filename = f"{name}_task.zip"
    with open(zip_filename, "wb") as f:
        f.write(resp.content)
    LOGGER.info(f"任务包下载完成：{zip_filename}")

    # 自动解压到 WORKSPACE_DIR
    os.makedirs(WORKSPACE_DIR, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_filename, "r") as zf:
            zf.extractall(WORKSPACE_DIR)
        LOGGER.info(f"已解压到目录：{WORKSPACE_DIR}")
        # 解压成功后询问是否删除原始 ZIP（可选，保留亦可）
        # os.remove(zip_filename)   # 如需清理可取消注释
    except Exception as e:
        LOGGER.error(f"解压失败：{e}")
        return
    
    # 在解压后，获取当前应分配的图片列表
    try:
        resp = requests.get(f"{SERVER_URL}/status", params={"name": name}, timeout=10, verify=True)
        if resp.status_code == 200:
            data = resp.json()
            active_images = data.get('assigned_images', [])
            active_basenames = {os.path.splitext(img)[0] for img in active_images}
        else:
            active_basenames = set()
    except Exception:
        active_basenames = set()

    # 清理 workshop 中的无效 JSON
    if os.path.isdir(WORKSPACE_DIR):
        for fname in os.listdir(WORKSPACE_DIR):
            if fname.lower().endswith('.json'):
                base = os.path.splitext(fname)[0]
                if active_basenames and base not in active_basenames:
                    os.remove(os.path.join(WORKSPACE_DIR, fname))
                    LOGGER.info(f"已删除失效标注文件：{fname}")

    LOGGER.info("提示：请使用 LabelMe 打开 workshop 目录中的图片进行标注，标注后 JSON 文件会自动保存在同一目录。")


def _upload_json(file_path: str, name: str) -> bool:
    """内部函数：上传单个 JSON 文件，返回是否成功"""
    if not os.path.isfile(file_path):
        LOGGER.error(f"文件不存在：{file_path}")
        return False

    # 服务器要求上传字段名为 'file'
    with open(file_path, "rb") as f:
        files = {"file": (os.path.basename(file_path), f, "application/json")}
        try:
            resp = requests.post(
                f"{SERVER_URL}/push", params={"name": name}, files=files, timeout=30, verify=True
            )
            if resp.status_code == 200:
                LOGGER.info(f"✅ 上传成功：{file_path}")
                return True
            else:
                LOGGER.error(f"❌ 上传失败 {file_path}：HTTP {resp.status_code} - {resp.text}")
                return False
        except Exception as e:
            LOGGER.error(f"❌ 上传异常 {file_path}：{e}")
            return False


@cli.command()
def push():
    """自动上传 workshop 目录下所有的 JSON 标注文件"""
    name = get_saved_name()
    if not name:
        return

    if not os.path.isdir(WORKSPACE_DIR):
        LOGGER.error(f"错误：工作目录 {WORKSPACE_DIR} 不存在，请先运行 pull 下载任务。")
        return

    json_files = [f for f in os.listdir(WORKSPACE_DIR) if f.lower().endswith(".json")]
    if not json_files:
        LOGGER.info(f"在 {WORKSPACE_DIR} 中没有找到任何 .json 文件")
        return

    LOGGER.info(f"找到 {len(json_files)} 个 JSON 文件，开始上传...")
    success = 0
    for jf in json_files:
        full_path = os.path.join(WORKSPACE_DIR, jf)
        if _upload_json(full_path, name):
            success += 1

    LOGGER.info(f"上传完成：成功 {success} / 总计 {len(json_files)}")

@cli.command()
def status():
    """查看任务进度及分配图片列表"""
    name = get_saved_name()
    if not name:
        return
    try:
        resp = requests.get(f"{SERVER_URL}/status", params={"name": name}, timeout=10, verify=True)
        if resp.status_code != 200:
            LOGGER.error(f"获取状态失败：{resp.text}")
            return
        data = resp.json()
        LOGGER.info(f"任务进度：{data['uploaded']}/{data['total']} 已完成，剩余 {data['unuploaded']} 张")
        LOGGER.info("当前分配图片：")
        for img in data.get('assigned_images', []):
            LOGGER.info(f"  - {img}")
    except Exception as e:
        LOGGER.error(f"请求失败：{e}")
        
@cli.command()
def clean():
    """删除 workspace 目录及其所有内容（清除本地的图片和标注文件）"""
    if not os.path.exists(WORKSPACE_DIR):
        LOGGER.info(f"工作目录 {WORKSPACE_DIR} 不存在，无需清理。")
        return

    # 交互确认防止误删
    if click.confirm(f"即将删除整个目录 '{WORKSPACE_DIR}'，其中包含的所有图片和标注文件都将丢失。确定要执行吗？"):
        import shutil
        shutil.rmtree(WORKSPACE_DIR)
        LOGGER.info(f"已删除目录：{WORKSPACE_DIR}")
    else:
        LOGGER.info("操作已取消。")

@cli.command()
def update():
    """从更新服务器下载最新客户端包并增量覆盖当前目录"""
    # 读取配置中的更新服务器地址
    update_url = config.get("update_server_url")
    if not update_url:
        LOGGER.error("错误：config.json 中未配置 'update_server_url'")
        return

    LOGGER.info(f"正在从 {update_url} 获取更新包...")
    try:
        # 流式下载，避免大文件占用过多内存
        resp = requests.get(update_url, stream=True, timeout=30, verify=True)
        if resp.status_code != 200:
            LOGGER.error(f"下载失败：HTTP {resp.status_code}")
            return

        # 保存到临时 ZIP 文件
        import tempfile
        fd, tmp_zip = tempfile.mkstemp(suffix=".zip")
        os.close(fd)
        total_size = int(resp.headers.get('content-length', 0))
        with open(tmp_zip, 'wb') as f:
            with click.progressbar(length=total_size, label="下载进度") as bar:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
                    bar.update(len(chunk))

        # 解压到当前目录（增量覆盖）
        LOGGER.info("正在解压更新包...")
        with zipfile.ZipFile(tmp_zip, 'r') as zf:
            zf.extractall(".")   # 直接解压到当前工作目录（client.exe 所在处）
        LOGGER.info("更新完成！请重新启动客户端以使更新生效。")

        # 清理临时文件
        os.remove(tmp_zip)
    except Exception as e:
        LOGGER.error(f"更新失败：{e}")

@cli.command()
def upload_log():
    """上传日志文件到遥测服务器（需在 config 中开启遥测）"""
    # 检查遥测是否启用
    telemetry_enabled = config.get("telemetry_enabled", False)
    telemetry_url = config.get("telemetry_server_url")
    
    if not telemetry_enabled:
        click.echo("遥测功能未开启，请在 config.json 中设置 telemetry_enabled=true")
        return
    if not telemetry_url:
        click.echo("错误：未配置 telemetry_server_url", err=True)
        return
    
    # 查找日志文件
    log_dir = "./_log"
    if not os.path.isdir(log_dir):
        click.echo("没有找到日志目录，请先运行程序产生日志。")
        return
    
    # 获取最新的日志文件（按修改时间排序）
    log_files = [f for f in os.listdir(log_dir) if f.endswith('.log')]
    if not log_files:
        click.echo("没有找到日志文件")
        return
    latest_log = max(log_files, key=lambda f: os.path.getmtime(os.path.join(log_dir, f)))
    log_path = os.path.join(log_dir, latest_log)
    
    click.echo(f"准备上传日志文件：{latest_log}")
    try:
        with open(log_path, 'rb') as f:
            files = {'log_file': (latest_log, f, 'text/plain')}
            # 可选：添加客户端标识（如主机名、用户名等）
            data = {'client_name': get_saved_name() or 'anonymous'}
            resp = requests.post(telemetry_url, files=files, data=data, timeout=30, verify=True)
        if resp.status_code == 200:
            click.echo("日志上传成功")
            LOGGER.info(f"日志文件 {latest_log} 已上传至遥测服务器")
        else:
            click.echo(f"上传失败：HTTP {resp.status_code} - {resp.text}", err=True)
            LOGGER.error(f"上传日志失败：{resp.status_code} {resp.text}")
    except Exception as e:
        click.echo(f"上传异常：{e}", err=True)
        LOGGER.exception("上传日志时发生异常")

if __name__ == "__main__":
    cli()