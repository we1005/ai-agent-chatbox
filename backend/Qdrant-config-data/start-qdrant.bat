@echo off
chcp 65001 >nul

echo ==============================
echo  Starting Qdrant Vector DB
echo  HTTP : http://localhost:6333
echo  WebUI: http://localhost:6333/dashboard
echo ==============================
echo.

REM 切换到配置目录，使 Qdrant 相对路径解析基于此目录（双重保险）
cd /d "D:\FastAPI-chatbox-langraph-version\backend\Qdrant-config-data"

"D:\qdrant-x86_64-pc-windows-msvc\qdrant.exe" ^
  --config-path "D:\FastAPI-chatbox-langraph-version\backend\Qdrant-config-data\config.yaml"
