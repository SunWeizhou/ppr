@echo off
chcp 65001 >nul
set KMP_DUPLICATE_LIB_OK=TRUE

echo 正在停止 Web 服务器...
taskkill /F /IM python.exe 2>nul
timeout /t 3 /nobreak >nul

echo 正在启动 Web 服务器...
cd /d "%~dp0"

REM 使用虚拟环境或系统 Python
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe web_server.py
) else (
    python web_server.py
)

pause
