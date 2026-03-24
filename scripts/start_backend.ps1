$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$logsRoot = Join-Path $projectRoot 'logs'
$pythonExe = Join-Path $projectRoot '.conda\case-pipeline\python.exe'

New-Item -ItemType Directory -Path $logsRoot -Force | Out-Null

if (-not (Test-Path $pythonExe)) {
    throw "Missing backend Python environment: $pythonExe"
}

Start-Process -FilePath $pythonExe -ArgumentList '-u', '.\backend\app\main.py', '--host', '127.0.0.1', '--port', '8000' -WorkingDirectory $projectRoot -RedirectStandardOutput (Join-Path $logsRoot 'backend.out.log') -RedirectStandardError (Join-Path $logsRoot 'backend.err.log')
