@echo off
REM ============================================================
REM  Master Dashboard — Silent Refresh (for Task Scheduler)
REM  Same as refresh-dashboard.bat but no pause, with logging.
REM ============================================================

setlocal
cd /d "%~dp0"

REM ── Force UTF-8 so Python unicode prints don't crash under Task Scheduler ──
set PYTHONIOENCODING=utf-8

REM ── Locate git via GitHub Desktop (not on PATH) ──
set "GIT_CMD="
for /f "delims=" %%D in ('dir /b /ad /o-n "%LOCALAPPDATA%\GitHubDesktop\app-*" 2^>nul') do (
    if not defined GIT_CMD set "GIT_CMD=%LOCALAPPDATA%\GitHubDesktop\%%D\resources\app\git\cmd\git.exe"
)
if not defined GIT_CMD (
    set "GIT_CMD=git"
)

set LOGFILE=%~dp0\..\logs\refresh-%date:~-4%%date:~3,2%%date:~0,2%_%time:~0,2%%time:~3,2%.log
set LOGFILE=%LOGFILE: =0%

if not exist "%~dp0\..\logs" mkdir "%~dp0\..\logs"

echo Master Dashboard Refresh — %date% %time% > "%LOGFILE%"
echo. >> "%LOGFILE%"

echo [1/4] Fetching prices + computing filters... >> "%LOGFILE%"
python generate_master_data.py --full-universe >> "%LOGFILE%" 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo FAILED: generate_master_data.py exit code %ERRORLEVEL% >> "%LOGFILE%"
    exit /b 1
)

echo [2/4] Generating chart data... >> "%LOGFILE%"
python generate_chart_data.py --live >> "%LOGFILE%" 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo FAILED: generate_chart_data.py exit code %ERRORLEVEL% >> "%LOGFILE%"
    exit /b 1
)

echo [3/4] Building index.html... >> "%LOGFILE%"
python build_dashboard.py >> "%LOGFILE%" 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo FAILED: build_dashboard.py exit code %ERRORLEVEL% >> "%LOGFILE%"
    exit /b 1
)

echo [4/4] Git commit + push... >> "%LOGFILE%"
cd /d "%~dp0\.."

if not exist ".git" (
    echo      Initialising git repo... >> "%LOGFILE%"
    "%GIT_CMD%" init >> "%LOGFILE%" 2>&1
    "%GIT_CMD%" branch -M main >> "%LOGFILE%" 2>&1
    "%GIT_CMD%" remote add origin https://github.com/vfhqi/master-dashboard.git >> "%LOGFILE%" 2>&1
)

"%GIT_CMD%" add -A >> "%LOGFILE%" 2>&1
"%GIT_CMD%" commit -m "Automated refresh %date% %time%" >> "%LOGFILE%" 2>&1
"%GIT_CMD%" push origin main >> "%LOGFILE%" 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: Git push failed >> "%LOGFILE%"
)

echo Refresh complete. >> "%LOGFILE%"
exit /b 0
