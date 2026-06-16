import json
import requests
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import bcrypt
from functools import wraps
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))

# ---------- 加载用户数据 ----------
def load_users():
    users = {}
    # 加载学生
    try:
        with open('students.json', 'r', encoding='utf-8') as f:
            students = json.load(f)
            for s in students:
                users[s['name']] = {'password_hash': s['password_hash'], 'role': 'student'}
    except FileNotFoundError:
        print("Warning: students.json not found")
    # 加载管理员
    try:
        with open('admin.json', 'r', encoding='utf-8') as f:
            admins = json.load(f)
            for a in admins:
                users[a['name']] = {'password_hash': a['password_hash'], 'role': 'admin'}
    except FileNotFoundError:
        print("Warning: admin.json not found")
    return users

USERS = load_users()

# ---------- 外部 API 地址 ----------
OVERVIEW_API = "https://localhost:12010/api/overview"

# ---------- 装饰器：需要登录 ----------
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ---------- 路由 ----------
@app.route('/')
def index():
    if 'username' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('student_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            return render_template('login.html', error='请输入用户名和密码')
        user = USERS.get(username)
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            session['username'] = username
            session['role'] = user['role']
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('student_dashboard'))
        else:
            return render_template('login.html', error='用户名或密码错误')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/student')
@login_required
def student_dashboard():
    if session.get('role') != 'student':
        return "Access Denied", 403
    return render_template('student.html', username=session['username'])

@app.route('/admin')
@login_required
def admin_dashboard():
    if session.get('role') != 'admin':
        return "Access Denied", 403
    return render_template('admin.html', username=session['username'])

# ---------- API：获取概览数据（根据角色过滤） ----------
@app.route('/api/data')
@login_required
def get_data():
    try:
        resp = requests.get(OVERVIEW_API, timeout=5)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return jsonify({'error': f'无法获取外部数据: {str(e)}'}), 500

    # 复制数据，避免修改原始
    result = {
        'students': data.get('students', []),
        'total_overall': data.get('total_overall', {})
    }

    role = session.get('role')
    username = session.get('username')

    if role == 'student':
        # 过滤出当前学生
        filtered = [s for s in result['students'] if s.get('name') == username]
        result['students'] = filtered
        # 若没有该学生，返回空，但保留整体进度
    # 管理员：直接返回全部

    return jsonify(result)

# ---------- 启动 ----------
if __name__ == '__main__':
    app.run(debug=True, port=12018)