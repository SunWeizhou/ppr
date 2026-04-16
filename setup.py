@echo off
chcp 65001 >nul
REM arXiv 论文推荐系统 - 配置向导启动脚本

echo.
echo ========================================
echo   arXiv 论文推荐系统 - 配置向导
echo ========================================
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.9+
    pause
    exit /b 1
)

REM 运行配置向导
python -m installer.cli_wizard

echo.
pause
