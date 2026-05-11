"""
教师端服务器 (Flask)
启动方式：
    python ./server.py <图片文件夹路径> <学生名单文件路径>
示例：
    python ./server.py ./Images students.txt
服务器将在 0.0.0.0:12010 上监听，可供局域网内学生访问。
"""
from gevent import monkey
monkey.patch_all()

import os
import sys
import json
import random
import zipfile
import io
from flask import Flask, request, jsonify, send_file, render_template 
from datetime import datetime

app = Flask(__name__)

# ---------- 全局配置 ----------
IMAGE_DIR = ""          # 图片文件夹路径，通过命令行参数传入
STUDENTS_FILE = ""      # 学生名单文件路径，通过命令行参数传入
ASSIGNMENTS_FILE = "assignments.json"   # 分配结果保存文件
RESULTS_DIR = "results"                 # 学生上传的 JSON 结果存放根目录
SUPPORTED_IMG_EXT = ('.jpg', '.jpeg', '.png')
LAST_PUSH_FILE = "last_push_times.json"
last_push_times = {}    # 格式：{"张三": "2025-04-01T14:35:22", ...}

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
def load_last_push_times():
    global last_push_times
    if os.path.exists(LAST_PUSH_FILE):
        try:
            with open(LAST_PUSH_FILE, 'r', encoding='utf-8') as f:
                last_push_times = json.load(f)
            print(f"✅ 已加载最后推送时间记录 ({len(last_push_times)} 条)")
        except Exception as e:
            print(f"⚠️ 读取 {LAST_PUSH_FILE} 失败: {e}")
            last_push_times = {}
    else:
        last_push_times = {}

def save_last_push_times():
    with open(LAST_PUSH_FILE, 'w', encoding='utf-8') as f:
        json.dump(last_push_times, f, ensure_ascii=False, indent=2)

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
    # 记录最后推送时间
    last_push_times[name] = datetime.now().isoformat()
    save_last_push_times()

    return jsonify({"status": "ok"})

@app.route('/reassign', methods=['POST'])
def reassign():
    """
    改派：将一张图片从 A 学生转给 B 学生。
    请求体 JSON: {"image": "cat.jpg", "from_student": "张三", "to_student": "李四"}
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"status": "error", "message": "请求体必须为 JSON"}), 400

    image = data.get('image', '').strip()
    from_stu = data.get('from_student', '').strip()
    to_stu = data.get('to_student', '').strip()

    # 1. 参数完整性
    if not image or not from_stu or not to_stu:
        return jsonify({"status": "error", "message": "缺少必要参数 (image, from_student, to_student)"}), 400

    # 2. 图片是否存在（全局图片池）
    if image not in image_files:
        return jsonify({"status": "error", "message": f"图片 '{image}' 不在图片库中"}), 400

    # 3. 学生是否合法（必须在名单中，且不能相同）
    if from_stu not in assignments or to_stu not in assignments:
        return jsonify({"status": "error", "message": "学生姓名不在名单中"}), 403
    if from_stu == to_stu:
        return jsonify({"status": "error", "message": "不能将图片改派给同一个学生"}), 400

    # 4. 图片当前是否属于 from_student
    if image not in assignments[from_stu]:
        return jsonify({"status": "error", "message": f"图片 '{image}' 不属于学生 {from_stu}"}), 400

    # 5. 防止 to_student 列表中已存在该图片（重复分配）
    if image in assignments[to_stu]:
        return jsonify({"status": "error", "message": f"学生 {to_stu} 已拥有图片 '{image}'"}), 400

    # 6. 执行改派：从 A 移除，加入 B
    assignments[from_stu].remove(image)
    assignments[to_stu].append(image)

    # 7. 将更新后的 assignments 写回文件
    with open(ASSIGNMENTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(assignments, f, ensure_ascii=False, indent=2)

    # 8. 检查是否存在已上传的标注文件，返回警告信息
    warning = None
    # 假设 JSON 文件与图片基本名相同
    base_name = os.path.splitext(image)[0]
    from_student_dir = get_student_dir(from_stu)
    possible_json = os.path.join(from_student_dir, base_name + '.json')
    if os.path.isfile(possible_json):
        warning = (f"学生 {from_stu} 已为该图片上传标注文件 ({base_name}.json)，"
                   f"文件仍保留在其目录下，请手动处理")

    return jsonify({
        "status": "ok",
        "message": f"已将 '{image}' 从 {from_stu} 改派给 {to_stu}",
        "warning": warning
    })

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

        assigned_images = assignments.get(name, [])   # 原始文件名列表
        return jsonify({
            "uploaded": uploaded,
            "unuploaded": total - uploaded,
            "total": total,
            "assigned_images": assigned_images        # 新增
        })

# ---------- 前端页面 ----------
@app.route('/dashboard')
def dashboard():
    """教师端可视化面板"""
    return render_template('dashbord.html')

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

        last_push = last_push_times.get(student) # 可能为 None

        overview["students"].append({
            "name": student,
            "total": total,
            "uploaded": uploaded,
            "images": images,                   # 原始图片文件名列表，如 ["cat.jpg","dog.png"]
            "uploaded_images": uploaded_images, # 已上传的图片基本名列表
            "last_push": last_push              # 最后提交时间，ISO 格式字符串或 null
        })

    overview["total_overall"] = {
        "total": total_all,
        "uploaded": uploaded_all
    }
    return jsonify(overview)

@app.route("/health")
def health_check():
    """健康检查端点，用于监控"""
    return jsonify({'status': 'ok'}), 200

# ---------- 启动入口 ----------

# 处理命令行参数
if len(sys.argv) != 3:
    print("用法: python server.py <图片文件夹> <学生名单文件>")
    print("示例: python server.py ./Images students.txt")
    sys.exit(1)

IMAGE_DIR = sys.argv[1]
STUDENTS_FILE = sys.argv[2]

# 初始化：加载名单、图片、分配
load_students()
load_images()
assign_images()
load_last_push_times()  # 参考https://chat.deepseek.com/share/qudm5z8j7ut0ez04wz

# 确保 results 根目录存在
os.makedirs(RESULTS_DIR, exist_ok=True)

print("\n🚀 服务器启动，监听 0.0.0.0:12010 ...")
os.makedirs(RESULTS_DIR, exist_ok=True)

# 创建 Gevent WSGI 服务器
from gevent.pywsgi import WSGIServer
http_server = WSGIServer(('0.0.0.0', 12010), 
                            app,
                            )
print("\n🚀 Gevent 服务器启动，监听 0.0.0.0:12010 ...")
http_server.serve_forever()