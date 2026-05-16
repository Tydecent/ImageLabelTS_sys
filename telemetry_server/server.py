import os
import logging
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge

# 配置
UPLOAD_ENDPOINT = '/upload'              # 可配置的上传端点，默认 /upload
UPLOAD_FOLDER = 'uploads'                # 文件保存目录
MAX_CONTENT_LENGTH = 10 * 1024 * 1024    # 10MB 文件大小限制
ALLOWED_EXTENSIONS = {'log'}             # 允许的文件扩展名

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# 确保上传目录存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 配置日志（用于服务端记录，非必须）
logging.basicConfig(level=logging.INFO)

def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(e):
    """处理文件超过限制大小的异常，返回 413 并符合 API 格式"""
    return jsonify({
        "status": "error",
        "message": f"文件超过服务器限制大小（最大 {MAX_CONTENT_LENGTH // (1024*1024)}MB）"
    }), 413

@app.route(UPLOAD_ENDPOINT, methods=['POST'])
def upload_log():
    """
    处理日志文件上传
    期望 multipart/form-data，字段：
        log_file: 文件（必需）
        client_name: 字符串（可选）
        timestamp: 字符串（可选）
    """
    # 检查是否包含 log_file 字段
    if 'log_file' not in request.files:
        return jsonify({
            "status": "error",
            "message": "缺少 log_file 字段"
        }), 400

    file = request.files['log_file']

    # 检查文件是否为空（用户未选择文件或上传空文件）
    if file.filename == '':
        return jsonify({
            "status": "error",
            "message": "未选择文件"
        }), 400

    # 可选参数，记录但不进行业务处理
    client_name = request.form.get('client_name', '')
    timestamp = request.form.get('timestamp', '')

    # 安全处理文件名并校验扩展名
    filename = secure_filename(file.filename)
    if not allowed_file(filename):
        return jsonify({
            "status": "error",
            "message": "无效的文件类型，请上传 .log 文件"
        }), 400

    # 构造保存路径并保存文件
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    try:
        file.save(save_path)
        file_size = os.path.getsize(save_path)
    except Exception as e:
        app.logger.error(f"保存文件失败: {e}")
        return jsonify({
            "status": "error",
            "message": "服务器内部错误，保存文件失败"
        }), 500

    # 可选：在服务端记录接收到的元数据（仅供调试）
    app.logger.info(f"收到文件: {filename}, 大小: {file_size} bytes, client_name: {client_name}, timestamp: {timestamp}")

    return jsonify({
        "status": "ok",
        "message": "日志已接收",
        "filename": filename,
        "size": file_size
    }), 200

@app.route('/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=12015, debug=False)