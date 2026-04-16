@echo off
REM 安装期刊每周更新任务
REM 每周一早上8点自动检查新论文

set SCRIPT_DIR=%~dp0
set PYTHON_EXE=%SCRIPT_DIR%venv\Scripts\python.exe
set UPDATE_SCRIPT=%SCRIPT_DIR%update_journals.py

REM 创建每周一8:00运行的任务
schtasks /create /tn "ArXiv-Journal-Update" /tr "\"%PYTHON_EXE%\" \"%UPDATE_SCRIPT%\"" /sc weekly /d MON /st 08:00 /f

echo.
echo Task installed successfully!
echo.
echo The task will run every Monday at 8:00 AM.
echo To run manually: schtasks /run /tn "ArXiv-Journal-Update"
echo To delete: schtasks /delete /tn "ArXiv-Journal-Update"
echo.
pause
