# ============================================================================
# 一键启动：MongoDB → Qdrant → 天气 MCP → Backend → Frontend
#
# 按依赖顺序依次在**独立窗口**拉起 5 个服务（前端放最后，因为要等后端先就绪）。
# 每个服务单独一个 PowerShell 窗口 → 方便观察日志、也可 Ctrl+C 单独中止。
# ============================================================================

# ─────────────────────────────────────────────────────────────
# ⚠️  警告（始终先打印）
# ─────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "⚠️  本脚本仅仅适用于开发者的windows电脑环境，各个依赖软件的路径都是硬编码的，你需要对应更改。" -ForegroundColor Yellow
Write-Host ""

$ErrorActionPreference = 'Continue'

# ─────────────────────────────────────────────────────────────
# 硬编码路径 —— 拷到别的机器用时改这一段即可
# ─────────────────────────────────────────────────────────────
$ROOT          = 'D:\FastAPI-chatbox-langraph-version'
$BACKEND       = "$ROOT\backend"
$MCP_DIR       = "$ROOT\Gaode-weather-MCP-server"
$FRONTEND      = "$ROOT\frontend"
$QDRANT_EXE    = 'D:\qdrant-x86_64-pc-windows-msvc\qdrant.exe'
$QDRANT_CONFIG = "$BACKEND\Qdrant-config-data\config.yaml"
$MONGO_CONF    = "$BACKEND\mongo.conf"
$VENV_ACTIVATE = "$BACKEND\venv\Scripts\Activate.ps1"

# ─────────────────────────────────────────────────────────────
# 工具：在新 PowerShell 窗口里跑命令
# ─────────────────────────────────────────────────────────────
function Start-InNewWindow {
    param(
        [Parameter(Mandatory = $true)] [string] $Title,
        [Parameter(Mandatory = $true)] [string] $Command
    )
    # -NoExit：命令结束后窗口保留，方便观察错误 / 日志
    $wrapped = "`$host.UI.RawUI.WindowTitle = '$Title'; Write-Host '=== $Title ===' -ForegroundColor Cyan; $Command"
    Start-Process powershell -ArgumentList '-NoExit', '-Command', $wrapped
}

# ─────────────────────────────────────────────────────────────
# 启动顺序：MongoDB → Qdrant → MCP → Backend → Frontend
# （MongoDB/Qdrant 是后端硬依赖；MCP 非硬依赖但放后端前更快可用；前端最后启）
# ─────────────────────────────────────────────────────────────

Write-Host "[1/5] 启动 MongoDB ..." -ForegroundColor Cyan
Start-InNewWindow 'MongoDB' "Set-Location '$BACKEND'; mongod --config '$MONGO_CONF'"
Start-Sleep -Seconds 2

Write-Host "[2/5] 启动 Qdrant ..." -ForegroundColor Cyan
Start-InNewWindow 'Qdrant' "Set-Location '$BACKEND\Qdrant-config-data'; & '$QDRANT_EXE' --config-path '$QDRANT_CONFIG'"
Start-Sleep -Seconds 2

Write-Host "[3/5] 启动 天气 MCP Server（使用 backend 的 venv，默认端口 8001） ..." -ForegroundColor Cyan
$mcpCmd = "& '$VENV_ACTIVATE'; Set-Location '$MCP_DIR'; python server.py"
Start-InNewWindow 'Weather MCP (port 8001)' $mcpCmd
Start-Sleep -Seconds 3

Write-Host "[4/5] 启动 Backend（FastAPI / uvicorn，端口 8000，带 --reload） ..." -ForegroundColor Cyan
$backendCmd = "& '$VENV_ACTIVATE'; Set-Location '$BACKEND'; uvicorn main:app --reload --reload-dir app"
Start-InNewWindow 'Backend (port 8000)' $backendCmd
Start-Sleep -Seconds 3

Write-Host "[5/5] 启动 Frontend（Vite dev server，端口 5173） ..." -ForegroundColor Cyan
Start-InNewWindow 'Frontend (port 5173)' "Set-Location '$FRONTEND'; npm run dev"

# ─────────────────────────────────────────────────────────────
# 启动完毕提示
# ─────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "==============================================================" -ForegroundColor Green
Write-Host "所有服务已在独立窗口启动：" -ForegroundColor Green
Write-Host "  • MongoDB        → 27017"
Write-Host "  • Qdrant         → 6333           dashboard: http://localhost:6333/dashboard"
Write-Host "  • Weather MCP    → 8001           SSE endpoint: http://127.0.0.1:8001/sse"
Write-Host "  • Backend        → 8000           API docs:     http://localhost:8000/docs"
Write-Host "  • Frontend       → 5173           访问:         http://localhost:5173"
Write-Host "==============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  关闭某个服务：切到对应窗口按 Ctrl+C，或直接关窗。" -ForegroundColor DarkGray
Write-Host ""

Read-Host "按 Enter 关闭此启动器窗口（不影响已启动的服务）"
