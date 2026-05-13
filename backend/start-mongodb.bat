@echo off
chcp 65001 >nul 2>nul

where mongod >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 未在系统 PATH 中找到 mongod。
    echo 请先安装 MongoDB 并将其 bin 目录添加到系统环境变量中。
    echo 示例路径: D:\mongodb-windows-x86_64-8.2.6\mongodb-win32-x86_64-windows-8.2.6\bin
    pause
    exit /b 1
)

cd /d "%~dp0"

if not exist mongo-data (
    echo 正在创建数据目录 mongo-data ...
    mkdir mongo-data
)

if not exist mongo-log (
    echo 正在创建日志目录 mongo-log ...
    mkdir mongo-log
)

echo 正在启动 MongoDB ...
mongod --config mongo.conf
