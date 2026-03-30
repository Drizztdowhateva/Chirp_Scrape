param(
    [string]$PythonExe = ".venv\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Test-Path $PythonExe)) {
    Write-Error "Missing venv Python at '$PythonExe'. Run: python bootstrap.py install"
}

& $PythonExe -m pip install pyinstaller
& $PythonExe -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name FreqFinder `
    --add-data "media;media" `
    --add-data "csv_files;csv_files" `
    --add-data "radioref.csv;." `
    chirp_scraper.py

Write-Host "Built: dist/FreqFinder.exe"
