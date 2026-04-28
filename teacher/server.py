"""
教师端服务器 (Flask)
启动方式：
    python ./teacher/server.py <图片文件夹路径> <学生名单文件路径>
示例：
    python ./teacher/server.py ./images students.txt
服务器将在 0.0.0.0:5000 上监听，可供局域网内学生访问。
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

    print("\n🚀 服务器启动，监听 0.0.0.0:5000 ...")
    app.run(host='0.0.0.0', port=5000, debug=False)