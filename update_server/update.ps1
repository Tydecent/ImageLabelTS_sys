<#
.SYNOPSIS
    更新脚本：解压 update.zip 覆盖当前目录，然后重新启动主程序并自清理。
.DESCRIPTION
    由主程序 ImageLabelTS.client.exe 在下载完 update.zip 后启动。
    脚本会等待主程序退出（必要时强制结束），解压更新包，删除压缩包，
    启动新版本主程序，最后删除自身。
#>

param(
    [string]$AppName = "ImageLabelTS.client.exe",
    [string]$ZipFile = "update.zip",
    [int]$WaitSeconds = 3
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$AppPath = Join-Path $ScriptDir $AppName
$ZipPath = Join-Path $ScriptDir $ZipFile

# 1. 等待主程序完全退出（确保文件解锁）
Start-Sleep -Seconds $WaitSeconds

# 2. 强制结束残留进程（如果仍在运行）
$processName = [System.IO.Path]::GetFileNameWithoutExtension($AppName)
$proc = Get-Process -Name $processName -ErrorAction SilentlyContinue
if ($proc) {
    $proc | Stop-Process -Force
    Start-Sleep -Seconds 2
}

# 3. 解压更新包，覆盖当前目录所有文件
if (-not (Test-Path $ZipPath)) {
    Write-Error "更新包文件未找到: $ZipPath"
    exit 1
}

Write-Host "正在解压更新包..."
Expand-Archive -Path $ZipPath -DestinationPath $ScriptDir -Force
Write-Host "解压完成。"

# 4. 删除更新包
Remove-Item -Path $ZipPath -Force
Write-Host "更新包已删除。"

# 5. 重新启动应用程序
if (Test-Path $AppPath) {
    Start-Process -FilePath $AppPath -WorkingDirectory $ScriptDir
    Write-Host "已启动新版本应用程序。"
} else {
    Write-Error "未找到应用程序: $AppPath"
    exit 1
}

# 6. 自删除（脚本自身）
Remove-Item -Path $MyInvocation.MyCommand.Definition -Force