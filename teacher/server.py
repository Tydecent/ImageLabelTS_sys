"""
教师端服务器 (Flask)
启动方式：
    python ./server.py <图片文件夹路径> <学生名单文件路径>
示例：
    python ./server.py ./images students.txt
服务器将在 0.0.0.0:12010 上监听，可供局域网内学生访问。
"""
import os
import sys
import json
import random
import zipfile
import io
from flask import Flask, request, jsonify, send_file

app = Flask(__name__)

# ---------- 全局配置 ----------
IMAGE_DIR = ""          # 图片文件夹路径，通过命令行参数传入
STUDENTS_FILE = ""      # 学生名单文件路径，通过命令行参数传入
ASSIGNMENTS_FILE = "assignments.json"   # 分配结果保存文件
RESULTS_DIR = "results"                 # 学生上传的 JSON 结果存放根目录
SUPPORTED_IMG_EXT = ('.jpg', '.jpeg', '.png')

# 内存中的数据结构
students = []           # 学生名单列表
assignments = {}        # 分配字典, 格式: {"张三": ["img1.jpg", ...], ...}
image_files = []        # 所有有效图片文件名列表

# ---------- 辅助函数 ----------
def load_students():
    """从名单文件中读取学生姓名，每行一个，去除空行与首尾空格。"""
    global students
    if not os.path.exists(STUDENTS_FILE):
        print(f"❌ 学生名单文件不存在: {STUDENTS_FILE}")
        sys.exit(1)
    with open(STUDENTS_FILE, 'r', encoding='utf-8') as f:
        students = [line.strip() for line in f if line.strip()]
    print(f"✅ 已加载 {len(students)} 名学生: {', '.join(students)}")

def load_images():
    """从图片文件夹中获取所有支持的图片文件名。"""
    global image_files
    if not os.path.isdir(IMAGE_DIR):
        print(f"❌ 图片文件夹不存在: {IMAGE_DIR}")
        sys.exit(1)
    all_files = os.listdir(IMAGE_DIR)
    image_files = [f for f in all_files if f.lower().endswith(SUPPORTED_IMG_EXT)]
    if not image_files:
        print("❌ 图片文件夹中没有支持的文件（jpg, jpeg, png）")
        sys.exit(1)
    print(f"✅ 找到 {len(image_files)} 张图片")

def assign_images():
    """
    随机打乱图片，平均分配给每名学生。
    如果已有 assignments.json 且学生名单匹配，则直接加载，
    否则重新生成分配方案并保存。
    """
    global assignments
    # 检查是否存在历史分配方案
    if os.path.exists(ASSIGNMENTS_FILE):
        with open(ASSIGNMENTS_FILE, 'r', encoding='utf-8') as f:
            old_assignments = json.load(f)
        # 简单判断：如果历史记录中的学生集合与当前名单一致，则沿用
        if set(old_assignments.keys()) == set(students):
            assignments = old_assignments
            print("📂 已从 assignments.json 加载现有分配方案")
            return
        else:
            print("⚠️ 学生名单已变更，将重新分配图片")

    # 随机打乱图片顺序
    shuffled = image_files.copy()
    random.shuffle(shuffled)

    # 计算每名学生的基础分配数量
    base_count = len(shuffled) // len(students)
    remainder = len(shuffled) % len(students)

    assignments = {}
    idx = 0
    for i, student in enumerate(students):
        # 前 remainder 名学生多分配一张图片
        count = base_count + (1 if i < remainder else 0)
        assignments[student] = shuffled[idx:idx + count]
        idx += count

    # 保存分配方案到文件
    with open(ASSIGNMENTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(assignments, f, ensure_ascii=False, indent=2)
    print(f"✅ 已生成新分配方案并保存至 {ASSIGNMENTS_FILE}")

def get_student_dir(name):
    """返回某个学生的结果目录路径，例如 results/张三/"""
    return os.path.join(RESULTS_DIR, name)

def get_task_image_basenames(name):
    """返回该学生分配到的图片的基本名（不含扩展名）列表，用于 push 校验。"""
    if name not in assignments:
        return []
    return [os.path.splitext(img)[0] for img in assignments[name]]

# ---------- API 端点 ----------
@app.route('/login', methods=['GET'])
def login():
    """登录检查：姓名是否在名单中，并返回任务数量。"""
    name = request.args.get('name', '').strip()
    if not name or name not in assignments:
        return jsonify({"status": "error", "message": "姓名不在名单中"}), 403
    task_count = len(assignments[name])
    return jsonify({"status": "ok", "task_count": task_count})

@app.route('/pull', methods=['GET'])
def pull():
    """
    打包下载：将该学生分配的所有原始图片 + 他已上传的所有 JSON 文件
    打包成 ZIP 返回，ZIP 内部文件平铺在根目录。
    """
    name = request.args.get('name', '').strip()
    if not name or name not in assignments:
        return "姓名不在名单中", 403

    # 创建内存 ZIP 文件
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # 1. 添加分配的原始图片（从 IMAGE_DIR 读取）
        for img_filename in assignments[name]:
            img_path = os.path.join(IMAGE_DIR, img_filename)
            if os.path.isfile(img_path):
                zf.write(img_path, img_filename)  # 平铺在 ZIP 根目录
            else:
                # 原图片缺失时，记录警告（不影响打包流程）
                print(f"⚠️ 图片文件缺失: {img_path}")

        # 2. 添加该学生已上传的所有 JSON 文件
        student_dir = get_student_dir(name)
        if os.path.isdir(student_dir):
            for fname in os.listdir(student_dir):
                if fname.lower().endswith('.json'):
                    fpath = os.path.join(student_dir, fname)
                    zf.write(fpath, fname)  # 平铺

    zip_buffer.seek(0)
    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'{name}_task.zip'
    )

@app.route('/push', methods=['POST'])
def push():
    """
    接收学生上传的 JSON 标注文件。
    要求：文件名（不含扩展名）必须与该学生任务中的某张图片（不含扩展名）一致。
    """
    name = request.args.get('name', '').strip()
    if not name or name not in assignments:
        return "姓名不在名单中", 403

    # 检查是否有文件上传，字段名为 'file'
    if 'file' not in request.files:
        return "缺少上传文件，字段名应为 'file'", 400

    file = request.files['file']
    if file.filename == '':
        return "未选择文件", 400

    # 只接受 .json 文件
    original_filename = file.filename
    if not original_filename.lower().endswith('.json'):
        return "只允许上传 .json 文件", 403

    # 提取基本名（不含扩展名）
    base_name = os.path.splitext(original_filename)[0]

    # 校验：是否属于该学生的任务图片（按基本名匹配）
    valid_basenames = get_task_image_basenames(name)
    if base_name not in valid_basenames:
        return f"文件名 '{base_name}' 与该学生任务不匹配", 403

    # 创建学生结果目录（如 results/张三/）
    student_dir = get_student_dir(name)
    os.makedirs(student_dir, exist_ok=True)

    # 保存文件（覆盖同名文件）
    save_path = os.path.join(student_dir, original_filename)
    file.save(save_path)
    print(f"📥 收到 {name} 的标注: {original_filename}")

    return jsonify({"status": "ok"})

@app.route('/status', methods=['GET'])
def status():
    """
    可选端点：返回该学生已上传和未上传的图片数量。
    """
    name = request.args.get('name', '').strip()
    if not name or name not in assignments:
        return jsonify({"error": "姓名不在名单中"}), 403

    total = len(assignments[name])
    student_dir = get_student_dir(name)
    uploaded = 0
    if os.path.isdir(student_dir):
        # 统计目录下与任务图片名对应的 JSON 文件
        json_files = [f for f in os.listdir(student_dir) if f.endswith('.json')]
        basename_jsons = {os.path.splitext(f)[0] for f in json_files}
        task_basenames = set(get_task_image_basenames(name))
        uploaded = len(basename_jsons & task_basenames)

    return jsonify({
        "uploaded": uploaded,
        "unuploaded": total - uploaded,
        "total": total
    })

# ---------- 前端页面 ----------
@app.route('/dashboard')
def dashboard():
    """教师端可视化面板"""
    html = '''
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>标注任务监控面板</title>
            <style>
                :root {
                    --bg: #f0f4f8;
                    --card-bg: #ffffff;
                    --primary: #4f6ef7;
                    --primary-hover: #3b54d4;
                    --success: #22c55e;
                    --success-bg: #dcfce7;
                    --success-border: #86efac;
                    --warning: #f59e0b;
                    --text: #1e293b;
                    --text-secondary: #64748b;
                    --border: #e2e8f0;
                    --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.04);
                    --shadow: 0 4px 6px rgba(0, 0, 0, 0.05), 0 2px 4px rgba(0, 0, 0, 0.03);
                    --shadow-lg: 0 10px 25px rgba(0, 0, 0, 0.08), 0 4px 10px rgba(0, 0, 0, 0.04);
                    --radius: 12px;
                    --radius-sm: 8px;
                    --transition: 0.2s cubic-bezier(0.4, 0, 0.2, 1);
                    --font: 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', system-ui, -apple-system, sans-serif;
                }

                * {
                    box-sizing: border-box;
                    margin: 0;
                    padding: 0;
                }

                body {
                    font-family: var(--font);
                    background: var(--bg);
                    color: var(--text);
                    min-height: 100vh;
                    padding: 2rem;
                    background-image:
                        radial-gradient(ellipse at 15% 20%, rgba(79, 110, 247, 0.04) 0%, transparent 60%),
                        radial-gradient(ellipse at 85% 75%, rgba(34, 197, 94, 0.03) 0%, transparent 60%),
                        radial-gradient(ellipse at 50% 50%, rgba(148, 163, 184, 0.03) 0%, transparent 70%);
                }

                /* ========== 主容器 ========== */
                .container {
                    max-width: 960px;
                    margin: 0 auto;
                    display: flex;
                    flex-direction: column;
                    gap: 1.5rem;
                }

                /* ========== 页头 ========== */
                .page-header {
                    display: flex;
                    align-items: center;
                    gap: 1rem;
                    flex-wrap: wrap;
                }

                .page-header .icon-wrapper {
                    width: 44px;
                    height: 44px;
                    border-radius: var(--radius-sm);
                    background: linear-gradient(135deg, #4f6ef7 0%, #7c8cf8 100%);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    flex-shrink: 0;
                    box-shadow: 0 4px 12px rgba(79, 110, 247, 0.3);
                }

                .page-header .icon-wrapper svg {
                    width: 22px;
                    height: 22px;
                    fill: #fff;
                }

                .page-header h1 {
                    font-size: 1.65rem;
                    font-weight: 700;
                    letter-spacing: -0.02em;
                    color: #0f172a;
                    line-height: 1.2;
                }

                .page-header .subtitle {
                    font-size: 0.85rem;
                    color: var(--text-secondary);
                    font-weight: 400;
                    display: block;
                }

                /* ========== 总体进度卡片 ========== */
                .summary-card {
                    background: var(--card-bg);
                    border-radius: var(--radius);
                    padding: 1.25rem 1.5rem;
                    box-shadow: var(--shadow);
                    border: 1px solid var(--border);
                    display: flex;
                    align-items: center;
                    gap: 1rem;
                    flex-wrap: wrap;
                    transition: box-shadow var(--transition);
                }

                .summary-card:hover {
                    box-shadow: var(--shadow-lg);
                }

                .summary-card .summary-label {
                    font-weight: 600;
                    font-size: 0.9rem;
                    color: var(--text-secondary);
                    text-transform: uppercase;
                    letter-spacing: 0.04em;
                }

                .summary-card .summary-value {
                    font-weight: 700;
                    font-size: 1.4rem;
                    color: var(--primary);
                    letter-spacing: -0.01em;
                }

                .summary-card .summary-divider {
                    width: 1px;
                    height: 28px;
                    background: var(--border);
                    border-radius: 1px;
                    flex-shrink: 0;
                }

                .summary-card .summary-percent {
                    font-size: 2rem;
                    font-weight: 800;
                    letter-spacing: -0.02em;
                    color: #0f172a;
                    line-height: 1;
                }

                .summary-card .summary-sub {
                    font-size: 0.8rem;
                    color: var(--text-secondary);
                }

                /* 总体进度条 */
                .overall-progress-wrap {
                    flex: 1;
                    min-width: 180px;
                    display: flex;
                    flex-direction: column;
                    gap: 6px;
                }

                .overall-progress-bar-outer {
                    background: #e8ecf1;
                    border-radius: 20px;
                    height: 10px;
                    overflow: hidden;
                    width: 100%;
                }

                .overall-progress-bar-inner {
                    height: 100%;
                    border-radius: 20px;
                    background: linear-gradient(90deg, #4f6ef7 0%, #6d8afa 50%, #22c55e 100%);
                    transition: width 0.6s cubic-bezier(0.25, 0.8, 0.25, 1.2);
                    position: relative;
                }

                .overall-progress-bar-inner::after {
                    content: '';
                    position: absolute;
                    right: 2px;
                    top: 2px;
                    bottom: 2px;
                    width: 6px;
                    border-radius: 50%;
                    background: rgba(255, 255, 255, 0.7);
                    animation: shimmer 2s infinite;
                }

                @keyframes shimmer {
                    0%,
                    100% {
                        opacity: 0.4;
                    }
                    50% {
                        opacity: 1;
                    }
                }

                /* ========== 表格容器 ========== */
                .table-wrapper {
                    background: var(--card-bg);
                    border-radius: var(--radius);
                    box-shadow: var(--shadow);
                    border: 1px solid var(--border);
                    overflow: hidden;
                }

                table {
                    border-collapse: collapse;
                    width: 100%;
                    font-size: 0.9rem;
                }

                thead {
                    background: #f8fafc;
                    border-bottom: 2px solid var(--border);
                }

                th {
                    padding: 14px 16px;
                    text-align: left;
                    font-weight: 700;
                    font-size: 0.78rem;
                    text-transform: uppercase;
                    letter-spacing: 0.05em;
                    color: var(--text-secondary);
                    white-space: nowrap;
                }

                th:first-child {
                    padding-left: 20px;
                }
                th:last-child {
                    text-align: center;
                    padding-right: 20px;
                }

                tbody tr {
                    border-bottom: 1px solid #f1f5f9;
                    transition: background-color var(--transition);
                }

                tbody tr:last-child {
                    border-bottom: none;
                }

                tbody tr.main-row:hover {
                    background-color: #f8fafd;
                }

                tbody tr.main-row {
                    cursor: default;
                }

                td {
                    padding: 14px 16px;
                    vertical-align: middle;
                    color: var(--text);
                }

                td:first-child {
                    padding-left: 20px;
                    font-weight: 600;
                    white-space: nowrap;
                }

                td:last-child {
                    text-align: center;
                    padding-right: 20px;
                }

                /* ========== 进度条单元格 ========== */
                .progress-cell {
                    display: flex;
                    align-items: center;
                    gap: 10px;
                    flex-wrap: wrap;
                }

                .progress-container {
                    background-color: #e8ecf1;
                    border-radius: 20px;
                    width: 130px;
                    height: 8px;
                    overflow: hidden;
                    flex-shrink: 0;
                }

                .progress-bar {
                    background: linear-gradient(90deg, #4f6ef7 0%, #22c55e 100%);
                    height: 100%;
                    border-radius: 20px;
                    transition: width 0.5s ease;
                    position: relative;
                }

                .progress-fraction {
                    font-weight: 600;
                    font-size: 0.85rem;
                    color: var(--text);
                    white-space: nowrap;
                    letter-spacing: -0.01em;
                }

                /* ========== 按钮 ========== */
                .btn-detail {
                    display: inline-flex;
                    align-items: center;
                    gap: 6px;
                    padding: 8px 16px;
                    background: #fff;
                    color: var(--primary);
                    border: 1.5px solid #dde4f7;
                    border-radius: 20px;
                    font-size: 0.8rem;
                    font-weight: 600;
                    cursor: pointer;
                    transition: all var(--transition);
                    white-space: nowrap;
                    font-family: var(--font);
                    letter-spacing: 0.01em;
                }

                .btn-detail:hover {
                    background: #f0f3ff;
                    border-color: var(--primary);
                    color: var(--primary-hover);
                    box-shadow: 0 2px 8px rgba(79, 110, 247, 0.15);
                    transform: translateY(-1px);
                }

                .btn-detail:active {
                    transform: scale(0.96);
                    background: #e8ecfe;
                }

                .btn-detail .arrow-icon {
                    display: inline-block;
                    transition: transform var(--transition);
                    font-size: 0.7rem;
                }

                .btn-detail.expanded .arrow-icon {
                    transform: rotate(180deg);
                }

                /* ========== 详情行 ========== */
                .detail-row {
                    display: none;
                    background: #fafbfd;
                }

                .detail-row td {
                    padding: 0 20px 20px 20px;
                }

                .detail-card {
                    background: #fff;
                    border: 1px solid #e8ecf1;
                    border-radius: var(--radius-sm);
                    padding: 1rem 1.25rem;
                    animation: fadeSlideIn 0.3s ease;
                    box-shadow: var(--shadow-sm);
                }

                @keyframes fadeSlideIn {
                    from {
                        opacity: 0;
                        transform: translateY(-8px);
                    }
                    to {
                        opacity: 1;
                        transform: translateY(0);
                    }
                }

                .detail-card .detail-title {
                    font-weight: 700;
                    font-size: 0.82rem;
                    color: var(--text);
                    margin-bottom: 0.75rem;
                    text-transform: uppercase;
                    letter-spacing: 0.04em;
                    display: flex;
                    align-items: center;
                    gap: 6px;
                }

                .detail-card .detail-title::before {
                    content: '';
                    display: inline-block;
                    width: 4px;
                    height: 16px;
                    border-radius: 2px;
                    background: var(--primary);
                    flex-shrink: 0;
                }

                /* ========== 图片列表 - 一行一个（垂直排列） ========== */
                .image-list {
                    display: flex;
                    flex-direction: column;
                    gap: 6px;
                    margin-top: 4px;
                    max-height: 360px;
                    overflow-y: auto;
                    padding-right: 4px;
                }

                /* 自定义滚动条 */
                .image-list::-webkit-scrollbar {
                    width: 5px;
                }

                .image-list::-webkit-scrollbar-track {
                    background: transparent;
                    border-radius: 10px;
                }

                .image-list::-webkit-scrollbar-thumb {
                    background: #d4d9e2;
                    border-radius: 10px;
                }

                .image-list::-webkit-scrollbar-thumb:hover {
                    background: #b0b8c4;
                }

                .image-item {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    background: #f8fafc;
                    border: 1px solid #e8ecf1;
                    border-radius: 6px;
                    padding: 9px 14px;
                    font-size: 0.82rem;
                    font-weight: 500;
                    color: #475569;
                    transition: all var(--transition);
                    font-family: 'SF Mono', 'Cascadia Code', 'Consolas', 'Monaco', monospace;
                    letter-spacing: 0.01em;
                    cursor: default;
                    word-break: break-all;
                }

                .image-item:hover {
                    background: #f1f5f9;
                    border-color: #ccd6e0;
                }

                .image-item .status-icon {
                    flex-shrink: 0;
                    width: 20px;
                    height: 20px;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 11px;
                    font-weight: 700;
                }

                .image-item.uploaded {
                    background: #f0fdf4;
                    border-color: #bbf7d0;
                    color: #166534;
                }

                .image-item.uploaded:hover {
                    background: #dcfce7;
                    border-color: #86efac;
                }

                .image-item.uploaded .status-icon {
                    background: #22c55e;
                    color: #fff;
                }

                .image-item.not-uploaded .status-icon {
                    background: #f1f5f9;
                    color: #94a3b8;
                    border: 1.5px solid #d4d9e2;
                }

                .image-item .img-name {
                    flex: 1;
                    min-width: 0;
                }

                .image-item .img-badge {
                    flex-shrink: 0;
                    font-size: 0.68rem;
                    font-weight: 700;
                    padding: 3px 8px;
                    border-radius: 10px;
                    letter-spacing: 0.03em;
                    text-transform: uppercase;
                }

                .image-item.uploaded .img-badge {
                    background: #bbf7d0;
                    color: #166534;
                }

                .image-item.not-uploaded .img-badge {
                    background: #f1f5f9;
                    color: #94a3b8;
                }

                /* ========== 空状态 & 加载 ========== */
                .loading-text {
                    color: var(--text-secondary);
                    font-style: italic;
                    font-size: 0.82rem;
                    padding: 4px 0;
                    animation: pulse 1.5s infinite;
                }

                @keyframes pulse {
                    0%,
                    100% {
                        opacity: 1;
                    }
                    50% {
                        opacity: 0.45;
                    }
                }

                .no-images {
                    color: #94a3b8;
                    font-size: 0.82rem;
                    padding: 8px 0;
                }

                /* ========== 响应式 ========== */
                @media (max-width: 640px) {
                    body {
                        padding: 1rem;
                    }

                    .page-header h1 {
                        font-size: 1.3rem;
                    }

                    .summary-card {
                        flex-direction: column;
                        align-items: flex-start;
                        gap: 0.6rem;
                    }

                    .summary-card .summary-divider {
                        display: none;
                    }

                    .progress-container {
                        width: 90px;
                    }

                    th,
                    td {
                        padding: 10px 8px;
                        font-size: 0.78rem;
                    }

                    td:first-child,
                    th:first-child {
                        padding-left: 10px;
                    }
                    td:last-child,
                    th:last-child {
                        padding-right: 10px;
                    }

                    .btn-detail {
                        padding: 6px 12px;
                        font-size: 0.72rem;
                    }

                    .detail-row td {
                        padding: 0 8px 14px 8px;
                    }

                    .image-item {
                        font-size: 0.74rem;
                        padding: 7px 10px;
                    }
                }

                @media (max-width: 400px) {
                    .progress-cell {
                        flex-direction: column;
                        align-items: flex-start;
                        gap: 4px;
                    }
                    .progress-container {
                        width: 100%;
                    }
                }
            </style>
        </head>
        <body>
            <div class="container">
                <!-- 页头 -->
                <div class="page-header">
                    <div class="icon-wrapper">
                        <svg viewBox="0 0 24 24"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zM9 17H7v-7h2v7zm4 0h-2V7h2v10zm4 0h-2v-4h2v4z"/></svg>
                    </div>
                    <div>
                        <h1>标注任务监控面板</h1>
                        <span class="subtitle">实时追踪团队标注进度</span>
                    </div>
                </div>

                <!-- 总体进度 -->
                <div class="summary-card" id="summary">
                    <span class="loading-text">正在加载数据…</span>
                </div>

                <!-- 学生表格 -->
                <div class="table-wrapper">
                    <table id="student-table">
                        <thead>
                            <tr>
                                <th>姓名</th>
                                <th>完成进度</th>
                                <th style="text-align:center;">详情</th>
                            </tr>
                        </thead>
                        <tbody id="table-body"></tbody>
                    </table>
                </div>
            </div>

            <script>
                async function loadData() {
                    const resp = await fetch('/api/overview');
                    const data = await resp.json();
                    const summary = data.total_overall;

                    // 渲染总体进度卡片
                    const percentOverall = ((summary.uploaded / summary.total) * 100).toFixed(1);
                    document.getElementById('summary').innerHTML = `
                                <span class="summary-label">📊 总体进度</span>
                                <span class="summary-value">${summary.uploaded} / ${summary.total}</span>
                                <span class="summary-divider"></span>
                                <span class="summary-percent">${percentOverall}%</span>
                                <span class="summary-sub">已完成</span>
                                <div class="overall-progress-wrap">
                                    <div class="overall-progress-bar-outer">
                                        <div class="overall-progress-bar-inner" style="width:${percentOverall}%;"></div>
                                    </div>
                                    <span style="font-size:0.72rem;color:#94a3b8;">剩余 ${summary.total - summary.uploaded} 张图片待标注</span>
                                </div>
                            `;

                    const tbody = document.getElementById('table-body');
                    tbody.innerHTML = '';
                    data.students.forEach((stu, idx) => {
                        const percent = (stu.uploaded / stu.total * 100).toFixed(1);
                        // 主数据行
                        const row = tbody.insertRow();
                        row.className = 'main-row';
                        // 姓名
                        row.insertCell(0).innerText = stu.name;
                        // 进度
                        row.insertCell(1).innerHTML = `
                                    <div class="progress-cell">
                                        <div class="progress-container">
                                            <div class="progress-bar" style="width:${percent}%;"></div>
                                        </div>
                                        <span class="progress-fraction">${stu.uploaded}/${stu.total} (${percent}%)</span>
                                    </div>
                                `;
                        // 按钮
                        const btnCell = row.insertCell(2);
                        const btn = document.createElement('button');
                        btn.className = 'btn-detail';
                        btn.innerHTML = '查看图片 <span class="arrow-icon">▾</span>';
                        btn.onclick = function() {
                            toggleDetail(idx, stu, btn);
                        };
                        btnCell.appendChild(btn);

                        // 隐藏的详情行
                        const detailRow = tbody.insertRow();
                        detailRow.className = 'detail-row';
                        detailRow.id = `detail-${idx}`;
                        const detailCell = detailRow.insertCell(0);
                        detailCell.colSpan = 3;
                        detailCell.innerHTML =
                            '<div id="detail-content-' + idx +
                            '" style="min-height:20px;"><span class="loading-text">点击查看后加载…</span></div>';
                        detailRow.style.display = 'none';
                    });
                    window.studentsData = data.students;
                }

                function toggleDetail(idx, stu, btnElement) {
                    const detailRow = document.getElementById(`detail-${idx}`);
                    const isVisible = detailRow.style.display !== 'none';
                    if (!isVisible) {
                        const uploadedSet = new Set(stu.uploaded_images);
                        // 去掉扩展名的辅助函数
                        const stripExt = (filename) => filename.replace(/\.[^/.]+$/, '');
                        const html = `
                                    <div class="detail-card">
                                        <div class="detail-title">📁 分配图片列表（共 ${stu.images.length} 张）</div>
                                        <div class="image-list">
                                            ${stu.images.map(img => {
                                                const baseName = stripExt(img);
                                                const isUploaded = uploadedSet.has(img) || uploadedSet.has(baseName);
                                                const cls = isUploaded ? 'uploaded' : 'not-uploaded';
                                                const icon = isUploaded ? '✓' : '—';
                                                const badge = isUploaded ? '已上传' : '未上传';
                                                return `
                                                    <div class="image-item ${cls}">
                                                        <span class="status-icon">${icon}</span>
                                                        <span class="img-name" title="${img}">${img}</span>
                                                        <span class="img-badge">${badge}</span>
                                                    </div>`;
                                            }).join('')}
                                        </div>
                                    </div>
                                `;
                        document.getElementById(`detail-content-${idx}`).innerHTML = html;
                        detailRow.style.display = 'table-row';
                        if (btnElement) {
                            btnElement.classList.add('expanded');
                            btnElement.innerHTML = '收起图片 <span class="arrow-icon">▾</span>';
                        }
                    } else {
                        detailRow.style.display = 'none';
                        if (btnElement) {
                            btnElement.classList.remove('expanded');
                            btnElement.innerHTML = '查看图片 <span class="arrow-icon">▾</span>';
                        }
                    }
                }

                loadData();
            </script>
        </body>
        </html>
    '''
    from flask import render_template_string
    return render_template_string(html)

@app.route('/api/overview')
def api_overview():
    """返回所有学生的任务分配及完成情况（JSON）"""
    from flask import jsonify
    overview = {
        "students": [],
        "total_overall": {"total": 0, "uploaded": 0}
    }
    total_all = 0
    uploaded_all = 0

    for student in students:
        # 该学生分配的原始图片文件名列表
        images = assignments.get(student, [])
        total = len(images)
        total_all += total

        # 该学生结果目录
        student_dir = get_student_dir(student)
        uploaded_basenames = set()
        if os.path.isdir(student_dir):
            for fname in os.listdir(student_dir):
                if fname.lower().endswith('.json'):
                    base = os.path.splitext(fname)[0]
                    uploaded_basenames.add(base)

        # 计算已上传数量（图片基本名匹配）
        uploaded = 0
        uploaded_images = []
        for img in images:
            base = os.path.splitext(img)[0]
            if base in uploaded_basenames:
                uploaded += 1
                uploaded_images.append(base)
        uploaded_all += uploaded

        overview["students"].append({
            "name": student,
            "total": total,
            "uploaded": uploaded,
            "images": images,                     # 原始图片文件名列表，如 ["cat.jpg","dog.png"]
            "uploaded_images": uploaded_images   # 已上传的图片基本名列表
        })

    overview["total_overall"] = {
        "total": total_all,
        "uploaded": uploaded_all
    }
    return jsonify(overview)

# ---------- 启动入口 ----------
if __name__ == '__main__':
    # 处理命令行参数
    if len(sys.argv) != 3:
        print("用法: python server.py <图片文件夹> <学生名单文件>")
        print("示例: python server.py ./images students.txt")
        sys.exit(1)

    IMAGE_DIR = sys.argv[1]
    STUDENTS_FILE = sys.argv[2]

    # 初始化：加载名单、图片、分配
    load_students()
    load_images()
    assign_images()

    # 确保 results 根目录存在
    os.makedirs(RESULTS_DIR, exist_ok=True)

    # 启用HTTPS：
    ssl_context = ('server.crt', 'server.key')

    print("\n🚀 服务器启动，监听 0.0.0.0:12010 ...")
    app.run(host='0.0.0.0', port=12010, debug=False, ssl_context=ssl_context)