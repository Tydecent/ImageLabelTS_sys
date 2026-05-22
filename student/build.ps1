# 切换到脚本所在目录
Set-Location $PSScriptRoot

# 检查是否具有管理员权限
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")

if (-not $isAdmin) {
    Write-Host "正在请求管理员权限..." -ForegroundColor Yellow
    Start-Process PowerShell -Verb RunAs "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    exit
}

Write-Host "已获得管理员权限。" -ForegroundColor Green

# 激活虚拟环境
$venvActivate = Join-Path $PSScriptRoot "..\.venv\Scripts\Activate.ps1"
if (-not (Test-Path $venvActivate)) {
    Write-Error "错误：未找到虚拟环境激活脚本 $venvActivate"
    exit 1
}

Write-Host "正在激活虚拟环境：$venvActivate" -ForegroundColor Cyan
& $venvActivate

# 检查是否安装了 nuitka
if (-not (Get-Command nuitka -ErrorAction SilentlyContinue)) {
    Write-Error "错误：未找到 nuitka，请确认虚拟环境中已安装 (pip install nuitka)"
    exit 1
}

# 执行 Nuitka 编译
Write-Host "开始编译 client.py ..." -ForegroundColor Cyan
nuitka --standalone --onefile --output-dir=./dist ./client.py

# 检查编译结果
if ($LASTEXITCODE -eq 0) {
    Write-Host "编译成功完成！" -ForegroundColor Green
} else {
    Write-Host "编译失败，退出代码：$LASTEXITCODE" -ForegroundColor Red
    exit $LASTEXITCODE
}