from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_DIR_NAMES = {
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "build",
    "dist",
}
IGNORED_WALK_DIRS = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".tox",
    ".venv",
    "node_modules",
    "venv",
}
LOCAL_ARTIFACT_SUFFIXES = (
    ".bak",
    ".db",
    ".db-shm",
    ".db-wal",
    ".log",
    ".orig",
    ".pid",
    ".sqlite",
    ".sqlite3",
    ".temp",
    ".tmp",
)
LOCAL_ARTIFACT_NAMES = {
    "events.jsonl",
}
TEXT_SUFFIXES = {
    ".cfg",
    ".css",
    ".example",
    ".html",
    ".in",
    ".ini",
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
PRIVATE_RELEASE_PATTERNS = (
    re.compile(
        r"\b[A-Z]:\\Users\\(?!YOU(?:\\|$)|USER(?:\\|$)|USERNAME(?:\\|$))[^\\\r\n\"']+",
        re.IGNORECASE,
    ),
    re.compile(r"\b[A-Z]:\\__[^\\\r\n\"']+", re.IGNORECASE),
    re.compile(
        r"\b[A-Z]:\\[^\\\r\n\"']*(?:feedback|private|scratch|tmp)[^\\\r\n\"']*",
        re.IGNORECASE,
    ),
    re.compile(r"\b[A-Z]:\\[^\\\r\n\"']*_local(?:\\|$)", re.IGNORECASE),
)
ROOT_MULTILINGUAL_READMES = {
    "README.md",
    "README_DE.md",
    "README_ES.md",
    "README_JA.md",
    "README_PT_BR.md",
    "README_ZH.md",
}
LANGUAGE_SUPPORT_FILES = {
    "src/codex_agent_mem/providers/noop.py",
}
SPANISH_TERMS = {
    "accion",
    "acciones",
    "archivo",
    "archivos",
    "auditoria",
    "cambios",
    "carpeta",
    "carpetas",
    "completado",
    "con",
    "debe",
    "deben",
    "documentacion",
    "ejecutivo",
    "espanol",
    "fase",
    "guia",
    "mantener",
    "objetivo",
    "para",
    "pendiente",
    "proyecto",
    "proyectos",
    "prueba",
    "pruebas",
    "publicacion",
    "resumen",
    "riesgo",
    "riesgos",
    "seguridad",
    "sin",
    "usar",
    "validacion",
}
SPANISH_ACCENT_RE = re.compile(
    "[\u00e1\u00e9\u00ed\u00f3\u00fa\u00fc\u00f1\u00bf\u00a1]",
    re.IGNORECASE,
)
CHECKSUM_LINE_RE = re.compile(r"^([A-Fa-f0-9]{64})\s+(.+?)\s*$")
WORD_RE = re.compile(r"\b[\w-]+\b", re.IGNORECASE)


@dataclass(frozen=True)
class Finding:
    severity: str
    path: str
    message: str


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _is_egg_info(path: Path) -> bool:
    return path.name.endswith(".egg-info")


def _is_local_artifact(path: Path) -> bool:
    name = path.name
    lower_name = name.casefold()
    if lower_name in LOCAL_ARTIFACT_NAMES:
        return True
    return any(lower_name.endswith(suffix) for suffix in LOCAL_ARTIFACT_SUFFIXES)


def _is_checksum_candidate(path: Path) -> bool:
    lower_name = path.name.casefold()
    return (
        lower_name in {"checksums_sha256.txt", "sha256sums", "sha256sums.txt"}
        or lower_name.endswith(".sha256")
    )


def _is_versioned_verification_checksum(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    return (
        len(rel.parts) == 4
        and rel.parts[0] == "docs"
        and rel.parts[1] == "verification"
        and rel.parts[2].startswith("v")
        and rel.parts[3] == "checksums_sha256.txt"
    )


def _is_private_verification_dir(path: Path, root: Path) -> bool:
    try:
        rel = path.relative_to(root)
    except ValueError:
        return False
    return (
        len(rel.parts) >= 3
        and rel.parts[0] == "docs"
        and rel.parts[1] == "verification"
        and path.name in {"runs", "export_public"}
    )


def _is_text_file(path: Path) -> bool:
    if path.name in {"LICENSE", "NOTICE", "MANIFEST.in"}:
        return True
    return path.suffix.casefold() in TEXT_SUFFIXES


def _is_git_ignored(path: Path, root: Path) -> bool:
    git_dir = root / ".git"
    if not git_dir.exists():
        return False
    rel_path = _rel(path, root)
    completed = subprocess.run(
        ["git", "-C", str(root), "check-ignore", "-q", "--", rel_path],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return completed.returncode == 0


def _language_scan_allowed(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    if len(rel.parts) == 1 and rel.name in ROOT_MULTILINGUAL_READMES:
        return True
    return rel.as_posix() in LANGUAGE_SUPPORT_FILES


def _looks_spanish(line: str) -> bool:
    if SPANISH_ACCENT_RE.search(line):
        return True
    words = {match.group(0).casefold() for match in WORD_RE.finditer(line)}
    return len(words & SPANISH_TERMS) >= 2


def _scan_spanish(path: Path, root: Path, *, max_findings: int) -> list[Finding]:
    if _language_scan_allowed(path, root) or not _is_text_file(path):
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    findings: list[Finding] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if _looks_spanish(line):
            snippet = line.strip()
            if len(snippet) > 120:
                snippet = snippet[:117] + "..."
            findings.append(
                Finding(
                    "error",
                    f"{_rel(path, root)}:{line_no}",
                    f"possible Spanish text outside multilingual README exception: {snippet}",
                )
            )
            if len(findings) >= max_findings:
                break
    return findings


def _scan_private_markers(path: Path, root: Path) -> list[Finding]:
    if not _is_text_file(path):
        return []
    rel_path = _rel(path, root)
    if rel_path == "scripts/check_repo_hygiene.py":
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (UnicodeDecodeError, OSError):
        return []
    findings: list[Finding] = []
    for line_no, line in enumerate(lines, start=1):
        for pattern in PRIVATE_RELEASE_PATTERNS:
            if pattern.search(line):
                findings.append(
                    Finding(
                        "error",
                        f"{rel_path}:{line_no}",
                        "private local path marker must not be published",
                    )
                )
                break
    return findings


def _verify_checksum_file(
    path: Path,
    root: Path,
    *,
    require_local_targets: bool,
) -> list[Finding]:
    findings: list[Finding] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return [
            Finding(
                "error",
                _rel(path, root),
                "checksum file must be UTF-8 text",
            )
        ]
    except OSError as exc:
        return [
            Finding(
                "error",
                _rel(path, root),
                f"checksum file cannot be read: {exc}",
            )
        ]

    for line_no, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = CHECKSUM_LINE_RE.match(line)
        if match is None:
            findings.append(
                Finding(
                    "error",
                    f"{_rel(path, root)}:{line_no}",
                    "invalid SHA-256 checksum line",
                )
            )
            continue
        expected_hash, target_name = match.groups()
        target_name = target_name.strip()
        if target_name.startswith("*"):
            target_name = target_name[1:]
        target_path = (path.parent / target_name).resolve()
        if Path(target_name).is_absolute() or not target_path.is_relative_to(root):
            findings.append(
                Finding(
                    "error",
                    f"{_rel(path, root)}:{line_no}",
                    "checksum target must stay inside the repository",
                )
            )
            continue
        if not require_local_targets:
            target = Path(target_name)
            if target.name != target_name or target_name in {".", ".."}:
                findings.append(
                    Finding(
                        "error",
                        f"{_rel(path, root)}:{line_no}",
                        "release checksum target must be a plain artifact file name",
                    )
                )
            continue
        if not target_path.exists() or not target_path.is_file():
            findings.append(
                Finding(
                    "error",
                    f"{_rel(path, root)}:{line_no}",
                    f"checksum target is missing: {target_name}",
                )
            )
            continue
        actual_hash = hashlib.sha256(target_path.read_bytes()).hexdigest()
        if actual_hash != expected_hash.casefold():
            findings.append(
                Finding(
                    "error",
                    _rel(path, root),
                    f"checksum mismatch for {target_name}: expected {expected_hash.casefold()}, got {actual_hash}",
                )
            )
    return findings


def _walk_repo(root: Path) -> tuple[list[Path], list[Path]]:
    dirs: list[Path] = []
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        kept_dirs: list[str] = []
        for dirname in dirnames:
            child = current / dirname
            if dirname in IGNORED_WALK_DIRS:
                continue
            dirs.append(child)
            if (
                dirname in FORBIDDEN_DIR_NAMES
                or dirname in {"temp", "tmp"}
                or _is_egg_info(child)
                or _is_private_verification_dir(child, root)
            ):
                continue
            if _is_git_ignored(child, root):
                continue
            kept_dirs.append(dirname)
        dirnames[:] = kept_dirs
        files.extend(current / filename for filename in filenames)
    return dirs, files


def collect_findings(
    root: Path,
    *,
    release_version: str,
    strict_checksums: bool,
    strict_language: bool,
    skip_language: bool,
    max_language_findings: int,
) -> list[Finding]:
    findings: list[Finding] = []
    dirs, files = _walk_repo(root)

    for path in dirs:
        if path.name in FORBIDDEN_DIR_NAMES or _is_egg_info(path):
            findings.append(
                Finding("error", _rel(path, root), "generated directory must not be published")
            )
        elif path.name in {"temp", "tmp"}:
            findings.append(
                Finding(
                    "error",
                    _rel(path, root),
                    "local temporary directory must not be published",
                )
            )
        elif _is_private_verification_dir(path, root):
            findings.append(
                Finding(
                    "error",
                    _rel(path, root),
                    "private verification runs/export_public directory must not be published",
                )
            )

    checksum_candidates: list[Path] = []
    for path in files:
        rel_path = _rel(path, root)
        if path.name == "uv.lock":
            if _is_git_ignored(path, root):
                findings.append(
                    Finding(
                        "warning",
                        rel_path,
                        "uv.lock is ignored locally and excluded from the public release policy",
                    )
                )
            else:
                findings.append(
                    Finding("error", rel_path, "uv.lock is not part of this public release policy")
                )
        if _is_egg_info(path):
            findings.append(
                Finding("error", rel_path, "generated egg-info file must not be published")
            )
        if _is_local_artifact(path):
            findings.append(
                Finding("error", rel_path, "local DB, log, or temporary artifact detected")
            )
        if _is_checksum_candidate(path):
            checksum_candidates.append(path)
        findings.extend(_scan_private_markers(path, root))
        if not skip_language:
            for finding in _scan_spanish(path, root, max_findings=max_language_findings):
                findings.append(
                    finding
                    if strict_language
                    else Finding("warning", finding.path, finding.message)
                )

    expected_checksum = root / "docs" / "verification" / release_version / "checksums_sha256.txt"
    for candidate in checksum_candidates:
        if (
            candidate.resolve() != expected_checksum.resolve()
            and not _is_versioned_verification_checksum(candidate, root)
        ):
            severity = "error" if strict_checksums else "warning"
            findings.append(
                Finding(
                    severity,
                    _rel(candidate, root),
                    f"checksum file is outside docs/verification/{release_version}/",
                )
            )
        if _is_versioned_verification_checksum(candidate, root):
            findings.extend(
                _verify_checksum_file(
                    candidate,
                    root,
                    require_local_targets=candidate.resolve() != expected_checksum.resolve(),
                )
            )
    if not expected_checksum.exists():
        severity = "error" if strict_checksums else "warning"
        findings.append(
            Finding(
                severity,
                _rel(expected_checksum, root),
                "expected release checksum file is missing",
            )
        )

    return findings


def _safe_console_text(text: str) -> str:
    encoding = sys.stdout.encoding or "utf-8"
    return text.encode(encoding, errors="backslashreplace").decode(encoding, errors="replace")


def _safe_print(text: str) -> None:
    print(_safe_console_text(text))


def print_findings(findings: list[Finding]) -> None:
    for finding in sorted(findings, key=lambda item: (item.severity, item.path, item.message)):
        _safe_print(f"{finding.severity.upper()}: {finding.path}: {finding.message}")
    errors = sum(1 for finding in findings if finding.severity == "error")
    warnings = sum(1 for finding in findings if finding.severity == "warning")
    if errors or warnings:
        _safe_print(f"Summary: {errors} error(s), {warnings} warning(s)")
    else:
        _safe_print("PASS: repository hygiene checks found no issues")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Report public release hygiene issues without deleting files."
    )
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="Repository root to scan.")
    parser.add_argument(
        "--release-version",
        default="v1.0.1",
        help="Release folder expected under docs/verification/.",
    )
    parser.add_argument(
        "--strict-checksums",
        action="store_true",
        help="Fail on missing or misplaced checksums.",
    )
    parser.add_argument(
        "--language-warning-only",
        action="store_true",
        help="Downgrade possible Spanish text findings to warnings.",
    )
    parser.add_argument(
        "--skip-language",
        action="store_true",
        help="Skip the heuristic Spanish text scan.",
    )
    parser.add_argument("--max-language-findings", type=int, default=40)
    parser.add_argument(
        "--warn-only",
        action="store_true",
        help="Print findings but return success.",
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()
    if not (root / "pyproject.toml").exists():
        print(
            f"FAIL: {root} does not look like the codex-agent-mem repository root",
            file=sys.stderr,
        )
        return 2

    findings = collect_findings(
        root,
        release_version=args.release_version,
        strict_checksums=args.strict_checksums,
        strict_language=not args.language_warning_only,
        skip_language=args.skip_language,
        max_language_findings=max(1, args.max_language_findings),
    )
    print_findings(findings)
    has_errors = any(finding.severity == "error" for finding in findings)
    return 0 if args.warn_only or not has_errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
