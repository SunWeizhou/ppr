@echo off
chcp 65001 >nul
REM 启动 Web 服务器

echo 启动 arXiv 论文推荐系统...
echo 访问地址: http://localhost:5555
echo 按 Ctrl+C 停止服务器
echo.

REM 切换到项目根目录
cd /d "%~dp0"
cd ..

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

python web_server.py
