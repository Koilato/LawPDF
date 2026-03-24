param(
    [string]$RepoRoot = '.',
    [string]$Remote = 'origin',
    [int[]]$HttpProxyPorts = @(7890, 10809),
    [int[]]$SocksProxyPorts = @(7891, 10808),
    [int]$ConnectTimeoutMs = 4000,
    [int]$GitProbeTimeoutSec = 12,
    [switch]$RunGitProbe
)

$ErrorActionPreference = 'Stop'

function Write-Section {
    param([string]$Title)
    Write-Output ''
    Write-Output ('## ' + $Title)
}

function Quote-Argument {
    param([string]$Value)

    if ($null -eq $Value) {
        return '""'
    }

    if ($Value -match '[\s"]') {
        return '"' + ($Value -replace '"', '\"') + '"'
    }

    return $Value
}

function Get-GitValue {
    param(
        [string]$RepoPath,
        [string[]]$Arguments
    )

    $output = & git -C $RepoPath @Arguments 2>$null
    if ($LASTEXITCODE -ne 0 -or $null -eq $output) {
        return ''
    }

    return (($output | ForEach-Object { $_.ToString().Trim() }) -join [Environment]::NewLine).Trim()
}

function Test-TcpPort {
    param(
        [string]$TargetHost,
        [int]$Port,
        [int]$TimeoutMs = 4000
    )

    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $async = $client.BeginConnect($TargetHost, $Port, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne($TimeoutMs, $false)) {
            $client.Close()
            return $false
        }

        $null = $client.EndConnect($async)
        $client.Close()
        return $true
    }
    catch {
        return $false
    }
}

function Get-OpenProxyCandidates {
    param(
        [int[]]$Ports,
        [string]$Scheme,
        [int]$TimeoutMs
    )

    $results = @()
    foreach ($port in $Ports) {
        if (Test-TcpPort -TargetHost '127.0.0.1' -Port $port -TimeoutMs $TimeoutMs) {
            $results += [pscustomobject]@{
                Scheme = $Scheme
                Port   = $port
                Url    = if ($Scheme -eq 'http') {
                    'http://127.0.0.1:' + $port
                }
                else {
                    'socks5h://127.0.0.1:' + $port
                }
            }
        }
    }

    return $results
}

function Invoke-GitProbe {
    param(
        [string]$RepoPath,
        [string[]]$GitArguments,
        [string]$Label,
        [int]$TimeoutSec
    )

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = 'git'
    $psi.WorkingDirectory = $RepoPath
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    $psi.Arguments = (($GitArguments | ForEach-Object { Quote-Argument $_ }) -join ' ')

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $psi

    try {
        $null = $process.Start()
        if (-not $process.WaitForExit($TimeoutSec * 1000)) {
            try {
                $process.Kill($true)
            }
            catch {
            }

            return [pscustomobject]@{
                Label    = $Label
                Success  = $false
                ExitCode = -1
                TimedOut = $true
                StdOut   = ''
                StdErr   = 'Timed out after ' + $TimeoutSec + 's'
            }
        }

        $stdout = $process.StandardOutput.ReadToEnd().Trim()
        $stderr = $process.StandardError.ReadToEnd().Trim()

        return [pscustomobject]@{
            Label    = $Label
            Success  = ($process.ExitCode -eq 0)
            ExitCode = $process.ExitCode
            TimedOut = $false
            StdOut   = $stdout
            StdErr   = $stderr
        }
    }
    catch {
        return [pscustomobject]@{
            Label    = $Label
            Success  = $false
            ExitCode = -2
            TimedOut = $false
            StdOut   = ''
            StdErr   = $_.Exception.Message
        }
    }
    finally {
        $process.Dispose()
    }
}

function Get-PreviewLine {
    param([string]$Text)

    if ([string]::IsNullOrWhiteSpace($Text)) {
        return ''
    }

    return (($Text -split "`r?`n")[0]).Trim()
}

if (-not (Test-Path $RepoRoot)) {
    throw "Repo root does not exist: $RepoRoot"
}

$resolvedRepoRoot = (Resolve-Path $RepoRoot).Path
$gitVersion = (& git --version 2>$null)
$branch = Get-GitValue -RepoPath $resolvedRepoRoot -Arguments @('rev-parse', '--abbrev-ref', 'HEAD')
$remoteUrl = Get-GitValue -RepoPath $resolvedRepoRoot -Arguments @('remote', 'get-url', $Remote)
$globalHttpProxy = Get-GitValue -RepoPath $resolvedRepoRoot -Arguments @('config', '--global', '--get', 'http.proxy')
$globalHttpsProxy = Get-GitValue -RepoPath $resolvedRepoRoot -Arguments @('config', '--global', '--get', 'https.proxy')
$localHttpProxy = Get-GitValue -RepoPath $resolvedRepoRoot -Arguments @('config', '--local', '--get', 'http.proxy')
$localHttpsProxy = Get-GitValue -RepoPath $resolvedRepoRoot -Arguments @('config', '--local', '--get', 'https.proxy')
$envHttpProxy = $env:HTTP_PROXY
$envHttpsProxy = $env:HTTPS_PROXY
$envAllProxy = $env:ALL_PROXY
$envNoProxy = $env:NO_PROXY

$httpCandidates = @(Get-OpenProxyCandidates -Ports $HttpProxyPorts -Scheme 'http' -TimeoutMs $ConnectTimeoutMs)
$socksCandidates = @(Get-OpenProxyCandidates -Ports $SocksProxyPorts -Scheme 'socks5h' -TimeoutMs $ConnectTimeoutMs)
$allCandidates = @($httpCandidates + $socksCandidates)

try {
    $proxyProcesses = Get-CimInstance Win32_Process |
        Where-Object { $_.Name -match 'v2rayN|sing-box|clash|xray|mihomo' } |
        Select-Object Name, ProcessId, ExecutablePath
}
catch {
    $proxyProcesses = @()
}

$github443 = Test-TcpPort -TargetHost 'github.com' -Port 443 -TimeoutMs $ConnectTimeoutMs
$sshGithub443 = Test-TcpPort -TargetHost 'ssh.github.com' -Port 443 -TimeoutMs $ConnectTimeoutMs

Write-Section 'Context'
Write-Output ('Timestamp: ' + (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))
Write-Output ('RepoRoot: ' + $resolvedRepoRoot)
Write-Output ('Remote: ' + $Remote)
Write-Output ('RemoteUrl: ' + $(if ($remoteUrl) { $remoteUrl } else { '(missing)' }))
Write-Output ('Branch: ' + $(if ($branch) { $branch } else { '(unknown)' }))
Write-Output ('GitVersion: ' + ($gitVersion -join ' '))

Write-Section 'Git Proxy Config'
Write-Output ('GlobalHttpProxy: ' + $(if ($globalHttpProxy) { $globalHttpProxy } else { '(unset)' }))
Write-Output ('GlobalHttpsProxy: ' + $(if ($globalHttpsProxy) { $globalHttpsProxy } else { '(unset)' }))
Write-Output ('LocalHttpProxy: ' + $(if ($localHttpProxy) { $localHttpProxy } else { '(unset)' }))
Write-Output ('LocalHttpsProxy: ' + $(if ($localHttpsProxy) { $localHttpsProxy } else { '(unset)' }))

Write-Section 'Proxy Environment'
Write-Output ('HTTP_PROXY: ' + $(if ($envHttpProxy) { $envHttpProxy } else { '(unset)' }))
Write-Output ('HTTPS_PROXY: ' + $(if ($envHttpsProxy) { $envHttpsProxy } else { '(unset)' }))
Write-Output ('ALL_PROXY: ' + $(if ($envAllProxy) { $envAllProxy } else { '(unset)' }))
Write-Output ('NO_PROXY: ' + $(if ($envNoProxy) { $envNoProxy } else { '(unset)' }))

Write-Section 'Reachability'
Write-Output ('github.com:443 => ' + $(if ($github443) { 'reachable' } else { 'unreachable' }))
Write-Output ('ssh.github.com:443 => ' + $(if ($sshGithub443) { 'reachable' } else { 'unreachable' }))

Write-Section 'Local Proxy Candidates'
if ($allCandidates.Count -eq 0) {
    Write-Output 'No common local proxy ports responded.'
}
else {
    $allCandidates |
        Sort-Object Scheme, Port |
        ForEach-Object { Write-Output ('[' + $_.Scheme + '] ' + $_.Url) }
}

Write-Section 'Proxy Processes'
if ($proxyProcesses.Count -eq 0) {
    Write-Output 'No matching proxy processes found.'
}
else {
    $proxyProcesses | Format-Table -AutoSize | Out-String -Width 220 | Write-Output
}

$probeResults = @()
if ($RunGitProbe) {
    Write-Section 'Git Probes'

    $probeResults += Invoke-GitProbe -RepoPath $resolvedRepoRoot -GitArguments @('-C', $resolvedRepoRoot, 'ls-remote', $Remote) -Label 'current' -TimeoutSec $GitProbeTimeoutSec
    $probeResults += Invoke-GitProbe -RepoPath $resolvedRepoRoot -GitArguments @('-C', $resolvedRepoRoot, '-c', 'http.proxy=', '-c', 'https.proxy=', 'ls-remote', $Remote) -Label 'direct' -TimeoutSec $GitProbeTimeoutSec

    foreach ($candidate in $allCandidates) {
        $label = $candidate.Scheme + ':' + $candidate.Port
        $probeResults += Invoke-GitProbe -RepoPath $resolvedRepoRoot -GitArguments @('-C', $resolvedRepoRoot, '-c', ('http.proxy=' + $candidate.Url), '-c', ('https.proxy=' + $candidate.Url), 'ls-remote', $Remote) -Label $label -TimeoutSec $GitProbeTimeoutSec
    }

    foreach ($result in $probeResults) {
        $status = if ($result.Success) { 'SUCCESS' } elseif ($result.TimedOut) { 'TIMEOUT' } else { 'FAIL' }
        $preview = Get-PreviewLine -Text $(if ($result.Success) { $result.StdOut } else { $result.StdErr })
        Write-Output ('[' + $status + '] ' + $result.Label + $(if ($preview) { ' => ' + $preview } else { '' }))
    }
}
else {
    Write-Section 'Git Probes'
    Write-Output 'Skipped. Re-run with -RunGitProbe to test git ls-remote in multiple modes.'
}

$successfulDirect = $probeResults | Where-Object { $_.Label -eq 'direct' -and $_.Success } | Select-Object -First 1
$successfulHttp = $probeResults | Where-Object { $_.Success -and $_.Label -like 'http:*' } | Select-Object -First 1
$successfulSocks = $probeResults | Where-Object { $_.Success -and $_.Label -like 'socks5h:*' } | Select-Object -First 1
$successfulCurrent = $probeResults | Where-Object { $_.Label -eq 'current' -and $_.Success } | Select-Object -First 1

$recommendedMode = 'manual-investigation'
$suggestedGitTemplate = ''
$suggestedLsRemote = ''

if ($successfulDirect) {
    $recommendedMode = 'direct'
    $suggestedGitTemplate = 'git -c http.proxy= -c https.proxy= <git arguments>'
    $suggestedLsRemote = 'git -c http.proxy= -c https.proxy= ls-remote ' + $Remote
}
elseif ($successfulHttp) {
    $port = ($successfulHttp.Label -split ':', 2)[1]
    $url = 'http://127.0.0.1:' + $port
    $recommendedMode = 'http-proxy:' + $url
    $suggestedGitTemplate = 'git -c http.proxy=' + $url + ' -c https.proxy=' + $url + ' <git arguments>'
    $suggestedLsRemote = 'git -c http.proxy=' + $url + ' -c https.proxy=' + $url + ' ls-remote ' + $Remote
}
elseif ($successfulSocks) {
    $port = ($successfulSocks.Label -split ':', 2)[1]
    $url = 'socks5h://127.0.0.1:' + $port
    $recommendedMode = 'socks5h-proxy:' + $url
    $suggestedGitTemplate = 'git -c http.proxy=' + $url + ' -c https.proxy=' + $url + ' <git arguments>'
    $suggestedLsRemote = 'git -c http.proxy=' + $url + ' -c https.proxy=' + $url + ' ls-remote ' + $Remote
}
elseif ($successfulCurrent) {
    $recommendedMode = 'current-config'
    $suggestedGitTemplate = 'git <git arguments>'
    $suggestedLsRemote = 'git ls-remote ' + $Remote
}
elseif (-not $github443 -and $sshGithub443) {
    $recommendedMode = 'ssh-over-443-candidate'
}
elseif ($allCandidates.Count -gt 0) {
    $recommendedMode = 'proxy-detected-but-not-confirmed'
}

Write-Section 'Recommendation'
Write-Output ('RecommendedMode: ' + $recommendedMode)
if ($suggestedGitTemplate) {
    Write-Output ('SuggestedGitTemplate: ' + $suggestedGitTemplate)
}
if ($suggestedLsRemote) {
    Write-Output ('SuggestedGitLsRemote: ' + $suggestedLsRemote)
}
if ($recommendedMode -like 'http-proxy:*') {
    $proxyUrl = $recommendedMode.Substring('http-proxy:'.Length)
    Write-Output ('SuggestedSetGlobalProxy: git config --global http.proxy ' + $proxyUrl)
    Write-Output ('SuggestedSetGlobalProxy: git config --global https.proxy ' + $proxyUrl)
}
if ($recommendedMode -eq 'direct') {
    Write-Output 'SuggestedUnsetGlobalProxy: git config --global --unset-all http.proxy'
    Write-Output 'SuggestedUnsetGlobalProxy: git config --global --unset-all https.proxy'
}
if ($recommendedMode -eq 'ssh-over-443-candidate') {
    Write-Output 'SuggestedNextStep: test ssh -T -p 443 -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL git@ssh.github.com'
}

