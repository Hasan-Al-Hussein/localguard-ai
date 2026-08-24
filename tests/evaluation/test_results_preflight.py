"""Security and workflow regressions for evaluation-results mount preparation."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from scripts.prepare_evaluation_results import (
    DIRECTORY_MODE,
    FILE_MODE,
    RESULTS_ROOT,
    ResultsPreflightError,
    normalize_results_tree,
    probe_results_tree,
)

pytestmark = [
    pytest.mark.unit,
    pytest.mark.skipif(os.name != "posix", reason="the preflight runs in a Linux container"),
]


def test_results_preflight_normalizes_only_tree_and_proves_atomic_nonroot_write(
    tmp_path: Path,
) -> None:
    root = tmp_path / "results"
    run_directory = root / "bounded-run"
    run_directory.mkdir(parents=True)
    result_file = run_directory / "run.json"
    result_file.write_text('{"measured": true}\n', encoding="utf-8")
    root.chmod(0o700)
    run_directory.chmod(0o777)
    result_file.chmod(0o600)

    normalize_results_tree(root, owner_uid=os.geteuid(), owner_gid=os.getegid())

    assert stat.S_IMODE(root.stat().st_mode) == DIRECTORY_MODE
    assert stat.S_IMODE(run_directory.stat().st_mode) == DIRECTORY_MODE
    assert stat.S_IMODE(result_file.stat().st_mode) == FILE_MODE
    before = sorted(item.relative_to(root) for item in root.rglob("*"))
    probe_results_tree(root, expected_uid=os.geteuid(), expected_gid=os.getegid())
    assert sorted(item.relative_to(root) for item in root.rglob("*")) == before


def test_results_preflight_rejects_symlink_without_touching_target(tmp_path: Path) -> None:
    root = tmp_path / "results"
    root.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("unchanged", encoding="utf-8")
    (root / "linked.json").symlink_to(outside)
    original_mode = stat.S_IMODE(outside.stat().st_mode)

    with pytest.raises(ResultsPreflightError, match="symbolic links"):
        normalize_results_tree(root, owner_uid=os.geteuid(), owner_gid=os.getegid())

    assert outside.read_text(encoding="utf-8") == "unchanged"
    assert stat.S_IMODE(outside.stat().st_mode) == original_mode


def test_results_preflight_rejects_hardlinks_and_special_files(tmp_path: Path) -> None:
    hardlink_root = tmp_path / "hardlink-results"
    hardlink_root.mkdir()
    original = hardlink_root / "run.json"
    original.write_text("{}", encoding="utf-8")
    os.link(original, hardlink_root / "linked.json")
    with pytest.raises(ResultsPreflightError, match="hard-linked"):
        normalize_results_tree(
            hardlink_root,
            owner_uid=os.geteuid(),
            owner_gid=os.getegid(),
        )

    special_root = tmp_path / "special-results"
    special_root.mkdir()
    os.mkfifo(special_root / "blocked")
    with pytest.raises(ResultsPreflightError, match="special files"):
        normalize_results_tree(
            special_root,
            owner_uid=os.geteuid(),
            owner_gid=os.getegid(),
        )


def test_results_probe_refuses_the_wrong_runtime_identity(tmp_path: Path) -> None:
    root = tmp_path / "results"
    root.mkdir(mode=DIRECTORY_MODE)

    with pytest.raises(ResultsPreflightError, match="configured non-root evaluator"):
        probe_results_tree(
            root,
            expected_uid=os.geteuid() + 1,
            expected_gid=os.getegid(),
        )
    assert list(root.iterdir()) == []


def test_official_evaluator_preflights_mount_before_starting_provider() -> None:
    evaluate_script = Path("scripts/evaluate.ps1").read_text(encoding="utf-8")
    common_script = Path("scripts/common.ps1").read_text(encoding="utf-8")

    assert Path("/workspace/evals/results") == RESULTS_ROOT
    assert evaluate_script.index("Initialize-LocalGuardEvaluationResults") < evaluate_script.index(
        "Invoke-EvaluationCompose -ProjectName $evaluationProject"
    )
    assert "--user', '0:0'" not in evaluate_script
    assert "type=bind,source=$resolvedPath,target=/workspace/evals/results" in common_script
    assert "foreach ($componentPath in @($rootPath, $evalsPath, $expectedPath))" in common_script
    assert "[IO.FileAttributes]::ReparsePoint" in common_script
    assert "$item.LinkType" in common_script
    assert "'--network', 'none', '--read-only'" in common_script
    assert "'--cap-drop', 'ALL', '--cap-add', 'CHOWN', '--cap-add', 'FOWNER'" in common_script
    assert "'--cap-add', 'DAC_READ_SEARCH'" in common_script
    assert "DAC_OVERRIDE" not in common_script
    assert "'--user', '10001:10001'" in common_script
    assert "scripts.prepare_evaluation_results', 'normalize'" in common_script
    assert "scripts.prepare_evaluation_results', 'probe'" in common_script


def test_official_evaluator_uses_a_disposable_provider_neutral_scope() -> None:
    evaluate_script = Path("scripts/evaluate.ps1").read_text(encoding="utf-8")

    assert "localguard-eval-$scopeSuffix" in evaluate_script
    assert "Assert-EvaluationProjectUnused" in evaluate_script
    assert "'up', '-d', '--wait', 'db', 'redis'" in evaluate_script
    assert "'api', 'alembic', 'upgrade', 'head'" in evaluate_script
    assert "'localguard_api.cli', 'setup-checkpoints'" in evaluate_script
    assert "${evaluationArtifactsVolume}:/workspace/artifacts" in evaluate_script
    assert "unexpected host bind mount" in evaluate_script
    assert "'down', '--volumes', '--remove-orphans'" in evaluate_script
    assert "verify isolated Docker scope removal" in evaluate_script

    ollama_branch = evaluate_script.split("if ($Provider -eq 'ollama')", maxsplit=1)[1]
    assert "'network', 'create', '--driver', 'bridge', '--internal'" in ollama_branch
    assert "'network', 'connect', $modelBridgeName, $evaluationContainerId" in ollama_branch
    assert "'network', 'connect', '--alias', 'ollama'" in ollama_branch
    assert "'--profile', 'app', 'config', '--format', 'json'" in ollama_branch
    assert ollama_branch.index("$mainOllamaNetworksCaptured = $true") < ollama_branch.index(
        "$composeConfig = Get-DefaultComposeOutput"
    )
    assert "com.docker.compose.project' -ne 'localguard'" in ollama_branch
    assert "verify main Ollama network restoration" in ollama_branch
    assert "localguard_backend" not in evaluate_script
