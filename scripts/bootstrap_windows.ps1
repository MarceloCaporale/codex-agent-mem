param(
  [string]$VenvPath = ".venv",
  [string]$DbPath = "$HOME\.codex_agent_mem\codex_agent_mem.db",
  [switch]$SkipTests
)

$ErrorActionPreference = "Stop"

python -m venv $VenvPath
$python = Join-Path $VenvPath "Scripts\python.exe"

& $python -m pip install -e ".[dev]"

if (-not $SkipTests) {
  & $python -m pytest -q
}

& $python -m codex_agent_mem.smoke --db-path $DbPath | Out-Host
Write-Host ""
Write-Host "Codex config snippet:"
Write-Host ""
& $python -m codex_agent_mem.bootstrap_codex --python-exe $python --db-path $DbPath | Out-Host
