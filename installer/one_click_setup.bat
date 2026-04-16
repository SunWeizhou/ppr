@echo off
chcp 65001 >nul
REM ============================================
REM   arXiv 论文推荐系统 - 一键配置
REM ============================================

setlocal EnableDelayedExpansion

echo.
echo  ╔═════════════════════════════════════════════════════════╗
echo  ║                                              ║
echo  ║         arXiv 论文推荐系统 - 一键配置          ║
echo  ║                                              ║
echo  ╚═════════════════════════════════════════════════════════╝
echo.

REM 切换到脚本所在目录
cd /d "%~dp0"
cd ..

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [错误] 未检测到 Python
    echo  请先安装 Python 3.9+ : https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

echo [1/4] 检测 Python...OK!

REM 检查是否首次运行
if not exist "user_profile.json" (
    echo.
    echo  [2/4] 首次运行， 启动配置向导...
    echo.
    echo  正在打开 Web 配置界面...
    echo  请在浏览器中打开: http://localhost:5555/setup
    echo.
    echo  配置完成后， 此窗口会自动继续...
    echo.

    REM 启动临时服务器进行配置
    start /b python web_server.py
    timeout /t 60 /nobreak >nul

    echo.
    echo  如果浏览器没有自动打开， 请手动访问:
    echo  http://localhost:5555/setup
    echo.
    echo  等待配置完成...
    echo.

    REM 等待配置文件创建
    :wait_for_config
    if exist "user_profile.json" goto :config_done

    echo  仍在等待配置...
    timeout /t 5 /nobreak >nul
    goto :wait_for_config

    :config_done
    echo.
    echo  [OK] 配置完成!
) else (
    echo [OK] 检测到已有配置
)

REM 检查虚拟环境
echo.
echo [3/4] 检查依赖...

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo  创建虚拟环境...
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install -r requirements.txt -q
)

echo [OK] 依赖就绪

REM 创建必要目录
echo.
echo [4/4] 创建目录...
if not exist "cache" mkdir cache
if not exist "cache\journals" mkdir cache\journals
if not exist "history" mkdir history
if not exist "logs" mkdir logs
echo [OK] 目录创建完成

REM 完成
echo.
echo  ══════════════════════════════════════════════════════════
echo  配置完成！
echo  ══════════════════════════════════════════════════════════
echo.
echo  启动方式:
echo    1. 启动服务器:  双击 start_server.bat
echo    2. 获取推荐:    双击 run_daily.bat
echo    3. 访问界面:    http://localhost:5555
echo.
echo  按任意键启动服务器...
pause >nul

REM 启动服务器
start python web_server.py
timeout /t 3 /nobreak >nul
start http://localhost:5555
