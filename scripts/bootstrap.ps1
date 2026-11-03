param([ValidateSet('Core','Local')][string]$Profile = 'Core', [switch]$Offline)
$ErrorActionPreference = 'Stop'
$taskSkillRoot = Split-Path -Parent $PSScriptRoot
$taskUv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $taskUv) {
    Write-Output 'Install uv: https://docs.astral.sh/uv/getting-started/installation/'
    Write-Output 'Windows: winget install --id=astral-sh.uv -e'
    Write-Output 'Reopen the terminal, verify uv --version, then rerun this script.'
    exit 2
}
$taskArgs = @('sync','--project',(Join-Path $taskSkillRoot 'runtime'),'--python','3.12','--frozen')
if ($Profile -eq 'Local') { $taskArgs += @('--extra','local') }
if ($Offline) { $taskArgs += '--offline' }
& $taskUv.Source @taskArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$taskPythonArgs = @('run','--project',(Join-Path $taskSkillRoot 'runtime'),'--frozen')
if ($Profile -eq 'Local') { $taskPythonArgs += @('--extra','local') }
if ($Offline) { $taskPythonArgs += '--offline' }
$taskPythonArgs += @('python',(Join-Path $PSScriptRoot 'workflow.py'),'doctor')
& $taskUv.Source @taskPythonArgs
exit $LASTEXITCODE
