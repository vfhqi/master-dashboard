# Push Master Dashboard to GitHub Pages
# Usage: powershell -ExecutionPolicy Bypass -File push-to-github.ps1 "commit message"
# Or just: .\push-to-github.ps1

param(
    [string]$Message = "Update master dashboard"
)

$ErrorActionPreference = "Stop"

# Find git - check common locations
$gitPaths = @(
    "C:\Program Files\Git\bin\git.exe",
    "C:\Program Files (x86)\Git\bin\git.exe",
    "C:\Users\richb\AppData\Local\Programs\Git\bin\git.exe",
    "C:\ProgramData\chocolatey\bin\git.exe"
)
$GIT = $null
foreach ($gp in $gitPaths) {
    if (Test-Path $gp) { $GIT = $gp; break }
}
if (-not $GIT) {
    # Try finding it via where.exe from cmd
    $found = & cmd /c "where git" 2>$null
    if ($found) { $GIT = ($found -split "`n")[0].Trim() }
}
if (-not $GIT) {
    Write-Host "ERROR: git not found. Install Git for Windows or add it to PATH." -ForegroundColor Red
    exit 1
}
Write-Host "Using git: $GIT" -ForegroundColor Gray

$COWORK = "C:\Users\richb\Documents\COWORK"
$PAT = Get-Content "$COWORK\.secrets\github-pat.txt" -Raw
$PAT = $PAT.Trim()
$REPO_URL = "https://${PAT}@github.com/vfhqi/dashboards.git"
$TEMP_DIR = "$env:TEMP\dash-push-$(Get-Date -Format 'HHmmss')"
$SOURCE = "$COWORK\master-dashboard\index.html"

if (-not (Test-Path $SOURCE)) {
    Write-Host "ERROR: $SOURCE not found" -ForegroundColor Red
    exit 1
}

$size = (Get-Item $SOURCE).Length
Write-Host "Source: $SOURCE ($([math]::Round($size/1MB, 1)) MB)" -ForegroundColor Cyan

# Clone (shallow)
Write-Host "Cloning repo..." -ForegroundColor Yellow
& $GIT clone --depth 1 $REPO_URL $TEMP_DIR 2>&1 | Out-Null

# Copy
Copy-Item $SOURCE "$TEMP_DIR\master-dashboard.html" -Force
Write-Host "Copied to master-dashboard.html" -ForegroundColor Green

# Commit + push
Push-Location $TEMP_DIR
& $GIT add master-dashboard.html
& $GIT -c user.name="Watson" -c user.email="rich.black@gmail.com" commit -m "$Message`n`nCo-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
Write-Host "Pushing to GitHub..." -ForegroundColor Yellow
& $GIT push origin main 2>&1
Pop-Location

# Cleanup
Remove-Item $TEMP_DIR -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "`nDone. Live at: https://vfhqi.github.io/dashboards/master-dashboard.html" -ForegroundColor Green
