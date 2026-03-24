$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$frontendRoot = Join-Path $projectRoot 'frontend'
$logsRoot = Join-Path $projectRoot 'logs'
$npmExe = 'D:\Nodejs\npm.cmd'

New-Item -ItemType Directory -Path $logsRoot -Force | Out-Null

if (-not (Test-Path $frontendRoot)) {
    throw "Missing frontend directory: $frontendRoot"
}

if (-not (Test-Path $npmExe)) {
    $npmExe = 'npm.cmd'
}

Start-Process -FilePath $npmExe -ArgumentList 'run', 'dev', '--', '--host', '127.0.0.1', '--port', '5173', '--strictPort' -WorkingDirectory $frontendRoot -RedirectStandardOutput (Join-Path $logsRoot 'frontend.out.log') -RedirectStandardError (Join-Path $logsRoot 'frontend.err.log')
