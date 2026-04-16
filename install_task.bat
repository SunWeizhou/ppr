@echo off
chcp 65001 >nul
REM Install arXiv Daily Recommender as Windows Scheduled Task
REM Run this script ONCE as Administrator

echo ========================================
echo arXiv Daily Recommender - Installer
echo ========================================
echo.

REM Check admin
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ERROR: Please run as Administrator!
    echo Right-click this file and select "Run as administrator"
    pause
    exit /b 1
)

REM 获取脚本所在目录
set SCRIPT_DIR=%~dp0
set SCRIPT_DIR=%SCRIPT_DIR:~0,-1%

echo Creating scheduled task...
echo.
echo  Schedule:
echo   - Daily at 8:30 AM
echo   - Also runs 2 minutes after boot
echo   - If computer was off, runs ASAP when turned on
echo.

REM 动态生成 XML 文件
set XML_FILE=%SCRIPT_DIR%\arxiv_daily_task_temp.xml
echo ^<?xml version="1.0" encoding="UTF-16"?^> > "%XML_FILE%"
echo ^<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task"^> >> "%XML_FILE%"
echo   ^<Triggers^> >> "%XML_FILE%"
echo     ^<CalendarTrigger^> >> "%XML_FILE%"
echo       ^<StartBoundary^>2025-01-01T08:30:00^</StartBoundary^> >> "%XML_FILE%"
echo       ^<Enabled^>true^</Enabled^> >> "%XML_FILE%"
echo       ^<ScheduleByDay^> >> "%XML_FILE%"
echo         ^<DaysInterval^>1^</DaysInterval^> >> "%XML_FILE%"
echo       ^</ScheduleByDay^> >> "%XML_FILE%"
echo     ^</CalendarTrigger^> >> "%XML_FILE%"
echo     ^<BootTrigger^> >> "%XML_FILE%"
echo       ^<Enabled^>true^</Enabled^> >> "%XML_FILE%"
echo       ^<Delay^>PT2M^</Delay^> >> "%XML_FILE%"
echo     ^</BootTrigger^> >> "%XML_FILE%"
echo   ^</Triggers^> >> "%XML_FILE%"
echo   ^<Principals^> >> "%XML_FILE%"
echo     ^<Principal id="Author"^> >> "%XML_FILE%"
echo       ^<LogonType^>InteractiveToken^</LogonType^> >> "%XML_FILE%"
echo       ^<RunLevel^>LeastPrivilege^</RunLevel^> >> "%XML_FILE%"
echo     ^</Principal^> >> "%XML_FILE%"
echo   ^</Principals^> >> "%XML_FILE%"
echo   ^<Settings^> >> "%XML_FILE%"
echo     ^<MultipleInstancesPolicy^>IgnoreNew^</MultipleInstancesPolicy^> >> "%XML_FILE%"
echo     ^<DisallowStartIfOnBatteries^>false^</DisallowStartIfOnBatteries^> >> "%XML_FILE%"
echo     ^<StopIfGoingOnBatteries^>false^</StopIfGoingOnBatteries^> >> "%XML_FILE%"
echo     ^<AllowHardTerminate^>true^</AllowHardTerminate^> >> "%XML_FILE%"
echo     ^<StartWhenAvailable^>true^</StartWhenAvailable^> >> "%XML_FILE%"
echo     ^<RunOnlyIfNetworkAvailable^>true^</RunOnlyIfNetworkAvailable^> >> "%XML_FILE%"
echo     ^<AllowStartOnDemand^>true^</AllowStartOnDemand^> >> "%XML_FILE%"
echo     ^<Enabled^>true^</Enabled^> >> "%XML_FILE%"
echo     ^<Hidden^>false^</Hidden^> >> "%XML_FILE%"
echo     ^<RunOnlyIfIdle^>false^</RunOnlyIfIdle^> >> "%XML_FILE%"
echo     ^<WakeToRun^>false^</WakeToRun^> >> "%XML_FILE%"
echo     ^<ExecutionTimeLimit^>PT1H^</ExecutionTimeLimit^> >> "%XML_FILE%"
echo   ^</Settings^> >> "%XML_FILE%"
echo   ^<Actions Context="Author"^> >> "%XML_FILE%"
echo     ^<Exec^> >> "%XML_FILE%"
echo       ^<Command^>%SCRIPT_DIR%\auto_start.bat^</Command^> >> "%XML_FILE%"
echo       ^<WorkingDirectory^>%SCRIPT_DIR%^</WorkingDirectory^> >> "%XML_FILE%"
echo     ^</Exec^> >> "%XML_FILE%"
echo   ^</Actions^> >> "%XML_FILE%"
echo ^</Task^> >> "%XML_FILE%"

REM 创建计划任务
schtasks /Create /TN "arxiv_daily_task" /XML "%XML_FILE%" /F

REM 删除临时 XML
del "%XML_FILE%"

if %errorLevel% equ 0 (
    echo.
    echo SUCCESS! Task installed.
    echo.
    echo The recommender will run:
    echo   [1] Every day at 8:30 AM
    echo   [2] 2 minutes after you log in
    echo   [3] If missed (computer was off), runs on next boot
    echo.
    echo To test now, run: "%SCRIPT_DIR%\run_daily.bat"
    echo To manage: Task Scheduler (taskschd.msc)
    echo.
) else (
    echo.
    echo ERROR: Failed to create task.
)

echo.
pause
