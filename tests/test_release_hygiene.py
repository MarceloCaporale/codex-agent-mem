import hashlib
import importlib.util
import sys
from pathlib import Path


def load_hygiene_module():
    script = Path(__file__).resolve().parents[1] / "scripts" / "check_repo_hygiene.py"
    spec = importlib.util.spec_from_file_location("check_repo_hygiene", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_smoke_module():
    script = Path(__file__).resolve().parents[1] / "scripts" / "smoke_release.py"
    spec = importlib.util.spec_from_file_location("smoke_release", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_historical_verification_checksum_requires_local_target(tmp_path):
    hygiene = load_hygiene_module()
    root = tmp_path
    (root / "docs" / "verification" / "v1.0.0").mkdir(parents=True)
    checksum = root / "docs" / "verification" / "v1.0.0" / "checksums_sha256.txt"
    checksum.write_text(f"{'0' * 64}  missing.json\n", encoding="utf-8")

    findings = hygiene.collect_findings(
        root,
        release_version="v1.0.1",
        strict_checksums=False,
        strict_language=True,
        skip_language=True,
        max_language_findings=40,
    )

    assert any(
        finding.severity == "error" and "checksum target is missing" in finding.message
        for finding in findings
    )


def test_current_release_checksum_allows_external_artifact_names(tmp_path):
    hygiene = load_hygiene_module()
    root = tmp_path
    (root / "docs" / "verification" / "v1.0.1").mkdir(parents=True)
    checksum = root / "docs" / "verification" / "v1.0.1" / "checksums_sha256.txt"
    checksum.write_text(
        "\n".join(
            [
                f"{hashlib.sha256(b'wheel').hexdigest()}  codex_agent_mem-1.0.1-py3-none-any.whl",
                f"{hashlib.sha256(b'sdist').hexdigest()}  codex_agent_mem-1.0.1.tar.gz",
                "",
            ]
        ),
        encoding="utf-8",
    )

    findings = hygiene.collect_findings(
        root,
        release_version="v1.0.1",
        strict_checksums=True,
        strict_language=True,
        skip_language=True,
        max_language_findings=40,
    )

    assert not any(finding.severity == "error" for finding in findings)


def test_current_release_checksum_rejects_path_targets(tmp_path):
    hygiene = load_hygiene_module()
    root = tmp_path
    (root / "docs" / "verification" / "v1.0.1").mkdir(parents=True)
    checksum = root / "docs" / "verification" / "v1.0.1" / "checksums_sha256.txt"
    checksum.write_text(f"{hashlib.sha256(b'bad').hexdigest()}  dist/file.whl\n", encoding="utf-8")

    findings = hygiene.collect_findings(
        root,
        release_version="v1.0.1",
        strict_checksums=True,
        strict_language=True,
        skip_language=True,
        max_language_findings=40,
    )

    assert any(
        finding.severity == "error" and "plain artifact file name" in finding.message
        for finding in findings
    )


def test_private_local_markers_are_release_hygiene_errors(tmp_path):
    hygiene = load_hygiene_module()
    root = tmp_path
    (root / "docs" / "verification" / "v1.0.1").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "tests" / "fixture.txt").write_text(
        "Private path: C:\\PROJECT_local\\codex-agent-mem\n",
        encoding="utf-8",
    )
    (root / "docs" / "verification" / "v1.0.1" / "checksums_sha256.txt").write_text(
        f"{hashlib.sha256(b'wheel').hexdigest()}  codex_agent_mem-1.0.1-py3-none-any.whl\n",
        encoding="utf-8",
    )

    findings = hygiene.collect_findings(
        root,
        release_version="v1.0.1",
        strict_checksums=False,
        strict_language=True,
        skip_language=True,
        max_language_findings=40,
    )

    assert any(
        finding.severity == "error" and "private local path marker" in finding.message
        for finding in findings
    )


def test_private_user_and_root_workspace_paths_are_release_hygiene_errors(tmp_path):
    hygiene = load_hygiene_module()
    root = tmp_path
    (root / "docs" / "verification" / "v1.0.1").mkdir(parents=True)
    (root / "docs").mkdir(exist_ok=True)
    (root / "docs" / "fixture.md").write_text(
        "\n".join(
            [
                "User path: C:\\Users\\alice\\secret-workspace\\project",
                "Root workspace: F:\\__PRIVATE_WORKSPACE\\demo",
            ]
        ),
        encoding="utf-8",
    )
    (root / "docs" / "verification" / "v1.0.1" / "checksums_sha256.txt").write_text(
        f"{hashlib.sha256(b'wheel').hexdigest()}  codex_agent_mem-1.0.1-py3-none-any.whl\n",
        encoding="utf-8",
    )

    findings = hygiene.collect_findings(
        root,
        release_version="v1.0.1",
        strict_checksums=False,
        strict_language=True,
        skip_language=True,
        max_language_findings=40,
    )

    private_findings = [
        finding
        for finding in findings
        if finding.severity == "error" and "private local path marker" in finding.message
    ]
    assert len(private_findings) == 2


def test_public_placeholder_user_paths_are_allowed(tmp_path):
    hygiene = load_hygiene_module()
    root = tmp_path
    (root / "docs" / "verification" / "v1.0.1").mkdir(parents=True)
    (root / "docs" / "fixture.md").write_text(
        "Example path: C:\\Users\\YOU\\.codex_agent_mem\\codex_agent_mem.db\n",
        encoding="utf-8",
    )
    (root / "docs" / "verification" / "v1.0.1" / "checksums_sha256.txt").write_text(
        f"{hashlib.sha256(b'wheel').hexdigest()}  codex_agent_mem-1.0.1-py3-none-any.whl\n",
        encoding="utf-8",
    )

    findings = hygiene.collect_findings(
        root,
        release_version="v1.0.1",
        strict_checksums=False,
        strict_language=True,
        skip_language=True,
        max_language_findings=40,
    )

    assert not any(
        finding.severity == "error" and "private local path marker" in finding.message
        for finding in findings
    )


def test_export_artifacts_copies_wheel_and_sdist(tmp_path):
    smoke = load_smoke_module()
    output_dir = tmp_path / "dist"
    output_dir.mkdir()
    wheel = output_dir / "codex_agent_mem-1.0.1-py3-none-any.whl"
    sdist = output_dir / "codex_agent_mem-1.0.1.tar.gz"
    wheel.write_bytes(b"wheel")
    sdist.write_bytes(b"sdist")

    result = smoke._export_artifacts(output_dir, tmp_path / "release")

    assert result.status == "PASS"
    assert (tmp_path / "release" / wheel.name).read_bytes() == b"wheel"
    assert (tmp_path / "release" / sdist.name).read_bytes() == b"sdist"


def test_export_artifacts_requires_both_release_assets(tmp_path):
    smoke = load_smoke_module()
    output_dir = tmp_path / "dist"
    output_dir.mkdir()
    (output_dir / "codex_agent_mem-1.0.1-py3-none-any.whl").write_bytes(b"wheel")

    result = smoke._export_artifacts(output_dir, tmp_path / "release")

    assert result.status == "FAIL"
    assert "wheel and sdist" in result.detail
