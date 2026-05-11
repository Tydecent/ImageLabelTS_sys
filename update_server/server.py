#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
客户端更新服务器
提供 /download 端点，返回 ./update_package.zip 文件
"""

import os
from flask import Flask, send_file, abort

app = Flask(__name__)

# 配置文件路径（与脚本同目录下的 update_package.zip）
ZIP_FILE_PATH = os.path.join(os.path.dirname(__file__), "update_package.zip")

@app.route('/download', methods=['GET'])
def download_update():
    """客户端调用此接口下载最新客户端包"""
    if not os.path.exists(ZIP_FILE_PATH):
        abort(404, description="更新包不存在，请联系管理员")
    
    # 返回 zip 文件，作为附件下载（客户端会解压到当前目录）
    return send_file(
        ZIP_FILE_PATH,
        mimetype='application/zip',
        as_attachment=True,
        download_name='client_update.zip'   # 客户端看到的文件名，可随意
    )

@app.route('/health', methods=['GET'])
def health():
    """健康检查端点，可选"""
    return {"status": "ok"}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=12014, debug=False)