@echo off
REM ============================================================
REM  FableDan 掼蛋 AI - 网页对战 UI 启动器
REM  启动服务器并自动打开浏览器
REM ============================================================
chcp 65001 >nul
title FableDan 掼蛋 AI - UI 服务器
cd /d "%~dp0"

REM ---- 检查虚拟环境 ----
if not exist ".venv\Scripts\python.exe" (
    echo [错误] 未找到 .venv,请先运行:  python -m venv .venv
    echo        然后: .venv\Scripts\pip install numpy fastapi uvicorn torch
    pause
    exit /b 1
)

REM ---- 检查端口占用 ----
set PORT=8010
netstat -ano | findstr ":%PORT% " | findstr LISTENING >nul 2>&1
if %errorlevel%==0 (
    echo [提示] 端口 %PORT% 已被占用,改用 8011。
    set PORT=8011
)

REM ---- 延迟 1 秒后打开浏览器(等服务器就绪) ----
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://localhost:%PORT%"

REM ---- 启动服务器 ----
echo 正在启动 FableDan UI 服务器...
echo 服务器地址: http://localhost:%PORT%
echo 按 Ctrl+C 停止服务器,关闭本窗口即可退出。
echo.
.venv\Scripts\python.exe -m uvicorn ui.server:app --host 0.0.0.0 --port %PORT%

pause