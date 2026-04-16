@echo off
chcp 65001 >nul
REM 获取每日推荐论文

REM 切换到项目根目录（脚本在 installer/ 子目录）
cd /d "%~dp0"
cd ..

set KMP_DUPLICATE_LIB_OK=TRUE

REM 使用虚拟环境或系统 Python
if exist "venv\Scripts\python.exe" (
    set PYTHON_CMD=venv\Scripts\python.exe
    set PYTHONW_CMD=venv\Scripts\pythonw.exe
) else (
    set PYTHON_CMD=python
    set PYTHONW_CMD=pythonw
)

REM 启动 Web 服务器（后台）
start "" %PYTHONW_CMD% web_server.py
timeout /t 2 /nobreak >nul

REM 获取推荐
set PYTHONIOENCODING=utf-8
%PYTHON_CMD% arxiv_recommender_v5.py

REM 打开浏览器
start "" "http://localhost:5555"
