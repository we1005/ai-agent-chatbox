@echo off
chcp 65001 >nul
REM ==========================================================================
REM 双击入口：绕过 PowerShell 执行策略限制，拉起 start-all.ps1
REM ==========================================================================
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0start-all.ps1"
