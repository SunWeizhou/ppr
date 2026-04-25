@echo off
chcp 65001 >nul
REM ============================================
REM   arXiv 论文推荐系统 - 一键打包分发
REM ============================================

setlocal EnableDelayedExpansion

for %%I in ("%~dp0..") do set "PROJECT_ROOT=%%~fI"
set "DIST_DIR=%PROJECT_ROOT%\dist"
set "DIST_NAME=arxiv_recommender"
set "ZIP_FILE=%DIST_DIR%\%DIST_NAME%.zip"

echo.
echo  ╔═════════════════════════════════════════════════════════╗
echo  ║         arXiv 论文推荐系统 - 打包分发                  ║
echo  ╚═════════════════════════════════════════════════════════╝
echo.

REM 运行创建分发文件夹脚本
call "%PROJECT_ROOT%\installer\create_distribution.bat"

if errorlevel 1 (
    echo [错误] 创建分发文件夹失败
    pause
    exit /b 1
)

REM 压缩分发文件夹
echo.
echo 正在压缩分发文件夹...
if not exist "%DIST_DIR%" mkdir "%DIST_DIR%"

powershell -Command "Compress-Archive -Path '%PROJECT_ROOT%\%DIST_NAME%' -DestinationPath '%ZIP_FILE%' -Force" 2>nul

if errorlevel 1 (
    echo [提示] PowerShell 压缩失败，尝试 7-Zip...
    if exist "C:\Program Files\7-Zip\7z.exe" (
        "C:\Program Files\7-Zip\7z.exe" a -tzip "%ZIP_FILE%" "%PROJECT_ROOT%\%DIST_NAME%\*" >nul
    )
)

echo.
echo  ══════════════════════════════════════════════════════════
echo  打包完成!
echo  ══════════════════════════════════════════════════════════
echo.
echo  分发文件夹: %PROJECT_ROOT%\%DIST_NAME%
echo  ZIP 文件: %ZIP_FILE%
echo.
echo  发送给对方后， 使用步骤:
echo   1. 解压 arxiv_recommender.zip
echo   2. 双击 installer\setup.bat
echo   3. 访问 http://localhost:5555
echo.

REM 打开输出目录
explorer "%DIST_DIR%"

pause
