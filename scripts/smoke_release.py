from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
SCRIPTS_DIR = REPO_ROOT / "scripts"
TESTS_DIR = REPO_ROOT / "tests"


@dataclass
class StepResult:
    name: str
    status: str
    detail: str = ""


def _python_env(temp_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPYCACHEPREFIX"] = str(temp_root / "pycache")
    env.setdefault("SOURCE_DATE_EPOCH", "1761523200")
    env["PYTHONPATH"] = (
        str(SRC_DIR)
        if not env.get("PYTHONPATH")
        else str(SRC_DIR) + os.pathsep + env["PYTHONPATH"]
    )
    return env


def _run_command(
    name: str,
    command: list[str],
    *,
    env: dict[str, str],
    cwd: Path = REPO_ROOT,
    timeout_seconds: int,
) -> StepResult:
    print(f"RUN: {name}")
    print("     " + " ".join(command))
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return StepResult(name, "FAIL", f"timed out after {timeout_seconds}s")
    if completed.returncode == 0:
        return StepResult(name, "PASS")
    return StepResult(name, "FAIL", f"exit code {completed.returncode}")


def _skip(name: str, reason: str) -> StepResult:
    print(f"SKIP: {name} ({reason})")
    return StepResult(name, "SKIP", reason)


def _copy_build_source(destination: Path) -> Path:
    source = destination / "source"

    def ignore(_dir: str, names: list[str]) -> set[str]:
        ignored = {
            ".git",
            ".hg",
            ".mypy_cache",
            ".pytest_cache",
            ".ruff_cache",
            ".tmp_pytest",
            ".tox",
            ".venv",
            "__pycache__",
            "build",
            "dist",
            "venv",
        }
        ignored.update(name for name in names if name.endswith(".egg-info"))
        ignored.update(name for name in names if name.startswith("pytest-cache-files-"))
        ignored.update(name for name in names if name.startswith("tmp_pytest"))
        return ignored & set(names)

    shutil.copytree(REPO_ROOT, source, ignore=ignore)
    return source


def _run_build(
    temp_root: Path,
    env: dict[str, str],
    *,
    timeout_seconds: int,
) -> tuple[StepResult, Path | None]:
    build_root = temp_root / "build-source"
    output_dir = temp_root / "dist"
    try:
        source = _copy_build_source(build_root)
    except OSError as exc:
        return StepResult("build", "FAIL", f"could not prepare isolated build source: {exc}"), None
    result = _run_command(
        "build",
        [sys.executable, "-m", "build", "--outdir", str(output_dir)],
        env=env,
        cwd=source,
        timeout_seconds=timeout_seconds,
    )
    if result.status == "PASS":
        _normalize_sdist_artifacts(output_dir, source_date_epoch=int(env["SOURCE_DATE_EPOCH"]))
    return result, output_dir if result.status == "PASS" else None


def _normalize_sdist_artifacts(output_dir: Path, *, source_date_epoch: int) -> None:
    for artifact in output_dir.glob("*.tar.gz"):
        _normalize_tar_gz(artifact, source_date_epoch=source_date_epoch)


def _normalize_tar_gz(path: Path, *, source_date_epoch: int) -> None:
    entries: list[tuple[str, tarfile.TarInfo, bytes | None]] = []
    with tarfile.open(path, "r:gz") as source:
        for member in source.getmembers():
            data: bytes | None = None
            if member.isfile():
                extracted = source.extractfile(member)
                data = b"" if extracted is None else extracted.read()
                member.size = len(data)
            member.mtime = source_date_epoch
            member.uid = 0
            member.gid = 0
            member.uname = ""
            member.gname = ""
            member.pax_headers = {}
            entries.append((member.name, member, data))

    tar_bytes = io.BytesIO()
    with tarfile.open(fileobj=tar_bytes, mode="w", format=tarfile.PAX_FORMAT) as target:
        for _name, member, data in sorted(entries, key=lambda item: item[0]):
            fileobj = io.BytesIO(data) if data is not None else None
            target.addfile(member, fileobj)

    with path.open("wb") as raw:
        with gzip.GzipFile(
            filename="",
            mode="wb",
            fileobj=raw,
            mtime=source_date_epoch,
        ) as compressed:
            compressed.write(tar_bytes.getvalue())


def _wheel_smoke(output_dir: Path | None) -> StepResult:
    if output_dir is None:
        return StepResult("wheel smoke", "FAIL", "build output is unavailable")
    wheels = sorted(output_dir.glob("*.whl"))
    if not wheels:
        return StepResult("wheel smoke", "FAIL", "no wheel was produced")
    wheel = wheels[-1]
    required_members = {"codex_agent_mem/schema.sql"}
    required_members.update(
        f"codex_agent_mem/templates/{path.name}"
        for path in (SRC_DIR / "codex_agent_mem" / "templates").glob("*.html")
    )
    required_members.update(
        f"codex_agent_mem/static/{path.name}"
        for path in (SRC_DIR / "codex_agent_mem" / "static").glob("*")
        if path.is_file()
    )
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
    required_members.update(
        member
        for member in names
        if member.endswith(".dist-info/licenses/LICENSE")
        or member.endswith(".dist-info/licenses/NOTICE")
    )
    if not any(member.endswith(".dist-info/licenses/LICENSE") for member in names):
        required_members.add("<wheel dist-info licenses/LICENSE>")
    if not any(member.endswith(".dist-info/licenses/NOTICE") for member in names):
        required_members.add("<wheel dist-info licenses/NOTICE>")
    missing = sorted(required_members - names)
    if missing:
        return StepResult("wheel smoke", "FAIL", "missing package data: " + ", ".join(missing))
    sdists = sorted(output_dir.glob("*.tar.gz"))
    if not sdists:
        return StepResult("wheel smoke", "FAIL", "no sdist was produced")
    with tarfile.open(sdists[-1], "r:gz") as archive:
        sdist_names = set(archive.getnames())
    if not any(name.endswith("/LICENSE") for name in sdist_names):
        return StepResult("wheel smoke", "FAIL", "sdist is missing LICENSE")
    if not any(name.endswith("/NOTICE") for name in sdist_names):
        return StepResult("wheel smoke", "FAIL", "sdist is missing NOTICE")
    print(f"PASS: wheel smoke ({wheel.name})")
    return StepResult("wheel smoke", "PASS")


def _parse_checksum_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    match = re.match(r"^([A-Fa-f0-9]{64})\s+\*?(.+)$", stripped)
    if match:
        return match.group(1).lower(), match.group(2).strip()
    parts = stripped.split()
    if len(parts) >= 2 and re.fullmatch(r"[A-Fa-f0-9]{64}", parts[-1]):
        return parts[-1].lower(), " ".join(parts[:-1]).strip()
    return None


def _artifact_files(output_dir: Path | None) -> list[Path]:
    if output_dir is None:
        return []
    return sorted(
        path
        for path in output_dir.iterdir()
        if path.is_file() and path.suffix in {".whl", ".gz"}
    )


def _resolve_export_dir(export_dir: Path) -> Path:
    return export_dir if export_dir.is_absolute() else REPO_ROOT / export_dir


def _export_artifacts(output_dir: Path | None, export_dir: Path) -> StepResult:
    artifacts = _artifact_files(output_dir)
    if len(artifacts) < 2:
        return StepResult("export artifacts", "FAIL", "build output does not contain wheel and sdist")
    target_dir = _resolve_export_dir(export_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for artifact in artifacts:
        target = target_dir / artifact.name
        shutil.copy2(artifact, target)
        copied_hash = hashlib.sha256(target.read_bytes()).hexdigest()
        source_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()
        if copied_hash != source_hash:
            return StepResult("export artifacts", "FAIL", f"copy verification failed for {artifact.name}")
        copied.append(target.name)
    relative_dir = (
        target_dir.relative_to(REPO_ROOT).as_posix()
        if target_dir.is_relative_to(REPO_ROOT)
        else str(target_dir)
    )
    print(f"PASS: exported artifacts ({relative_dir}: {', '.join(copied)})")
    return StepResult("export artifacts", "PASS")


def _checksum_path(release_version: str) -> Path:
    return REPO_ROOT / "docs" / "verification" / release_version / "checksums_sha256.txt"


def _write_checksums(release_version: str, output_dir: Path | None) -> StepResult:
    artifacts = _artifact_files(output_dir)
    if len(artifacts) < 2:
        return StepResult("write checksums", "FAIL", "build output does not contain wheel and sdist")
    checksum_path = _checksum_path(release_version)
    checksum_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# codex-agent-mem {release_version} release artifact checksums",
        "# Generated from isolated release build output.",
        "# File names refer to GitHub release assets, not a committed dist/ directory.",
        "# These hashes identify the official release assets built by the release gate.",
        "# They are not a cross-platform bit-for-bit reproducible-build guarantee.",
        f"# This file is excluded from the {release_version} sdist to avoid self-referential hashes.",
        "",
    ]
    for artifact in artifacts:
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        lines.append(f"{digest}  {artifact.name}")
    checksum_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"PASS: wrote checksums ({checksum_path.relative_to(REPO_ROOT).as_posix()})")
    return StepResult("write checksums", "PASS")


def _verify_checksums(release_version: str, output_dir: Path | None) -> StepResult:
    artifacts = {path.name: path for path in _artifact_files(output_dir)}
    if not artifacts:
        return StepResult("checksums", "FAIL", "build output is unavailable")
    checksum_path = (
        REPO_ROOT / "docs" / "verification" / release_version / "checksums_sha256.txt"
    )
    if not checksum_path.exists():
        return StepResult(
            "checksums",
            "FAIL",
            f"missing {checksum_path.relative_to(REPO_ROOT).as_posix()}",
        )
    failures: list[str] = []
    checked = 0
    checksum_lines = checksum_path.read_text(encoding="utf-8").splitlines()
    for line_no, line in enumerate(checksum_lines, start=1):
        parsed = _parse_checksum_line(line)
        if parsed is None:
            if line.strip() and not line.lstrip().startswith("#"):
                failures.append(f"line {line_no}: unsupported checksum format")
            continue
        expected_hash, relative_name = parsed
        target_name = Path(relative_name).name
        target = artifacts.get(target_name)
        if target is None:
            failures.append(f"line {line_no}: built artifact is missing {target_name}")
            continue
        actual_hash = hashlib.sha256(target.read_bytes()).hexdigest()
        checked += 1
        if actual_hash != expected_hash:
            failures.append(f"line {line_no}: checksum mismatch for {relative_name}")
    if failures:
        return StepResult("checksums", "FAIL", "; ".join(failures[:8]))
    if checked == 0:
        return StepResult("checksums", "FAIL", "no checksum entries were checked")
    print(f"PASS: checksums ({checked} file(s))")
    return StepResult("checksums", "PASS")


def _final_requested(args: argparse.Namespace) -> bool:
    return bool(args.final)


def _ensure_final_has_no_dev_skips(args: argparse.Namespace) -> None:
    if not _final_requested(args):
        return
    if getattr(args, "write_checksums", False):
        raise SystemExit("Final release gate cannot modify checksum files; run --write-checksums before --final.")
    skipped = [
        name
        for name in (
            "dev_skip_hygiene",
            "dev_skip_compileall",
            "dev_skip_pytest",
            "dev_skip_mcp_contract",
            "dev_skip_ruff",
            "dev_skip_build",
            "dev_skip_wheel_smoke",
            "dev_skip_checksums",
        )
        if getattr(args, name)
    ]
    if skipped:
        names = ", ".join("--" + name.replace("_", "-") for name in skipped)
        raise SystemExit(f"Final release gate cannot use development skip flags: {names}")


def _print_summary(results: list[StepResult]) -> int:
    print("\nSummary:")
    for result in results:
        detail = f" - {result.detail}" if result.detail else ""
        print(f"{result.status}: {result.name}{detail}")
    failed = [result for result in results if result.status == "FAIL"]
    if failed:
        print(f"\nFAIL: {len(failed)} release smoke step(s) failed")
        return 1
    skipped = [result for result in results if result.status == "SKIP"]
    if skipped:
        print(f"\nPASS with development skips: {len(skipped)} step(s) skipped")
    else:
        print("\nPASS: release smoke completed")
    return 0


def _has_failures(results: list[StepResult]) -> bool:
    return any(result.status == "FAIL" for result in results)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the codex-agent-mem release smoke gate."
    )
    parser.add_argument(
        "--final",
        action="store_true",
        help="Run the full final gate and reject dev skips.",
    )
    parser.add_argument("--with-ruff", action="store_true", help="Run ruff check.")
    parser.add_argument(
        "--with-build",
        action="store_true",
        help="Build sdist and wheel in an isolated temp tree.",
    )
    parser.add_argument(
        "--with-wheel-smoke",
        action="store_true",
        help="Verify package data in the built wheel.",
    )
    parser.add_argument("--with-checksums", action="store_true", help="Verify release checksums.")
    parser.add_argument(
        "--write-checksums",
        action="store_true",
        help="Build artifacts and write docs/verification/<version>/checksums_sha256.txt.",
    )
    parser.add_argument(
        "--export-artifacts-dir",
        type=Path,
        help="Copy verified wheel/sdist release assets to this ignored local directory.",
    )
    parser.add_argument(
        "--mcp-subprocess",
        action="store_true",
        help="Use real stdio subprocess for MCP smoke.",
    )
    parser.add_argument("--release-version", default="v1.0.2")
    parser.add_argument("--step-timeout-seconds", type=int, default=300)
    parser.add_argument("--dev-skip-hygiene", action="store_true")
    parser.add_argument("--dev-skip-compileall", action="store_true")
    parser.add_argument("--dev-skip-pytest", action="store_true")
    parser.add_argument("--dev-skip-mcp-contract", action="store_true")
    parser.add_argument("--dev-skip-ruff", action="store_true")
    parser.add_argument("--dev-skip-build", action="store_true")
    parser.add_argument("--dev-skip-wheel-smoke", action="store_true")
    parser.add_argument("--dev-skip-checksums", action="store_true")
    args = parser.parse_args(argv)
    _ensure_final_has_no_dev_skips(args)

    if args.final:
        args.with_ruff = True
        args.with_build = True
        args.with_wheel_smoke = True
        args.with_checksums = True
    if args.write_checksums:
        args.with_build = True
        args.with_wheel_smoke = True
    if args.export_artifacts_dir:
        args.with_build = True
        args.with_wheel_smoke = True

    results: list[StepResult] = []
    with tempfile.TemporaryDirectory(prefix="codex-agent-mem-release-smoke-") as tmp:
        temp_root = Path(tmp)
        env = _python_env(temp_root)

        if args.dev_skip_hygiene:
            results.append(_skip("hygiene", "development skip requested"))
        else:
            hygiene_command = [
                sys.executable,
                str(SCRIPTS_DIR / "check_repo_hygiene.py"),
                "--root",
                str(REPO_ROOT),
                "--release-version",
                args.release_version,
            ]
            if args.final or args.with_checksums:
                hygiene_command.append("--strict-checksums")
            results.append(
                _run_command(
                    "hygiene",
                    hygiene_command,
                    env=env,
                    timeout_seconds=args.step_timeout_seconds,
                )
            )

        if args.dev_skip_compileall:
            results.append(_skip("compileall", "development skip requested"))
        else:
            results.append(
                _run_command(
                    "compileall",
                    [
                        sys.executable,
                        "-m",
                        "compileall",
                        "-q",
                        str(SRC_DIR),
                        str(SCRIPTS_DIR),
                        str(TESTS_DIR),
                    ],
                    env=env,
                    timeout_seconds=args.step_timeout_seconds,
                )
            )

        if args.dev_skip_pytest:
            results.append(_skip("pytest", "development skip requested"))
        else:
            results.append(
                _run_command(
                    "pytest",
                    [
                        sys.executable,
                        "-m",
                        "pytest",
                        "-q",
                        "-p",
                        "no:cacheprovider",
                        str(TESTS_DIR),
                    ],
                    env=env,
                    timeout_seconds=args.step_timeout_seconds,
                )
            )

        if args.dev_skip_mcp_contract:
            results.append(_skip("MCP contract smoke", "development skip requested"))
        else:
            mcp_command = [sys.executable, str(SCRIPTS_DIR / "mcp_contract_smoke.py")]
            if args.mcp_subprocess:
                mcp_command.append("--subprocess")
            results.append(
                _run_command(
                    "MCP contract smoke",
                    mcp_command,
                    env=env,
                    timeout_seconds=args.step_timeout_seconds,
                )
            )

        if args.with_ruff:
            if args.dev_skip_ruff:
                results.append(_skip("ruff", "development skip requested"))
            else:
                results.append(
                    _run_command(
                        "ruff",
                        [sys.executable, "-m", "ruff", "check", "--no-cache", "."],
                        env=env,
                        timeout_seconds=args.step_timeout_seconds,
                    )
                )
        elif args.dev_skip_ruff:
            results.append(_skip("ruff", "development skip requested"))

        if _has_failures(results):
            return _print_summary(results)

        build_output: Path | None = None
        build_needed = args.with_build or args.with_wheel_smoke
        if build_needed:
            if args.dev_skip_build:
                results.append(_skip("build", "development skip requested"))
            else:
                build_result, build_output = _run_build(
                    temp_root,
                    env,
                    timeout_seconds=args.step_timeout_seconds,
                )
                results.append(build_result)
        elif args.dev_skip_build:
            results.append(_skip("build", "development skip requested"))

        if args.with_wheel_smoke:
            if args.dev_skip_wheel_smoke:
                results.append(_skip("wheel smoke", "development skip requested"))
            else:
                results.append(_wheel_smoke(build_output))
        elif args.dev_skip_wheel_smoke:
            results.append(_skip("wheel smoke", "development skip requested"))

        if _has_failures(results):
            return _print_summary(results)

        if args.write_checksums:
            results.append(_write_checksums(args.release_version, build_output))

        if args.with_checksums:
            if args.dev_skip_checksums:
                results.append(_skip("checksums", "development skip requested"))
            else:
                results.append(_verify_checksums(args.release_version, build_output))
        elif args.dev_skip_checksums:
            results.append(_skip("checksums", "development skip requested"))

        if _has_failures(results):
            return _print_summary(results)

        if args.export_artifacts_dir:
            results.append(_export_artifacts(build_output, args.export_artifacts_dir))

    return _print_summary(results)


if __name__ == "__main__":
    raise SystemExit(main())
