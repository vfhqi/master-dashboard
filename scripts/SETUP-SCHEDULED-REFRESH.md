# Setting Up Daily Automated Refresh

## What you get
Every weekday at your chosen time, the dashboard auto-refreshes: fresh Yahoo Finance prices, recomputed filters, rebuilt HTML, pushed to GitHub Pages. No manual steps.

## Prerequisites (one-time)
1. Python on PATH — open a terminal, type `python --version`. Should return 3.x.
2. yfinance installed — `pip install yfinance pandas`
3. Git on PATH — open a terminal, type `git --version`. If not found, use Git Bash or add Git to PATH.

## Option 1: Double-click (manual)
Just double-click `refresh-dashboard.bat`. It runs all steps and pauses at the end so you can see output.

## Option 2: Windows Task Scheduler (automated)

1. Press Win+R, type `taskschd.msc`, press Enter
2. Click "Create Basic Task" in the right panel
3. Name: `Master Dashboard Refresh`
4. Trigger: **Weekly**, check Mon-Fri, set time (e.g. 18:00 for after market close)
5. Action: **Start a program**
6. Program: `C:\Users\richb\Documents\COWORK\master-dashboard\scripts\refresh-dashboard-silent.bat`
7. Start in: `C:\Users\richb\Documents\COWORK\master-dashboard\scripts`
8. Finish the wizard
9. Right-click the task → Properties → check "Run whether user is logged on or not" if you want it to run when PC is locked

## Option 3: Run from Git Bash
```bash
cd /c/Users/richb/Documents/COWORK/master-dashboard/scripts
./refresh-dashboard.bat
```

## Checking logs
Silent runs write logs to `master-dashboard/logs/refresh-YYYYMMDD_HHMM.log`. Check these if the dashboard looks stale.

## Git push note
The script runs `git commit + push` automatically. If git is not on PATH, the push step will fail silently — the data and HTML are still rebuilt locally. You can push manually via GitHub Desktop.

## Timing recommendation
- **18:00 weekdays** — after European market close, fresh EOD data
- Yahoo Finance data updates ~15-30 min after close, so 18:00 gives margin
