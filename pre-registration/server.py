#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import bcrypt
import json
import os
from flask import Flask, request, render_template, jsonify

app = Flask(__name__)

STUDENTS_FILE = 'students.json'

def load_students():
    """加载现有的学生数据，如果文件不存在则返回空列表"""
    if not os.path.exists(STUDENTS_FILE):
        return []
    with open(STUDENTS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_students(students):
    """将学生列表保存到 JSON 文件"""
    with open(STUDENTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(students, f, ensure_ascii=False, indent=4)

@app.route('/')
def register_form():
    """显示注册页面"""
    return render_template('register.html')

@app.route('/register', methods=['POST'])
def register():
    # 获取表单数据
    name = request.form.get('name', '').strip()
    password = request.form.get('password', '')
    confirm_password = request.form.get('confirm_password', '')

    # 验证输入
    if not name:
        return jsonify({'success': False, 'message': '姓名不能为空'}), 400
    if not password:
        return jsonify({'success': False, 'message': '密码不能为空'}), 400
    if password != confirm_password:
        return jsonify({'success': False, 'message': '两次输入的密码不一致'}), 400

    # 检查是否已注册
    students = load_students()
    if any(s['name'] == name for s in students):
        return jsonify({'success': False, 'message': '该姓名已注册'}), 400

    # 生成 bcrypt 哈希密码
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    password_hash = hashed.decode('utf-8')

    # 保存新学生
    students.append({
        'name': name,
        'password_hash': password_hash
    })
    save_students(students)

    return jsonify({'success': True, 'message': f'学生 {name} 注册成功！'})

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=12016)