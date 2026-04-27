@echo off
REM ============================================================
REM  Master Dashboard — Full Refresh Pipeline
REM  Double-click to run, or schedule via Windows Task Scheduler.
REM
REM  Steps:
REM    1. Fetch prices from Yahoo Finance (yfinance)
REM    2. Compute all 5 screening filters
REM    3. Generate per-ticker chart data files
REM    4. Build index.html
REM    5. (Optional) Git commit + push
REM
REM  Requirements: Python 3 with yfinance, pandas installed.
REM  Install once:  pip install yfinance pandas
REM ============================================================

setlocal
cd /d "%~dp0"

REM ── Locate git via GitHub Desktop (not on PATH) ──
set "GIT_CMD="
for /f "delims=" %%D in ('dir /b /ad /o-n "%LOCALAPPDATA%\GitHubDesktop\app-*" 2^>nul') do (
    if not defined GIT_CMD set "GIT_CMD=%LOCALAPPDATA%\GitHubDesktop\%%D\resources\app\git\cmd\git.exe"
)
if not defined GIT_CMD (
    echo WARNING: Could not find GitHub Desktop git. Git steps will be skipped.
    set "GIT_CMD=git"
)

echo.
echo ========================================
echo  Master Dashboard — Full Refresh
echo  %date% %time%
echo ========================================
echo.

REM ── Step 1+2: Generate prices + filters ──
echo [1/4] Fetching prices + computing filters...
python generate_master_data.py --full-universe
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: generate_master_data.py failed with exit code %ERRORLEVEL%
    goto :error
)
echo      Done.
echo.

REM ── Step 3: Generate chart data ──
echo [2/4] Generating chart data (per-ticker JS files)...
python generate_chart_data.py --live
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: generate_chart_data.py failed with exit code %ERRORLEVEL%
    goto :error
)
echo      Done.
echo.

REM ── Step 4: Build HTML ──
echo [3/4] Building index.html...
python build_dashboard.py
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: build_dashboard.py failed with exit code %ERRORLEVEL%
    goto :error
)
echo      Done.
echo.

REM ── Step 5: Git init (if needed) + commit + push ──
echo [4/4] Git commit + push...
cd /d "%~dp0\.."

REM First-run: initialise repo if .git doesn't exist
if not exist ".git" (
    echo      Initialising git repo for first time...
    "%GIT_CMD%" init
    "%GIT_CMD%" branch -M main
    "%GIT_CMD%" remote add origin https://github.com/vfhqi/master-dashboard.git
    echo      Git repo initialised. Remote: vfhqi/master-dashboard
)

"%GIT_CMD%" add -A
"%GIT_CMD%" commit -m "Automated refresh %date% %time%"
"%GIT_CMD%" push origin main
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo      Push failed. If this is the first push, you may need to run once from
    echo      GitHub Desktop to authenticate, then this script will work going forward.
    echo      Or try: "%GIT_CMD%" push -u origin main
) else (
    echo      Pushed to GitHub.
)
echo.

echo ========================================
echo  Refresh complete.
echo ========================================
echo.
pause
goto :eof

:error
echo.
echo ========================================
echo  PIPELINE FAILED — see error above.
echo ========================================
echo.
pause
