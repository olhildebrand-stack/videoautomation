<#
.SYNOPSIS
  Transcribe a video to word-level timestamps. Thin wrapper over
  transcribe/transcribe.py using that project's virtualenv.

.EXAMPLE
  .\transcribe.ps1 "C:\clips\avsnitt-01.mp4"

.EXAMPLE
  .\transcribe.ps1 clip.mp4 -o out.json --cpu
#>

# Deliberately no param() block and no [CmdletBinding()]. Either one turns this
# into an advanced script, which adds PowerShell's common parameters -- and then
# transcribe.py's own -o flag fails to bind as "ambiguous with -OutVariable,
# -OutBuffer" before the script even runs. Reading $args keeps every flag ours.

$ErrorActionPreference = 'Stop'

if ($args.Count -lt 1) {
  Write-Host 'usage: .\transcribe.ps1 <video> [transcribe.py options]' -ForegroundColor Yellow
  Write-Host '  e.g. .\transcribe.ps1 "C:\clips\avsnitt-01.mp4" -o words.json'
  exit 2
}

$video = [string]$args[0]
# @(...) is load-bearing. A one-element slice unwraps to a scalar, and
# splatting a string explodes it into single characters -- "--verbatim"
# arrives as "- - v e r b a t i m". Forcing an array keeps it one argument.
$rest = @(if ($args.Count -gt 1) { $args[1..($args.Count - 1)] } else { @() })

$venvPy = Join-Path $PSScriptRoot 'transcribe\.venv\Scripts\python.exe'
$script = Join-Path $PSScriptRoot 'transcribe\transcribe.py'

if (-not (Test-Path $venvPy)) {
  Write-Host "No virtualenv found at $venvPy" -ForegroundColor Red
  Write-Host 'Run .\setup.ps1 first.' -ForegroundColor Red
  exit 1
}

if (-not (Test-Path $video)) {
  Write-Host "No such file: $video" -ForegroundColor Red
  exit 2
}

& $venvPy $script $video @rest
exit $LASTEXITCODE
