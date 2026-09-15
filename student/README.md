# ImageLabelTS 学生端客户端（student）

基于 **.NET 10 / Windows Forms** 的桌面客户端，供学生登录、下载标注任务、上传标注结果并查看个人进度。

## 技术栈

| 项目 | 说明 |
|------|------|
| 框架 | .NET 10 (`net10.0-windows`)，WinForms |
| 输出类型 | `WinExe` |
| 平台 | `AnyCPU;x64` |
| 依赖 | `Newtonsoft.Json` 13.0.4 |
| 网络 | `HttpClient`（Bearer Token 认证） |

## 构建与运行

```bash
cd student
dotnet build
dotnet run
```

也可使用 Visual Studio 打开 `student.slnx`。构建产物位于 `bin/<Platform>/<Configuration>/net10.0-windows/`。

## 界面功能

主窗体（`MainForm`）提供以下操作：

| 按钮/菜单 | 说明 |
|-----------|------|
| **登录 / 切换用户** | 弹出登录窗口，成功后自动刷新状态 |
| **拉取任务** | 下载任务 ZIP 并解压到本地 `workshop` 目录 |
| **推送标注** | 扫描 `workshop` 下的 `.json` 并上传（自动跳过未修改文件） |
| **刷新状态** | 查询服务器，更新进度条与明细表格 |
| **工具 → 自交检测** | 调用 `Check_LabelMe.ps1` 检查标注多边形是否自交 |
| **工具 → 更新** | 从更新服务下载新版客户端并自动重启 |

明细表格列：`图片名` → `本地状态（存在/缺失）` → `远端状态（已上传时间 / 未上传）`。

## 配置文件 `config.json`

位于程序运行目录（与 `.exe` 同级）：

```json
{
    "server_url": "https://imagelabelts.dpdns.org",
    "update_server_url": "https://update.imagelabelts.dpdns.org/download"
}
```

| 字段 | 说明 |
|------|------|
| `server_url` | 教师端服务地址 |
| `update_server_url` | 更新服务的下载端点（客户端会再拼接 `/update_script`） |

> 若文件不存在，程序会**自动创建**一份默认配置（`http://localhost:12010`）并提示修改后重启。

## 与服务器的交互

| 操作 | 请求 | 说明 |
|------|------|------|
| 登录 | `POST {server_url}/login` | 提交 `{name, password}`，返回 `token` 与 `task_count` |
| 拉取 | `GET {server_url}/pull` | 携带 `Authorization: Bearer <token>`，返回 ZIP |
| 推送 | `POST {server_url}/push` | `multipart/form-data`，字段名 `file` |
| 状态 | `GET {server_url}/status` | 返回 `uploaded / unuploaded / total / assigned_images / uploaded_details` |

### 增量上传

推送前先调用 `/status`，比较本地文件与 `uploaded_details[base].hash`（MD5）。若哈希一致则**跳过**该文件，仅上传有变化的标注。上传结束后弹出统计：`成功 / 跳过 / 失败` 数量。

### 本地工作目录

```
<程序目录>/
├── config.json               # 配置文件
├── Check_LabelMe.ps1         # 自交检测脚本
└── workshop/                 # 拉取的任务与标注文件
    ├── image1.jpg
    ├── image1.json
    └── ...
```

- 拉取时会**先清空** `workshop` 再解压，并删除不属于当前学生任务的多余 `.json`。
- 推送时会忽略不在任务列表中的文件（服务端也会二次校验任务归属）。

## 目录结构

```
student/
├── Program.cs                # 入口，启动 MainForm
├── Form1.cs                  # 主窗体逻辑
├── Form1.Designer.cs / .resx
├── LoginForm.cs              # 登录窗口（类名 Login_Form）
├── LoginForm.Designer.cs / .resx
├── Properties/               # 资源（Resources.resx）
├── student.csproj
└── bin/x64/Debug/
    ├── config.json           # 运行时配置示例
    └── Check_LabelMe.ps1     # 自交检测脚本
```

## 自交检测脚本 `Check_LabelMe.ps1`

扫描 `./workshop` 下所有 `.json`，对每个 shape 的顶点序列做**线段相交判断**（含端点共线情形），用于发现标注多边形自交。包含容差 `1e-9`。

在工作目录下独立运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\Check_LabelMe.ps1
```

## 注意事项

- 客户端**不保存 Token 到磁盘**（当前实现仅在内存中维护），关闭程序后需重新登录。
- `Update_toolStripMenuItem_Click` 中读取的 `config.json` 使用**相对路径**，因此程序的工作目录必须为可执行文件所在目录。
- 更新流程会立即退出进程并由 `update.ps1` 接管，请在更新前保存本地标注。
- 文档 `docs/client_manual.md` 描述的是命令行版本的客户端行为（`login/pull/push/clean/update`），与本图形客户端在交互方式上存在差异，请注意区分。
