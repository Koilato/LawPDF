# Create the dedicated Conda environment for the independent case pipeline.

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$envPrefix = Join-Path $projectRoot '.conda\case-pipeline'
$condaExe = 'D:\Anaconda\Scripts\conda.exe'

if (-not (Test-Path $condaExe)) {
    throw "未找到 conda.exe: $condaExe"
}

& $condaExe env create -p $envPrefix -f (Join-Path $projectRoot 'environment.yml') --force
Write-Host "Conda environment ready: $envPrefix"
Write-Host "Activate with: conda activate $envPrefix"
