# Install "speak" (read replies aloud) for every AI agent found on this Windows machine.
#
#   powershell -ExecutionPolicy Bypass -File install.ps1            install / update
#   powershell -ExecutionPolicy Bypass -File install.ps1 -DryRun    show what would change
#   powershell -ExecutionPolicy Bypass -File install.ps1 -NoEdge    skip the natural voice
param([switch]$DryRun, [switch]$NoEdge)
$ErrorActionPreference = "Stop"

$Repo = $PSScriptRoot
$Skill = Join-Path $Repo "skills\speak"
$HomeDir = if ($env:SPEAK_HOME) { $env:SPEAK_HOME } else { Join-Path $HOME ".speak" }
$Script = Join-Path $HomeDir "speak.py"   # stable copy for agents wired by path (Codex, Grok)

function Say($m) { Write-Host $m -ForegroundColor Cyan }
function Note($m) { Write-Host "  $m" }
function Run([scriptblock]$b) { if ($DryRun) { Note "[dry-run] $b" } else { & $b } }
function Has($c) { [bool](Get-Command $c -ErrorAction SilentlyContinue) }

$Py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $Py) { $Py = (Get-Command py -ErrorAction SilentlyContinue).Source }
if (-not $Py) { Write-Host "Python 3 is required: https://www.python.org/downloads/"; exit 1 }

Say "1. Engine -> $Script"
Run { New-Item -ItemType Directory -Force $HomeDir | Out-Null }
Run { Copy-Item (Join-Path $Skill "scripts\speak.py") $Script -Force }

Say "2. Natural voice (edge-tts)"
& $Py -c "import edge_tts" 2>$null
if ((Has "edge-tts") -or $LASTEXITCODE -eq 0) { Note "already installed" }
elseif ($NoEdge) { Note "skipped (-NoEdge): the built-in Windows voice will be used" }
else { Run { & $Py -m pip install --user edge-tts } }

Say "3. Agents"
$found = $false

if (Has "claude") {
  $found = $true; Note "Claude Code: plugin speak@speak"
  Run { claude plugin marketplace add $Repo; claude plugin install speak@speak }
}

if (Has "agy") {
  $found = $true; Note "Antigravity: plugin speak"
  Run { agy plugin install $Repo }
}

$CodexDir = Join-Path $HOME ".codex"
if ((Has "codex") -or (Test-Path $CodexDir)) {
  $found = $true
  $Cfg = Join-Path $CodexDir "config.toml"
  $Line = 'notify = ["' + ($Py -replace '\\', '/') + '", "' + ($Script -replace '\\', '/') + '"]'
  $text = if (Test-Path $Cfg) { Get-Content $Cfg -Raw } else { "" }
  if ($text -match '(?m)^notify\s*=') {
    if ($text -match 'speak\.py') { Note "Codex: already set up" }
    else { Note "Codex: you already have a notify command, so I left it alone. To use speak, change it to:"; Note "  $Line" }
  } else {
    Note "Codex: adding to $Cfg -> $Line"
    # notify must be a top-level key, so it goes above any [section].
    Run { New-Item -ItemType Directory -Force $CodexDir | Out-Null; Set-Content $Cfg ($Line + "`n" + $text) -NoNewline }
  }
  Run { New-Item -ItemType Directory -Force (Join-Path $CodexDir "skills") | Out-Null
        Copy-Item $Skill (Join-Path $CodexDir "skills") -Recurse -Force }
}

$GrokDir = Join-Path $HOME ".grok"
if ((Has "grok") -or (Test-Path $GrokDir)) {
  $found = $true; Note "Grok: hook file ~/.grok/hooks/speak.json"
  $cmd = "`"$Py`" `"$Script`""
  $hooks = @{ hooks = @{
    Stop = @(@{ hooks = @(@{ type = "command"; command = $cmd }) })
    UserPromptSubmit = @(@{ hooks = @(@{ type = "command"; command = "$cmd --stop" }) })
  } } | ConvertTo-Json -Depth 8
  Run { New-Item -ItemType Directory -Force (Join-Path $GrokDir "hooks") | Out-Null
        Set-Content (Join-Path $GrokDir "hooks\speak.json") $hooks }
}

if (-not $found) { Note "No supported agent found. Pipe any text in:  echo hello | python `"$Script`" --text" }

Say "4. Check"
if (-not $DryRun) { & $Py $Script --doctor }
Say "Done. Restart your agent, then try /speak status (or /speak quick, /speak off ...)."
