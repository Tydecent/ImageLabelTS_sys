# locustfile.py
from locust import HttpUser, task, between

class TeacherUser(HttpUser):
    wait_time = between(0.5, 2)  # 模拟思考时间

    def on_start(self):
        # 任选一个学生（实际测试时最好随机取已存在的学生）
        self.student_name = "黄浦巍"   # 或者从预取的学生列表中轮询

    @task
    def pull_task(self):
        # 注意：服务器启用了 HTTPS，需要 verify=False 或提供证书
        with self.client.get(f"/pull?name={self.student_name}",
                             verify=False,
                             catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"Unexpected status {response.status_code}")
            # 检查 ZIP 内容长度（可选）
            if len(response.content) < 100:
                response.failure("ZIP too small")