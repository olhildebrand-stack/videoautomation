<#
.SYNOPSIS
  One-command setup for this project on Windows. Safe to re-run.

.DESCRIPTION
  Sets up both halves of the project and verifies them:
    broll/      Remotion -- npm install
    transcribe/ faster-whisper -- venv, deps, CUDA libraries

  Reports what worked and what did not. Does not install Node or Python
  itself; it tells you the winget command if either is missing.
#>

[CmdletBinding()]
param(
  [switch]$SkipBroll,
  [switch]$SkipTranscribe,
  [switch]$SkipFfmpeg,
  # Force-reinstall the CUDA wheels. Use when the probe reports unloadable DLLs.
  [switch]$RepairCuda
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot

# Windows PowerShell 5.1 mangles quoting when passing arguments to native
# executables and turns their stderr into terminating errors. Everything here
# is written to work on 5.1, but 7 is markedly less surprising.
if ($PSVersionTable.PSVersion.Major -lt 7) {
  Write-Host ("Running Windows PowerShell {0}. PowerShell 7 is recommended: winget install Microsoft.PowerShell" -f $PSVersionTable.PSVersion) -ForegroundColor Yellow
}
$problems = [System.Collections.Generic.List[string]]::new()
$notes = [System.Collections.Generic.List[string]]::new()

function Write-Step { param([string]$Text) Write-Host "`n== $Text" -ForegroundColor Cyan }
function Write-Ok   { param([string]$Text) Write-Host "   OK  $Text" -ForegroundColor Green }
function Write-Bad  { param([string]$Text) Write-Host "   !!  $Text" -ForegroundColor Red }

function Resolve-Python {
  # The py launcher avoids the Microsoft Store stub that shadows "python".
  foreach ($candidate in @('py', 'python')) {
    $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
    if (-not $cmd) { continue }
    try {
      $version = & $candidate --version 2>&1
      if ($LASTEXITCODE -eq 0 -and "$version" -match 'Python 3\.(\d+)') { return $candidate }
    } catch { }
  }
  return $null
}

# ---------------------------------------------------------------- broll ----

if (-not $SkipBroll) {
  Write-Step 'broll (Remotion)'
  if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Bad 'npm not found. Install Node: winget install OpenJS.NodeJS.LTS'
    $problems.Add('Node/npm missing')
  } else {
    Push-Location (Join-Path $root 'broll')
    try {
      npm install --no-fund --no-audit
      if ($LASTEXITCODE -ne 0) { throw "npm install exited $LASTEXITCODE" }
      Write-Ok 'dependencies installed'
      npm run check
      if ($LASTEXITCODE -ne 0) {
        Write-Bad 'typecheck or token guard failed'
        $problems.Add('broll checks failed')
      } else {
        Write-Ok 'typecheck and token guard pass'
      }
    } catch {
      Write-Bad $_.Exception.Message
      $problems.Add('broll setup failed')
    } finally { Pop-Location }
  }
}

# --------------------------------------------------------------- ffmpeg ----

if (-not $SkipFfmpeg) {
Write-Step 'ffmpeg (cutting and grading)'
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
  Write-Bad 'ffmpeg not found. Install it: winget install Gyan.FFmpeg'
  Write-Bad 'Then close and reopen this terminal so PATH refreshes.'
  $problems.Add('ffmpeg missing')
} else {
  $version = (& ffmpeg -version 2>&1 | Select-Object -First 1)
  Write-Ok "$version"

  if (-not (Get-Command ffprobe -ErrorAction SilentlyContinue)) {
    Write-Bad 'ffprobe not found -- it normally ships alongside ffmpeg'
    $problems.Add('ffprobe missing')
  }

  # The pipeline needs these specific filters. Remotion bundles an ffmpeg
  # built without eq/colortemperature, so presence alone is not enough.
  $prev = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  $filters = (& ffmpeg -hide_banner -filters 2>&1 | Out-String)
  $ErrorActionPreference = $prev

  $missing = @()
  foreach ($needed in @('trim', 'atrim', 'concat', 'eq', 'colortemperature')) {
    if ($filters -notmatch "(?m)^\s*\S+\s+$needed\s") { $missing += $needed }
  }
  if ($missing.Count -gt 0) {
    Write-Bad "ffmpeg is missing required filters: $($missing -join ', ')"
    Write-Bad 'This build cannot cut or grade. Install a full ffmpeg.'
    $problems.Add("ffmpeg lacks filters: $($missing -join ', ')")
  } else {
    Write-Ok 'required filters present (trim, atrim, concat, eq, colortemperature)'
  }
}

}

# ---------------------------------------------------------------- yt-dlp ----

# Optional. Only needed to pull the audio off a talk or tutorial worth
# transcribing and studying -- reference material, not part of a render. Absent
# is fine; the pipeline never calls it.
Write-Step 'yt-dlp (optional -- fetching reference audio)'
if (-not (Get-Command yt-dlp -ErrorAction SilentlyContinue)) {
  Write-Host '   --  yt-dlp not found. Optional: winget install yt-dlp.yt-dlp' -ForegroundColor DarkGray
  Write-Host '       Only needed to transcribe a video from a URL.' -ForegroundColor DarkGray
} else {
  Write-Ok ((& yt-dlp --version 2>&1 | Select-Object -First 1))
}

# ----------------------------------------------------------- transcribe ----

if (-not $SkipTranscribe) {
  Write-Step 'transcribe (faster-whisper)'
  $python = Resolve-Python
  if (-not $python) {
    Write-Bad 'Python 3 not found. Install it: winget install Python.Python.3.12'
    Write-Bad 'Then close and reopen this terminal so PATH refreshes.'
    $problems.Add('Python missing')
  } else {
    Write-Ok "using $python ($(& $python --version 2>&1))"
    $dir = Join-Path $root 'transcribe'
    $venv = Join-Path $dir '.venv'
    $venvPy = Join-Path $venv 'Scripts\python.exe'

    try {
      if (-not (Test-Path $venvPy)) {
        & $python -m venv $venv
        if ($LASTEXITCODE -ne 0) { throw "venv creation exited $LASTEXITCODE" }
        Write-Ok 'virtualenv created'
      } else {
        Write-Ok 'virtualenv already present'
      }

      & $venvPy -m pip install --upgrade pip --quiet
      & $venvPy -m pip install -r (Join-Path $dir 'requirements.txt') --quiet
      if ($LASTEXITCODE -ne 0) { throw "pip install exited $LASTEXITCODE" }
      Write-Ok 'faster-whisper installed'

      # CTranslate2 needs cuBLAS + cuDNN 9 for CUDA 12. These wheels supply
      # them without a system CUDA install; transcribe.py registers their DLL
      # directories at runtime, so no PATH changes are needed.
      $cudaArgs = @('-m', 'pip', 'install', 'nvidia-cublas-cu12', 'nvidia-cudnn-cu12==9.*', '--quiet')
      if ($RepairCuda) {
        Write-Host '   reinstalling CUDA wheels (-RepairCuda)'
        $cudaArgs += '--force-reinstall'
        $cudaArgs += '--no-cache-dir'
      }
      & $venvPy @cudaArgs
      if ($LASTEXITCODE -ne 0) {
        Write-Bad 'CUDA libraries failed to install; the script will fall back to CPU'
        $notes.Add('CUDA libraries not installed - transcription will run on CPU/int8')
      } else {
        Write-Ok 'CUDA libraries installed'
      }

      # A native command writing to stderr under $ErrorActionPreference='Stop'
      # becomes a terminating error, which would abort setup over a probe that
      # is only meant to report. Relax it here and judge by the exit code.
      $probeScript = Join-Path $dir 'cuda_probe.py'
      $previous = $ErrorActionPreference
      $ErrorActionPreference = 'Continue'
      $result = (& $venvPy $probeScript 2>&1 | Out-String).Trim()
      $probeExit = $LASTEXITCODE
      $ErrorActionPreference = $previous

      foreach ($line in $result -split "`r?`n") {
        if ($line.Trim()) { Write-Host "   $($line.Trim())" }
      }

      # Judge the verdict, not just the device count: a device can be visible
      # while the cuBLAS/cuDNN DLLs remain unloadable, which is exactly how a
      # green setup can still fall back to CPU at transcription time.
      if ($probeExit -ne 0) {
        Write-Bad 'CUDA probe failed to run - transcription will fall back to CPU/int8'
        $notes.Add('CUDA probe failed. Transcription still works on CPU/int8.')
      } elseif ($result -match 'verdict=cuda_ready') {
        Write-Ok 'CUDA ready - device visible, float16 supported, libraries load'
      } elseif ($result -match 'verdict=dll_missing:(\S+)') {
        Write-Bad "CUDA libraries will not load: $($Matches[1])"
        Write-Bad 'Transcription will fall back to CPU/int8.'
        $notes.Add("CUDA DLLs unloadable ($($Matches[1])). Try: .\setup.ps1 -RepairCuda")
      } elseif ($result -match 'verdict=no_float16') {
        Write-Bad 'CUDA device found but float16 unsupported - will fall back to CPU/int8'
        $notes.Add('float16 unsupported on this device.')
      } elseif ($result -match 'verdict=cpu_only') {
        Write-Bad 'No CUDA device visible - transcription will fall back to CPU/int8'
        $notes.Add('No CUDA device detected. Check your NVIDIA driver.')
      }
    } catch {
      Write-Bad $_.Exception.Message
      $problems.Add('transcribe setup failed')
    }
  }
}

# --------------------------------------------------------------- summary ---

Write-Step 'Summary'
if ($problems.Count -eq 0) {
  Write-Host '   Setup completed.' -ForegroundColor Green
  Write-Host ''
  Write-Host '   Remotion studio :  cd broll; npm start        -> http://localhost:3000'
  Write-Host '   Transcribe      :  transcribe\.venv\Scripts\python.exe transcribe\transcribe.py "clip.mp4"'
} else {
  Write-Host '   Finished with problems:' -ForegroundColor Red
  foreach ($p in $problems) { Write-Host "     - $p" -ForegroundColor Red }
}
foreach ($n in $notes) { Write-Host "   note: $n" -ForegroundColor Yellow }

if ($problems.Count -gt 0) { exit 1 }
