#!/usr/bin/env bash
set -euo pipefail
VENV_PATH="${1:-.venv}"
DB_PATH="${AGENTMEM_DB_PATH:-$HOME/.codex_agent_mem/codex_agent_mem.db}"

python -m venv "$VENV_PATH"
PYTHON_EXE="$VENV_PATH/bin/python"
"$PYTHON_EXE" -m pip install -e ".[dev]"
"$PYTHON_EXE" -m pytest -q
"$PYTHON_EXE" -m codex_agent_mem.smoke --db-path "$DB_PATH"
printf '\nCodex config snippet:\n\n'
"$PYTHON_EXE" -m codex_agent_mem.bootstrap_codex --python-exe "$PYTHON_EXE" --db-path "$DB_PATH"
