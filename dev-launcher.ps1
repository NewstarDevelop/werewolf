<#
.SYNOPSIS
    Werewolf 项目一键开发启动脚本
    同时启动后端 (uvicorn) + 前端 (vite dev server)
.DESCRIPTION
    - 后端: http://127.0.0.1:8000  (health: /health)
    - 前端: http://127.0.0.1:5173
    - 按 Ctrl+C 停止所有服务
#>

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"

# ---- 检测可用工具 ----
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Warning "[!] 找不到虚拟环境 Python: $python"
    Write-Warning "    尝试使用系统 python..."
    $python = "python"
}

# npm find
$npm = "C:\Program Files\nodejs\npm.cmd"
if (-not (Test-Path $npm)) {
    $npm = (Get-Command npm -ErrorAction SilentlyContinue).Source
    if (-not $npm) {
        Write-Error "[!] 找不到 npm，请确保 Node.js 已安装"
        exit 1
    }
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Werewolf 开发环境启动" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Python : $python" -ForegroundColor Gray
Write-Host "  npm    : $npm" -ForegroundColor Gray
Write-Host ""

# ---- 1. 启动后端 ----
Write-Host ">>> [1/2] 启动后端 (port 8000) ..." -ForegroundColor Green
$backendJob = Start-Job -ScriptBlock {
    param($py, $dir)
    Set-Location $dir
    & $py -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
} -ArgumentList $python, $backendDir

# ---- 2. 启动前端 ----
Write-Host ">>> [2/2] 启动前端 (port 5173) ..." -ForegroundColor Green
$frontendJob = Start-Job -ScriptBlock {
    param($npm, $dir)
    Set-Location $dir
    & $npm run dev
} -ArgumentList $npm, $frontendDir

# ---- 3. 等待健康检查 ----
Write-Host ""
Write-Host "等待后端就绪..." -ForegroundColor Yellow
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $resp = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -UseBasicParsing -TimeoutSec 2
        if ($resp.StatusCode -eq 200) {
            $ready = $true
            Write-Host "  ✅ 后端就绪! (health: 200)" -ForegroundColor Green
            break
        }
    } catch {}
}
if (-not $ready) {
    Write-Warning "  ⚠️  后端超时未就绪"
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  服务已启动" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  后端 API : http://127.0.0.1:8000" -ForegroundColor White
Write-Host "  后端健康 : http://127.0.0.1:8000/health" -ForegroundColor White
Write-Host "  前端 UI  : http://127.0.0.1:5173" -ForegroundColor White
Write-Host ""
Write-Host "  按 Ctrl+C 停止所有服务" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Cyan

# ---- 4. 等待用户中断 ----
try {
    # 保持运行，等待 Ctrl+C
    while ($true) {
        Start-Sleep -Seconds 5
        # 检查job是否还活着
        $bj = Receive-Job -Job $backendJob -Keep -ErrorAction SilentlyContinue
        $fj = Receive-Job -Job $frontendJob -Keep -ErrorAction SilentlyContinue
        # 简单健康检查
        try {
            $null = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -UseBasicParsing -TimeoutSec 2
        } catch {
            Write-Warning "[!] 后端似乎已停止，正在重启..."
            $backendJob = Start-Job -ScriptBlock {
                param($py, $dir)
                Set-Location $dir
                & $py -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
            } -ArgumentList $python, $backendDir
        }
    }
} finally {
    Write-Host ""
    Write-Host ">>> 正在停止所有服务 ..." -ForegroundColor Yellow
    Stop-Job $backendJob -ErrorAction SilentlyContinue
    Stop-Job $frontendJob -ErrorAction SilentlyContinue
    Remove-Job $backendJob -ErrorAction SilentlyContinue
    Remove-Job $frontendJob -ErrorAction SilentlyContinue
    Write-Host "  ✅ 已停止" -ForegroundColor Green
}
