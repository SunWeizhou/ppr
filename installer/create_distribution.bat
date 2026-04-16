@echo off
chcp 65001 >nul
REM ============================================
REM   创建完整分发包
REM ============================================

setlocal EnableDelayedExpansion

set DIST_NAME=arxiv_recommender_dist
set PROJECT_ROOT=D:\arxiv_recommender
set DIST_DIR=%PROJECT_ROOT%\%DIST_NAME%

echo.
echo  ========================================
echo   创建完整分发包
echo  ========================================
echo.

REM 删除旧的分发文件夹
if exist "%DIST_DIR%" rd /s /q "%DIST_DIR%" 2>nul

REM 创建分发文件夹
mkdir "%DIST_DIR%"

echo [1/6] 复制核心 Python 文件...
copy /Y "%PROJECT_ROOT%\*.py" "%DIST_DIR%\" 2>nul

echo [2/6] 复制配置文件...
copy /Y "%PROJECT_ROOT%\user_profile.json" "%DIST_DIR%\" 2>nul
if exist "%PROJECT_ROOT%\keywords_config.json" copy /Y "%PROJECT_ROOT%\keywords_config.json" "%DIST_DIR%\" 2>nul

echo [3/6] 复制依赖文件...
copy /Y "%PROJECT_ROOT%\requirements.txt" "%DIST_DIR%\" 2>nul

echo [4/6] 复制 installer 目录...
xcopy /E /Q /Y /I "%PROJECT_ROOT%\installer" "%DIST_DIR%\installer\"

echo [5/6] 创建必要目录...
cd "%DIST_DIR%"
if not exist "cache" mkdir cache
if not exist "cache\journals" mkdir cache\journals
if not exist "history" mkdir history
if not exist "logs" mkdir logs

echo [6/6] 创建示例配置（如果不存在）...
if not exist "user_profile.json" (
    echo {> user_profile.json (
    echo   "version": 2,
    echo   "keywords": {
    echo     "conformal prediction": {"weight": 5.0, "category": "core"},
    echo     "in-context learning": {"weight": 5.0, "category": "core"},
    echo     "generalization bound": {"weight": 4.5, "category": "core"},
    echo     "minimax": {"weight": 4.5, "category": "core"}
    echo   },
    echo   "theory_keywords": ["theorem", "proof", "bound", "convergence", "asymptotic"],
    echo   "settings": {
    echo     "papers_per_day": 20,
    echo     "prefer_theory": true
    echo   },
    echo   "sources": {"arxiv_enabled": true, "journal_enabled": true},
    echo   "zotero": {"database_path": "", "auto_detect": true, "enabled": true}
    echo }
) >> user_profile.json
)

cd ..

echo.
echo  ========================================
echo   打包完成！
echo  ========================================
echo.
echo  分发文件夹: %DIST_DIR%
echo.
echo  文件列表:
dir /b "%DIST_DIR%"
echo.
echo  下一步:
echo   1. 压缩 %DIST_NAME% 文件夹为 ZIP
echo   2. 发送给对方
echo   3. 对方解压后运行 installer\setup.bat
echo.

REM 打开分发文件夹
explorer "%DIST_DIR%"
