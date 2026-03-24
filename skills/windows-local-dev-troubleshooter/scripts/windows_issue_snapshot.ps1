param(
    [string]$ProjectRoot = '.',
    [int[]]$Ports = @(8000, 5173),
    [int]$LogTail = 10
)

$ErrorActionPreference = 'Stop'

function Write-Section {
    param([string]$Title)
    Write-Output ''
    Write-Output ('## ' + $Title)
}

function Format-EncodingName {
    param($Encoding)
    if ($null -eq $Encoding) {
        return ''
    }
    return $Encoding.WebName
}

function Get-ListeningProcessInfo {
    param([int]$Port)

    $lines = & netstat -ano -p tcp 2>$null
    foreach ($line in $lines) {
        if ($line -match "^\s*TCP\s+\S+:$Port\s+\S+\s+LISTENING\s+(\d+)\s*$") {
            $listeningPid = [int]$matches[1]
            $process = Get-Process -Id $listeningPid -ErrorAction SilentlyContinue
            return [pscustomobject]@{
                Port      = $Port
                Listening = $true
                PID       = $listeningPid
                Process   = if ($process) { $process.ProcessName } else { 'unknown' }
            }
        }
    }

    return [pscustomobject]@{
        Port      = $Port
        Listening = $false
        PID       = ''
        Process   = ''
    }
}

if (-not (Test-Path $ProjectRoot)) {
    throw "Project root does not exist: $ProjectRoot"
}

$resolvedProjectRoot = (Resolve-Path $ProjectRoot).Path
$logsRoot = Join-Path $resolvedProjectRoot 'logs'
$repoMarkers = @(
    'backend',
    'frontend',
    'logs',
    'scripts\start_backend.ps1',
    'scripts\start_frontend.ps1',
    '.conda\case-pipeline\python.exe'
)

Write-Section 'Context'
Write-Output ('Timestamp: ' + (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))
Write-Output ('ProjectRoot: ' + $resolvedProjectRoot)
Write-Output ('CurrentDirectory: ' + (Get-Location).Path)
Write-Output ('User: ' + [Environment]::UserName)
Write-Output ('Computer: ' + $env:COMPUTERNAME)

Write-Section 'Shell'
Write-Output ('PSVersion: ' + $PSVersionTable.PSVersion)
Write-Output ('PSEdition: ' + $PSVersionTable.PSEdition)
Write-Output ('CodePage: ' + ((& cmd /c chcp 2>$null) -join ' '))
Write-Output ('ConsoleInputEncoding: ' + (Format-EncodingName ([Console]::InputEncoding)))
Write-Output ('ConsoleOutputEncoding: ' + (Format-EncodingName ([Console]::OutputEncoding)))
Write-Output ('PowerShellOutputEncoding: ' + (Format-EncodingName $OutputEncoding))
Write-Output ('PYTHONUTF8: ' + $env:PYTHONUTF8)
Write-Output ('PYTHONIOENCODING: ' + $env:PYTHONIOENCODING)

Write-Section 'Repo Markers'
foreach ($marker in $repoMarkers) {
    $path = Join-Path $resolvedProjectRoot $marker
    $state = if (Test-Path $path) { 'OK' } else { 'MISSING' }
    Write-Output ('[' + $state + '] ' + $marker)
}

Write-Section 'Python'
$pythonCandidates = @(
    (Join-Path $resolvedProjectRoot '.conda\case-pipeline\python.exe'),
    (Join-Path $resolvedProjectRoot 'venv\Scripts\python.exe')
)

foreach ($candidate in $pythonCandidates) {
    if (Test-Path $candidate) {
        $version = (& $candidate -c "import sys; print(sys.version.split()[0])" 2>$null)
        Write-Output ('[FOUND] ' + $candidate)
        Write-Output ('Version: ' + ($version -join ' '))
    }
}

$pythonOnPath = Get-Command python -ErrorAction SilentlyContinue
if ($pythonOnPath) {
    Write-Output ('[PATH] ' + $pythonOnPath.Source)
}

Write-Section 'Git'
$gitBranch = (& git -C $resolvedProjectRoot rev-parse --abbrev-ref HEAD 2>$null)
if ($LASTEXITCODE -eq 0) {
    Write-Output ('Branch: ' + ($gitBranch -join ' '))
    $gitStatus = (& git -C $resolvedProjectRoot status --short 2>$null)
    if ($gitStatus) {
        Write-Output 'Status:'
        $gitStatus | Select-Object -First 20 | ForEach-Object { Write-Output ('  ' + $_) }
    }
    else {
        Write-Output 'Status: clean'
    }
}

Write-Section 'Ports'
$portInfo = foreach ($port in $Ports) { Get-ListeningProcessInfo -Port $port }
$portInfo | Format-Table -AutoSize | Out-String -Width 200 | Write-Output

Write-Section 'Recent Logs'
if (-not (Test-Path $logsRoot)) {
    Write-Output ('Logs directory not found: ' + $logsRoot)
}
else {
    $logNames = @(
        'backend.out.log',
        'backend.err.log',
        'frontend.out.log',
        'frontend.err.log',
        'backend_start.out.log',
        'backend_start.err.log',
        'frontend_start.out.log',
        'frontend_start.err.log'
    )

    foreach ($logName in $logNames) {
        $logPath = Join-Path $logsRoot $logName
        if (Test-Path $logPath) {
            Write-Output ('### ' + $logName)
            Get-Content -Path $logPath -Tail $LogTail -ErrorAction SilentlyContinue | ForEach-Object { Write-Output $_ }
            Write-Output ''
        }
    }
}
