#!/bin/bash
source ./venv/bin/activate
export IMAGE_DIR="./Images"
export STUDENTS_FILE="students.txt"
gunicorn -w 4 -k gevent --worker-connections 1000 -b 0.0.0.0:12010 --timeout 120 server:app