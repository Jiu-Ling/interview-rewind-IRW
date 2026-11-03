[CmdletBinding()]
param(
    [ValidateSet("Local", "Core")]
    [string]$Profile = "Local",
    [switch]$Offline,
    [switch]$RequireLark,
    [switch]$NoUvInstall
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$SkillRoot = $PSScriptRoot
$RuntimeRoot = Join-Path $SkillRoot "runtime"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Add-UvToPath {
    $candidates = @(
        (Join-Path $HOME ".local\bin"),
        (Join-Path $HOME ".cargo\bin")
    )
    foreach ($candidate in $candidates) {
        if ((Test-Path -LiteralPath $candidate) -and (($env:PATH -split ";") -notcontains $candidate)) {
            $env:PATH = "$candidate;$env:PATH"
        }
    }
}

function Find-Uv {
    $command = Get-Command uv -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $candidates = @(
        (Join-Path $HOME ".local\bin\uv.exe"),
        (Join-Path $HOME ".cargo\bin\uv.exe")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }
    return $null
}

Write-Host "Interview Rewind (IRW) installer" -ForegroundColor Green
Write-Host "Skill:   $SkillRoot"
Write-Host "Profile: $Profile"

Write-Step "Checking uv"
$uv = Find-Uv
if (-not $uv) {
    if ($NoUvInstall) {
        Write-Host "uv is not installed." -ForegroundColor Yellow
        Write-Host "Install it with: winget install --id=astral-sh.uv -e"
        Write-Host "Or follow: https://docs.astral.sh/uv/getting-started/installation/"
        exit 2
    }

    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        Write-Host "uv was not found; installing with winget..." -ForegroundColor Yellow
        & $winget.Source install --id astral-sh.uv -e --accept-source-agreements --accept-package-agreements
        if ($LASTEXITCODE -ne 0) {
            Write-Host "winget could not install uv (exit code $LASTEXITCODE)." -ForegroundColor Yellow
        }
        Add-UvToPath
        $uv = Find-Uv
    }

    if (-not $uv) {
        Write-Host "uv is still unavailable." -ForegroundColor Yellow
        Write-Host "Run: winget install --id=astral-sh.uv -e"
        Write-Host "Or follow: https://docs.astral.sh/uv/getting-started/installation/"
        Write-Host "Reopen the terminal, verify 'uv --version', then run this installer again."
        exit 2
    }
}
Write-Host "Using uv: $uv"

Write-Step "Synchronizing Python 3.12 runtime"
$syncArgs = @("sync", "--project", $RuntimeRoot, "--python", "3.12", "--frozen")
if ($Profile -eq "Local") {
    $syncArgs += @("--extra", "local")
}
if ($Offline) {
    $syncArgs += "--offline"
}
& $uv @syncArgs
if ($LASTEXITCODE -ne 0) {
    Write-Host "Runtime synchronization failed." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Step "Checking runtime components"
$runArgs = @("run", "--project", $RuntimeRoot, "--frozen")
if ($Profile -eq "Local") {
    $runArgs += @("--extra", "local")
}
if ($Offline) {
    $runArgs += "--offline"
}
& $uv @runArgs python (Join-Path $SkillRoot "scripts\workflow.py") doctor
if ($LASTEXITCODE -ne 0) {
    Write-Host "Runtime check failed." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Step "Checking Lark CLI"
$lark = Get-Command lark-cli -ErrorAction SilentlyContinue
$node = Get-Command node -ErrorAction SilentlyContinue
$npm = Get-Command npm -ErrorAction SilentlyContinue

if ($lark) {
    Write-Host "lark-cli: $($lark.Source)"
} else {
    Write-Host "lark-cli was not found." -ForegroundColor Yellow
    if (-not $node) {
        Write-Host "Node.js is also missing. Install Node.js 16+ first:"
        Write-Host "  winget install --id OpenJS.NodeJS.LTS -e"
    }
    if (-not $npm) {
        Write-Host "npm is missing. Reopen the terminal after installing Node.js."
    }
    Write-Host "Install the Feishu CLI with:"
    Write-Host "  npm install -g @larksuite/cli"
    Write-Host "Then run:"
    Write-Host "  lark-cli config show"
    Write-Host "  lark-cli config init --new   # only when no app is configured"
    Write-Host "  lark-cli auth status --json --verify"
    if ($RequireLark) {
        Write-Host "Lark CLI is required by this invocation." -ForegroundColor Red
        exit 3
    }
}

Write-Host ""
Write-Host "Installation complete." -ForegroundColor Green
Write-Host "Profile: $Profile"
if ($Profile -eq "Local") {
    Write-Host "Prepare the ASR model with:"
    Write-Host "  uv run --project `"$RuntimeRoot`" --frozen --extra local python `"$SkillRoot\scripts\prepare_model.py`" --model large-v3-turbo --download"
}
