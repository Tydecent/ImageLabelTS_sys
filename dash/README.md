# ImageLabelTS 进度面板（dash）

面向**学生**与**管理员**的 Web 进度看板。本服务本身不存储业务数据，而是作为代理层读取教师端服务的 `/api/overview`，再按登录用户的角色过滤后呈现。

## 技术栈

- **后端**：Python 3.8+，Flask（基于 Session 的登录态）
- **前端**：原生 HTML + JavaScript（`fetch('/api/data')` 轮询/刷新）
- **依赖**：`Flask`、`requests`、`bcrypt`

## 功能

| 角色 | 页面 | 可见内容 |
|------|------|----------|
| 学生 | `/student` | 仅自己的任务进度（总任务数 / 已上传数 / 上传明细） |
| 管理员 | `/admin` | 全部学生的任务进度与总体统计 |

- 用户数据来源于两份 JSON 文件：`students.json`（角色 `student`）与 `admin.json`（角色 `admin`）。
- 登录时使用 **bcrypt** 校验密码哈希。
- 管理员可直接查看 `total_overall` 汇总；学生数据在服务端完成过滤，不会下发他人信息。

## 快速开始

```bash
cd dash
pip install -r requirements.txt
python server.py
```

默认监听 `0.0.0.0:12018`（`debug=True`，生产环境请关闭）。

## 配置

| 配置项 | 位置 | 说明 |
|--------|------|------|
| `SECRET_KEY` | 环境变量 | Flask Session 签名密钥；未设置时使用 `os.urandom(24)`（每次重启失效） |
| `OVERVIEW_API` | `server.py` 顶部常量 | 教师端概览接口地址，默认 `https://localhost:12010/api/overview` |

### 数据文件

`students.json`：

```json
[
  { "name": "张三", "password_hash": "$2b$12$..." }
]
```

`admin.json`：

```json
[
  { "name": "admin", "password_hash": "$2b$12$..." }
]
```

> 两个文件均不会纳入版本控制（`.gitignore` 忽略 `*.json`），部署时需自行准备。

## 路由

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `GET` | `/` | — | 依据登录状态与角色跳转 |
| `GET/POST` | `/login` | — | 登录页与登录处理 |
| `GET` | `/logout` | — | 清除 Session |
| `GET` | `/student` | 学生 | 学生面板页 |
| `GET` | `/admin` | 管理员 | 管理员面板页 |
| `GET` | `/api/data` | 登录 | 代理并过滤教师端 `/api/overview` 数据 |

## 目录结构

```
dash/
├── server.py          # Flask 应用
├── requirements.txt
├── students.json      # 学生账号（需自行准备）
├── admin.json         # 管理员账号（需自行准备）
└── templates/
    ├── login.html
    ├── student.html
    └── admin.html
```

## 注意事项

- **用户列表在进程启动时一次性加载**，修改 `students.json` / `admin.json` 后需重启服务才能生效。
- `OVERVIEW_API` 默认使用 `https://localhost:12010`，而教师端 `server.py` 默认以 HTTP 启动。请根据实际部署（反向代理或协议）调整该常量，否则 `/api/data` 会返回 `无法获取外部数据`。
- 生产环境建议设置固定的 `SECRET_KEY`，并使用正式 WSGI 服务器（如 gunicorn）替代内置服务器。
