@echo off
chcp 65001 >nul
REM ============================================
REM   arXiv 论文推荐系统 - 完整安装脚本
REM ============================================

echo.
echo  ╔════════════════════════════════════════════════════════════╗
echo  ║       arXiv 论文推荐系统 - 安装程序                        ║
echo  ║       为统计学和机器学习研究者设计                          ║
echo  ╚════════════════════════════════════════════════════════════╝
echo.

REM 检查 Python 版本
echo [1/5] 检查 Python 环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python
    echo.
    echo 请先安装 Python 3.9 或更高版本:
    echo https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo       ✓ Python %PYVER% 已安装

REM 检查 pip
echo.
echo [2/5] 检查 pip...
pip --version >nul 2>&1
if errorlevel 1 (
    echo [错误] pip 未找到
    pause
    exit /b 1
)
echo       ✓ pip 已就绪

REM 创建虚拟环境（可选）
echo.
echo [3/5] 安装依赖包...
echo       这可能需要几分钟，请耐心等待...
echo.

REM 检查是否有虚拟环境
if exist "venv\Scripts\activate.bat" (
    echo       检测到已有虚拟环境，正在激活...
    call venv\Scripts\activate.bat
) else (
    echo       正在创建虚拟环境...
    python -m venv venv
    call venv\Scripts\activate.bat
)

REM 安装依赖
pip install -r requirements.txt -q
if errorlevel 1 (
    echo [警告] 部分依赖安装失败，继续安装...
)
echo       ✓ 依赖安装完成

REM 创建必要的目录
echo.
echo [4/5] 创建目录结构...
if not exist "cache" mkdir cache
if not exist "cache\journals" mkdir cache\journals
if not exist "history" mkdir history
if not exist "logs" mkdir logs
echo       ✓ 目录创建完成

REM 运行配置向导
echo.
echo [5/5] 启动配置向导...
echo.
echo ════════════════════════════════════════════════════════════
echo   接下来将引导您完成个性化配置
echo   包括：选择研究方向、设置关键词、配置偏好
echo ════════════════════════════════════════════════════════════
echo.

pause

python -m installer.cli_wizard

echo.
echo ════════════════════════════════════════════════════════════
echo   安装完成！
echo ════════════════════════════════════════════════════════════
echo.
echo   启动方式:
echo     1. 启动 Web 服务器:  start_server.bat
echo     2. 访问界面:        http://localhost:5555
echo     3. 获取推荐:        run_daily.bat
echo.
echo   修改配置:
echo     - 重新运行配置向导:  setup.bat
echo     - Web 界面设置:     http://localhost:5555/settings
echo.

pause
