@echo off
chcp 65001 >nul
REM ============================================
REM   整理文件夹结构
REM   分成：自己用的 / 给别人用的
REM ============================================

setlocal EnableDelayedExpansion

set PROJECT_ROOT=D:\arxiv_recommender
set DIST_ROOT=D:\arxiv_recommender_dist

echo.
echo  ╔═════════════════════════════════════════════════════════╗
echo  ║            整理文件夹结构                                    ║
echo  ╚═════════════════════════════════════════════════════════╝
echo.

REM ========== 第一步：清理分发文件夹 ==========
echo [1/2] 清理分发文件夹...

REM 删除旧的分发文件夹
if exist "%DIST_ROOT%" rd /s /q "%DIST_ROOT%" 2>nul

REM 创建新的分发文件夹
mkdir "%DIST_ROOT%"

REM ========== 第二步：复制必要文件 ==========
echo [2/2] 复制文件到分发文件夹...

REM Python 核心文件
echo   - Python 文件...
copy /Y "%PROJECT_ROOT%\arxiv_recommender_v5.py" "%DIST_ROOT%\" >nul
copy /Y "%PROJECT_ROOT%\backup_user_data.py" "%DIST_ROOT%\" >nul
copy /Y "%PROJECT_ROOT%\config_manager.py" "%DIST_ROOT%\" >nul
copy /Y "%PROJECT_ROOT%\fetch_top_journals.py" "%DIST_ROOT%\" >nul
copy /Y "%PROJECT_ROOT%\journal_tracker.py" "%DIST_ROOT%\" >nul
copy /Y "%PROJECT_ROOT%\journal_update.py" "%DIST_ROOT%\" >nul
copy /Y "%PROJECT_ROOT%\learn_paper.py" "%DIST_ROOT%\" >nul
copy /Y "%PROJECT_ROOT%\logger_config.py" "%DIST_ROOT%\" >nul
copy /Y "%PROJECT_ROOT%\update_journals.py" "%DIST_ROOT%\" >nul
copy /Y "%PROJECT_ROOT%\web_server.py" "%DIST_ROOT%\" >nul

REM HTML 文件
echo   - HTML 文件...
copy /Y "%PROJECT_ROOT%\*.html" "%DIST_ROOT%\" >nul 2>&1

REM installer 目录
echo   - installer 目录...
xcopy /E /Q /Y /I "%PROJECT_ROOT%\installer" "%DIST_ROOT%\installer\" >nul

REM 配置文件
echo   - 配置文件...
copy /Y "%PROJECT_ROOT%\requirements.txt" "%DIST_ROOT%\" >nul
copy /Y "%PROJECT_ROOT%\README.md" "%DIST_ROOT%\" >nul

REM 创建示例配置
echo   - 创建示例配置...
(
    echo {
    "version": 2,
    "keywords": {
        "conformal prediction": {"weight": 5.0, "category": "core"},
        "in-context learning": {"weight": 5.0, "category": "core"},
        "generalization bound": {"weight": 4.5, "category": "core"},
        "minimax optimal": {"weight": 4.5, "category": "core"},
        "excess risk": {"weight": 4.0, "category": "core"}
    },
    "theory_keywords": ["theorem", "proof", "bound", "convergence", "asymptotic"],
    "settings": {
        "papers_per_day": 20,
        "lookback_days": 14,
        "prefer_theory": true
    },
    "sources": {"arxiv_enabled": true, "journal_enabled": true},
    "zotero": {"database_path": "", "auto_detect": true, "enabled": true}
}
) > "%DIST_ROOT%\user_profile.json"

REM 创建空目录
echo   - 创建目录结构...
cd "%DIST_ROOT%"
if not exist "cache" mkdir cache
if not exist "cache\journals" mkdir cache\journals
if not exist "history" mkdir history
if not exist "logs" mkdir logs
if not exist "data" mkdir data

echo.
echo  ══════════════════════════════════════════════════════════
echo  整理完成!
echo  ══════════════════════════════════════════════════════════
echo.
echo  文件夹结构:
echo.
echo  1. D:\arxiv_recommender
echo     - 你自己用的（开发环境）
echo     - 包含所有源代码、 配置、 运行数据
echo.
echo  2. D:\arxiv_recommender_dist
echo     - 给别人用的（分发版本）
echo     - 只包含必要文件
echo     - 运行 installer\setup.bat 即可使用
echo.
echo  分发步骤:
echo   1. 压缩 D:\arxiv_recommender_dist 文件夹
echo   2. 发送 ZIP 给对方
echo   3. 对方解压后运行 installer\setup.bat
echo.

REM 打开两个文件夹
start "" explorer "%PROJECT_ROOT%"
start "" explorer "%DIST_ROOT%"

pause
