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
- set final project URLs in `pyproject.toml` if the public repository location is already defined
- tag release
- attach changelog
