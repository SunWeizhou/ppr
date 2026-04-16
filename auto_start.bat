@echo off
chcp 65001 >nul
echo ========================================
echo arXiv Daily - 自动启动
echo ========================================

REM 切换到脚本所在目录
cd /d "%~dp0"

REM 设置环境变量解决 OpenMP 冲突
set KMP_DUPLICATE_LIB_OK=TRUE

REM 使用虚拟环境或系统 Python
if exist "venv\Scripts\python.exe" (
    set PYTHON_CMD=venv\Scripts\python.exe
    set PYTHONW_CMD=venv\Scripts\pythonw.exe
) else (
    set PYTHON_CMD=python
    set PYTHONW_CMD=pythonw
)

REM 使用虚拟环境或系统 Python
if exist "venv\Scripts\python.exe" (
    set PYTHON_CMD=venv\Scripts\python.exe
    set PYTHONW_CMD=venv\Scripts\pythonw.exe
) else (
    set PYTHON_CMD=python
    set PYTHONW_CMD=pythonw
)

REM 等待网络连接
echo 等待网络连接...
ping -n 1 arxiv.org >nul 2>&1
if errorlevel 1 (
    echo 网络未连接，等待10秒后重试...
    timeout /t 10 /nobreak >nul
    ping -n 1 arxiv.org >nul 2>&1
)

REM 运行推荐
echo 运行论文推荐...
%PYTHON_CMD% arxiv_recommender_v5.py

REM 启动Web服务
echo 启动Web服务...
start /min %PYTHONW_CMD% web_server.py

REM 等待服务启动
timeout /t 3 /nobreak >nul

REM 打开浏览器
echo 打开浏览器...
start http://localhost:5555

echo ========================================
echo 完成！
echo ========================================
