#!/bin/bash

# 显示帮助信息
show_help() {
    echo "用法: $0 [选项]"
    echo "选项:"
    echo "  -d, --daemon    使用 nohup 在后台运行 Gunicorn"
    echo "  -h, --help      显示此帮助信息"
    echo ""
    echo "默认行为: 前台运行 Gunicorn（不产生 nohup.out）"
}

# 初始化后台标志
DAEMON_MODE=0

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case "$1" in
        -d|--daemon)
            DAEMON_MODE=1
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "错误: 未知参数 '$1'"
            show_help
            exit 1
            ;;
    esac
done

# 激活虚拟环境
source ./venv/bin/activate

# 设置环境变量
export IMAGE_DIR="./Images"
export STUDENTS_FILE="students.txt"

# 构建 Gunicorn 基础命令
GUNICORN_CMD="gunicorn -w 4 -k gevent --worker-connections 1000 -b 0.0.0.0:12010 --timeout 120 server:app"

# 根据后台标志执行
if [ $DAEMON_MODE -eq 1 ]; then
    echo "使用 nohup 后台运行 Gunicorn..."
    nohup $GUNICORN_CMD &
    echo "Gunicorn 已在后台启动，PID: $!"
else
    echo "前台运行 Gunicorn（按 Ctrl+C 停止）..."
    exec $GUNICORN_CMD
fi