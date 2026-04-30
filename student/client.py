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
        click.echo("错误：尚未登录，请先运行 'client login <姓名>'", err=True)
        return None
    with open(NAME_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()


def save_name(name: str):
    """将学生姓名保存到本地文件"""
    with open(NAME_FILE, "w", encoding="utf-8") as f:
        f.write(name.strip())


@click.group()
def cli():
    """学生端命令行工具 – 用于与教师服务器交互，获取并提交标注任务"""
    pass


@cli.command()
@click.argument("name")
def login(name):
    """登录服务器，检查姓名是否在分配名单中，并获取任务数量"""
    try:
        resp = requests.get(f"{SERVER_URL}/login", params={"name": name}, timeout=10, verify='server.crt')
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "ok":
                task_count = data.get("task_count", 0)
                save_name(name)
                click.echo(f"登录成功！姓名：{name}，分配到的图片数量：{task_count}")
            else:
                click.echo(f"登录失败：服务器返回状态异常 {data}", err=True)
        else:
            click.echo(f"登录失败：HTTP {resp.status_code} - {resp.text}", err=True)
    except Exception as e:
        click.echo(f"登录失败，网络或服务器错误：{e}", err=True)


@cli.command()
def pull():
    """从服务器下载分配给当前学生的任务包（原始图片 + 已上传的 JSON），并自动解压到 workspace 目录"""
    name = get_saved_name()
    if not name:
        return

    # 请求下载 ZIP 包
    try:
        resp = requests.get(f"{SERVER_URL}/pull", params={"name": name}, timeout=30, verify='server.crt')
        if resp.status_code != 200:
            click.echo(f"拉取任务失败：HTTP {resp.status_code} - {resp.text}", err=True)
            return
    except Exception as e:
        click.echo(f"拉取任务失败，网络异常：{e}", err=True)
        return

    # 保存 ZIP 到临时文件（直接用名字命名）
    zip_filename = f"{name}_task.zip"
    with open(zip_filename, "wb") as f:
        f.write(resp.content)
    click.echo(f"任务包下载完成：{zip_filename}")

    # 自动解压到 WORKSPACE_DIR
    os.makedirs(WORKSPACE_DIR, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_filename, "r") as zf:
            zf.extractall(WORKSPACE_DIR)
        click.echo(f"已解压到目录：{WORKSPACE_DIR}")
        # 解压成功后询问是否删除原始 ZIP（可选，保留亦可）
        # os.remove(zip_filename)   # 如需清理可取消注释
    except Exception as e:
        click.echo(f"解压失败：{e}", err=True)
        return
    
    # 在解压后，获取当前应分配的图片列表
    try:
        resp = requests.get(f"{SERVER_URL}/status", params={"name": name}, timeout=10, verify='server.crt')
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
                    click.echo(f"已删除失效标注文件：{fname}")

    click.echo("提示：请使用 LabelMe 打开 workshop 目录中的图片进行标注，标注后 JSON 文件会自动保存在同一目录。")


def _upload_json(file_path: str, name: str) -> bool:
    """内部函数：上传单个 JSON 文件，返回是否成功"""
    if not os.path.isfile(file_path):
        click.echo(f"文件不存在：{file_path}", err=True)
        return False

    # 服务器要求上传字段名为 'file'
    with open(file_path, "rb") as f:
        files = {"file": (os.path.basename(file_path), f, "application/json")}
        try:
            resp = requests.post(
                f"{SERVER_URL}/push", params={"name": name}, files=files, timeout=30, verify='server.crt'
            )
            if resp.status_code == 200:
                click.echo(f"✅ 上传成功：{file_path}")
                return True
            else:
                click.echo(f"❌ 上传失败 {file_path}：HTTP {resp.status_code} - {resp.text}", err=True)
                return False
        except Exception as e:
            click.echo(f"❌ 上传异常 {file_path}：{e}", err=True)
            return False


@cli.command()
def push():
    """自动上传 workshop 目录下所有的 JSON 标注文件"""
    name = get_saved_name()
    if not name:
        return

    if not os.path.isdir(WORKSPACE_DIR):
        click.echo(f"错误：工作目录 {WORKSPACE_DIR} 不存在，请先运行 pull 下载任务。", err=True)
        return

    json_files = [f for f in os.listdir(WORKSPACE_DIR) if f.lower().endswith(".json")]
    if not json_files:
        click.echo(f"在 {WORKSPACE_DIR} 中没有找到任何 .json 文件")
        return

    click.echo(f"找到 {len(json_files)} 个 JSON 文件，开始上传...")
    success = 0
    for jf in json_files:
        full_path = os.path.join(WORKSPACE_DIR, jf)
        if _upload_json(full_path, name):
            success += 1

    click.echo(f"上传完成：成功 {success} / 总计 {len(json_files)}")

@cli.command()
def status():
    """查看任务进度及分配图片列表"""
    name = get_saved_name()
    if not name:
        return
    try:
        resp = requests.get(f"{SERVER_URL}/status", params={"name": name}, timeout=10, verify='server.crt')
        if resp.status_code != 200:
            click.echo(f"获取状态失败：{resp.text}", err=True)
            return
        data = resp.json()
        click.echo(f"任务进度：{data['uploaded']}/{data['total']} 已完成，剩余 {data['unuploaded']} 张")
        click.echo("当前分配图片：")
        for img in data.get('assigned_images', []):
            click.echo(f"  - {img}")
    except Exception as e:
        click.echo(f"请求失败：{e}", err=True)

if __name__ == "__main__":
    cli()