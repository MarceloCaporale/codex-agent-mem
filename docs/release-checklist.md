# Release Checklist

Use this checklist after source review and before any tag, push, or GitHub
release. Do not publish from a dirty tree or from stale artifacts.

## Source gate

- Confirm `pyproject.toml` and `src/codex_agent_mem/__init__.py` declare the
  same version.
- Confirm `git status --short` is understood and any untracked release files are
  intentional.
- Confirm README files and support docs do not overclaim encryption, hosted
  auth, web bridges, universal compatibility, or guaranteed token savings.
- Confirm `uv.lock`, local DBs, caches, `dist/`, `build/`, egg-info, and private
  audit artifacts are not part of the public source.
- Confirm existing public verification checksum files match the files they
  declare.
- Confirm historical checksum files reference repo-local evidence, while the
  current release checksum file lists only artifact file names.

## Validation gate

```bash
python scripts/smoke_release.py --mcp-subprocess --with-ruff --with-build --with-wheel-smoke
```

This runs repository hygiene, compileall, pytest, MCP contract smoke, ruff,
isolated build, and wheel package-data smoke.

## Checksums

Generate release checksums from isolated build output:

```bash
python scripts/smoke_release.py --mcp-subprocess --with-ruff --with-build --with-wheel-smoke --write-checksums --export-artifacts-dir .release/v1.0.1
```

Review `docs/verification/v1.0.1/checksums_sha256.txt`, then commit it if the
release source will carry checksum evidence. `MANIFEST.in` excludes that v1.0.1
checksum file from the sdist so the sdist does not contain the hash of itself.

Final gate:

```bash
python scripts/smoke_release.py --final --mcp-subprocess --export-artifacts-dir .release/v1.0.1
```

The final gate verifies checksums against artifacts built in that same run. It
does not require a committed `dist/` directory.
When `--export-artifacts-dir` is used, the verified wheel and sdist are copied
to that ignored local directory only after build, wheel smoke, and checksum
writing or validation pass. Upload those exported files as the GitHub Release
assets.

These checksums identify the official release assets produced by the
maintainer's release gate; they are not a cross-platform bit-for-bit
reproducible-build guarantee.

## Human gates

- Ask explicitly before commit.
- After commit, recreate/move the local `v1.0.1` tag only with explicit approval.
- Ask explicitly before pushing the branch.
- Ask explicitly before pushing the tag.
- Ask explicitly before publishing a GitHub release.
