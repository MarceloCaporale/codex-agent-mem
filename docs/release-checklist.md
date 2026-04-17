# Release Checklist

- `pytest -q`
- `python -m compileall src`
- `ruff check .`
- verify `codex-agent-mem-smoke`
- verify `codex-agent-mem-bootstrap-codex`
- `python -m build`
- install the built wheel in a clean venv and rerun `codex-agent-mem-smoke`
- verify Windows example config
- review [discoverability metadata](./discoverability.md)
- verify `pyproject.toml` points at the live public repository URL
- tag release
- attach changelog
