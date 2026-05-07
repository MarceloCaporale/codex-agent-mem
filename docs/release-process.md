# Release Process

This process keeps v1.0.x releases verifiable and avoids publishing stale
artifacts or claims that are ahead of evidence.

## Principles

- Release from the reviewed source state, not from generated archives or audit
  packages.
- Use temporary databases for validation and smoke tests.
- Do not use an operational memory database for release checks.
- Do not commit, tag, push, or publish until the maintainer explicitly approves
  that step.
- Do not claim a support level unless the validation evidence names its level.
- Keep public docs in English, except intentional translated README files.
- Do not include private paths, local audit folders, credentials, caches,
  virtual environments, or build outputs in the public package.

## Pre-release checks

1. Confirm the version in `pyproject.toml` and `src/codex_agent_mem/__init__.py`.
2. Review `git status --short` and classify unrelated work before editing.
3. Review release notes, changelog, security posture, support matrix, and
   validation docs for consistency.
4. Confirm no public doc claims hosted bridges, OAuth web deployment, encryption
   at rest, or universal client behavior unless that exact scope is validated.
5. Confirm `uv.lock`, `dist/`, `build/`, caches, local databases, and generated
   private audit artifacts are not part of the release payload.

## Validation gate

Run the release gate from a clean or intentionally classified worktree:

```bash
python scripts/smoke_release.py --mcp-subprocess --with-ruff --with-build --with-wheel-smoke
```

For the final release gate, checksum files must already exist and must match
the artifacts produced by the same isolated build:

```bash
python scripts/smoke_release.py --final --mcp-subprocess --export-artifacts-dir .release/v1.0.2
```

The release smoke should confirm:

- package version;
- `schema.sql`, templates, and static assets are included;
- local smoke test passes with a temporary database;
- MCP contract smoke passes, including `structuredContent` object roots and
  `known_pack_hash` / `not_modified`.

## Evidence and checksums

- Keep synthetic fixture evidence under `docs/verification/`.
- Existing public verification checksum files must match the files they list;
  repository hygiene validates these hashes before release.
- Historical evidence checksums must point at versioned files in the repo.
- The current release checksum file lists release artifact names only; repository
  hygiene validates its format and safe file names, while `smoke_release.py`
  validates the hashes against the isolated build output.
- Release checksums identify the official assets produced by the maintainer's
  release gate. They are not a guarantee that every third-party OS, Python,
  build backend, or packaging toolchain will reproduce identical hashes.
- Generate final SHA-256 checksums only after the final wheel and sdist are
  rebuilt from the release source.
- The checksum file lists release asset file names, not a committed `dist/`
  directory.
- The current release checksum file is excluded from the sdist so the sdist does
  not contain the hash of itself.
- Do not reuse checksums from an earlier version.
- If a new verification folder is created, keep it separate from v1.0.0
  historical evidence.

To generate checksums from an isolated build:

```bash
python scripts/smoke_release.py --mcp-subprocess --with-ruff --with-build --with-wheel-smoke --write-checksums --export-artifacts-dir .release/v1.0.2
```

Review and commit the checksum file before running `--final`, or publish it as a
GitHub Release asset. If it is committed, `MANIFEST.in` still excludes the
current release checksum file from the sdist to avoid a circular hash.
The export directory is ignored by Git. It receives the verified wheel and sdist
only after build, wheel smoke, and checksum writing or validation pass; those
files are the release assets to upload. Do not rebuild artifacts later outside
the gate and substitute them for the exported files.

## Maturity decision

The package maturity classifier must match the completed release gate.

Use a conservative classifier if any relevant gap remains:

- failing tests or smoke scripts;
- stale build artifacts;
- unclassified generated files;
- support-matrix claims without evidence level;
- inconsistent README translations;
- security wording that overclaims encryption, hosted auth, or prompt-injection
  resistance.

## Publishing sequence

1. Finish source and documentation changes.
2. Run the validation gate.
3. Review the final diff.
4. Ask for explicit maintainer approval to commit.
5. Build final artifacts from the committed source and generate checksums.
6. Commit the checksum file if it is part of the public source release, keeping
   it excluded from the sdist.
7. Run `python scripts/smoke_release.py --final --mcp-subprocess --export-artifacts-dir .release/v1.0.2`.
8. Ask for explicit approval to tag.
9. Ask for explicit approval to push and publish the release.

Never move a tag, overwrite release artifacts, or publish a package because a
local folder appears ready. The source commit, tag, artifacts, checksums, and
release notes must describe the same version.
