"""Version and integrity behavior for the read-only evaluation history API."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest
from localguard_api import evaluation_routes
from localguard_api.errors import NotFoundError
from localguard_api.evaluation.contracts import (
    Capability,
    EvaluationInput,
    ProviderCallDiagnostic,
    RuntimeModelIdentity,
    SystemCaseOutput,
)
from localguard_api.evaluation.dataset import load_dataset
from localguard_api.evaluation.reporting import write_run_artifacts
from localguard_api.evaluation.runner import RESULT_SCHEMA_VERSION, run_evaluation
from localguard_api.models import User

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
LEGACY_10_RUN_ID = "20260823T041508075000Z-deterministic-f828e5352d66"
LEGACY_11_RUN_ID = "20260823T110127376141Z-deterministic-f828e5352d66"
CURRENT_RUN_ID = "20260824T010000000000Z-deterministic-2237aa9ef1fd"
UNKNOWN_RUN_ID = "20260824T030000000000Z-deterministic-aaaaaaaaaaaa"
CORRUPT_RUN_ID = "20260824T020000000000Z-deterministic-bbbbbbbbbbbb"


class _NoCapabilitySystem:
    @property
    def capabilities(self) -> frozenset[Capability]:
        return frozenset()

    @property
    def provider_raw_response_capture_enabled(self) -> bool:
        return False

    async def run_case(self, request: EvaluationInput) -> SystemCaseOutput:
        del request
        raise AssertionError("a system without capabilities must not execute a case")

    async def runtime_identity(self) -> RuntimeModelIdentity:
        return RuntimeModelIdentity(
            provider="deterministic",
            chat_model_name="deterministic-history-test-chat-v1",
            embedding_model_name="deterministic-history-test-embedding-v1",
            runtime_version="in-process-test-v1",
        )

    def drain_provider_diagnostics(self) -> list[ProviderCallDiagnostic]:
        return []

    async def aclose(self) -> None:
        return None


def _actor() -> User:
    return cast(User, object())


def _write_legacy_run(results_root: Path, run_id: str) -> Path:
    schema_version = {
        LEGACY_10_RUN_ID: "1.0.0",
        LEGACY_11_RUN_ID: "1.1.0",
    }[run_id]
    shared_payload = {
        "schema_version": schema_version,
        "run_id": run_id,
        "dataset_version": "1.0.0",
        "dataset_sha256": "a" * 64,
        "requested_provider": "fake",
        "runtime_provider": "deterministic",
        "aggregate": {"completed_case_count": 25, "case_count": 25},
        "gates": {
            "safety_passed": True,
            "quality_passed": True,
            "run_passed": True,
        },
    }
    directory = results_root / run_id
    raw = _write_json(
        directory / "run.json",
        {
            **shared_payload,
            "started_at": "2026-08-23T04:15:08.075000Z",
            "completed_at": "2026-08-23T04:15:09.075000Z",
            "wall_clock_ms": 1000.0,
            "warmup_completed": True,
        },
    )
    _write_json(
        directory / "summary.json",
        {
            **shared_payload,
            "raw_result_sha256": hashlib.sha256(raw).hexdigest(),
        },
    )
    return directory


def _write_json(path: Path, payload: object) -> bytes:
    raw = (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return raw


def _read_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_bytes())
    assert isinstance(payload, dict)
    return payload


async def _write_current_run(results_root: Path) -> Path:
    dataset = load_dataset(ROOT, verify=False)
    one_case_dataset = replace(dataset, cases=(dataset.cases[0],))
    run = (
        await run_evaluation(
            one_case_dataset,
            _NoCapabilitySystem(),
            requested_provider="fake",
            runtime_provider="deterministic",
            warmup=False,
        )
    ).model_copy(update={"run_id": CURRENT_RUN_ID})
    return write_run_artifacts(run, results_root).run_directory


def _replace_nested(payload: dict[str, object], path: tuple[str, ...], value: object) -> None:
    parent = payload
    for field in path[:-1]:
        child = parent[field]
        assert isinstance(child, dict)
        parent = child
    parent[path[-1]] = value


@pytest.mark.asyncio
async def test_legacy_10_and_11_are_explicit_metadata_and_exact_hash_verified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_legacy_run(tmp_path, LEGACY_10_RUN_ID)
    _write_legacy_run(tmp_path, LEGACY_11_RUN_ID)
    monkeypatch.setattr(evaluation_routes, "_RESULTS_ROOT", tmp_path)

    legacy_10 = await evaluation_routes.get_evaluation(LEGACY_10_RUN_ID, _actor())
    legacy_11 = await evaluation_routes.get_evaluation(LEGACY_11_RUN_ID, _actor())

    for detail, version in ((legacy_10, "1.0.0"), (legacy_11, "1.1.0")):
        assert detail.metadata.schema_version == version
        assert detail.metadata.comparability_status == "legacy_metadata_only"
        assert detail.metadata.integrity_status == "run_verified"
        assert detail.current_run is None
        assert detail.legacy_run_metadata is not None
        assert detail.legacy_run_metadata.schema_version == version

    overview = evaluation_routes.load_latest_summary()
    assert overview is not None
    assert overview.run_id == LEGACY_11_RUN_ID


@pytest.mark.asyncio
async def test_current_schema_detail_returns_the_fully_validated_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _write_current_run(tmp_path)
    monkeypatch.setattr(evaluation_routes, "_RESULTS_ROOT", tmp_path)

    detail = await evaluation_routes.get_evaluation(CURRENT_RUN_ID, _actor())

    assert detail.metadata.schema_version == RESULT_SCHEMA_VERSION
    assert detail.metadata.comparability_status == "current"
    assert detail.metadata.integrity_status == "run_verified"
    assert detail.current_run is not None
    assert detail.current_run.run_id == CURRENT_RUN_ID
    assert detail.legacy_run_metadata is None


@pytest.mark.parametrize(
    ("field_path", "replacement"),
    [
        (("cases_sha256",), "e" * 64),
        (("canonical_manifest_sha256",), "d" * 64),
        (("generated_fixture_manifest_sha256",), "c" * 64),
        (("corpus_bundle_sha256",), "f" * 64),
        (("runtime_model_identity", "runtime_version"), "tampered-runtime-v2"),
        (("structured_extraction_mode",), "tampered-structured-mode"),
        (("action_proposal_mode",), "tampered-action-mode"),
        (("provider_raw_response_capture_enabled",), True),
        (("aggregate", "extraction", "f1"), 0.25),
        (("claim_provenance", "claim_bearing_case_count"), 1),
        (("gates", "failed_gates"), ["tampered_gate"]),
    ],
)
@pytest.mark.asyncio
async def test_current_summary_must_exactly_match_every_run_derived_field(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field_path: tuple[str, ...],
    replacement: object,
) -> None:
    directory = await _write_current_run(tmp_path)
    summary_payload = _read_json(directory / "summary.json")
    _replace_nested(summary_payload, field_path, replacement)
    _write_json(directory / "summary.json", summary_payload)
    monkeypatch.setattr(evaluation_routes, "_RESULTS_ROOT", tmp_path)

    detail = await evaluation_routes.get_evaluation(CURRENT_RUN_ID, _actor())

    assert detail.metadata.integrity_status == "corrupt"
    assert detail.current_run is None


@pytest.mark.asyncio
async def test_list_and_latest_surface_unknown_and_corrupt_entries_without_aborting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_legacy_run(tmp_path, LEGACY_11_RUN_ID)
    _write_json(
        tmp_path / UNKNOWN_RUN_ID / "summary.json",
        {"schema_version": "9.0.0", "run_id": UNKNOWN_RUN_ID},
    )
    corrupt_directory = tmp_path / CORRUPT_RUN_ID
    corrupt_directory.mkdir()
    (corrupt_directory / "summary.json").write_bytes(b"{not-json")
    monkeypatch.setattr(evaluation_routes, "_RESULTS_ROOT", tmp_path)

    page_one = await evaluation_routes.list_evaluations(_actor(), offset=0, limit=2)
    page_two = await evaluation_routes.list_evaluations(_actor(), offset=2, limit=2)
    latest = await evaluation_routes.latest_evaluation(_actor())

    assert page_one.total == 3
    assert [item.run_id for item in page_one.items] == [UNKNOWN_RUN_ID, CORRUPT_RUN_ID]
    assert [item.integrity_status for item in page_one.items] == [
        "unsupported_schema",
        "corrupt",
    ]
    assert page_one.items[0].schema_version == "9.0.0"
    assert page_one.items[0].dataset_version is None
    assert [item.run_id for item in page_two.items] == [LEGACY_11_RUN_ID]
    assert latest.run_id == UNKNOWN_RUN_ID
    assert latest.integrity_status == "unsupported_schema"


@pytest.mark.asyncio
async def test_latest_surfaces_a_corrupt_newest_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_legacy_run(tmp_path, LEGACY_11_RUN_ID)
    corrupt_directory = tmp_path / CORRUPT_RUN_ID
    corrupt_directory.mkdir()
    (corrupt_directory / "summary.json").write_bytes(b"{not-json")
    monkeypatch.setattr(evaluation_routes, "_RESULTS_ROOT", tmp_path)

    latest = await evaluation_routes.latest_evaluation(_actor())

    assert latest.run_id == CORRUPT_RUN_ID
    assert latest.integrity_status == "corrupt"


@pytest.mark.asyncio
async def test_pagination_reads_only_the_requested_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_ids = [
        f"20260824T0{hour}0000000000Z-deterministic-{str(hour) * 12}" for hour in range(1, 5)
    ]
    for run_id in run_ids:
        (tmp_path / run_id).mkdir()
    monkeypatch.setattr(evaluation_routes, "_RESULTS_ROOT", tmp_path)
    original = evaluation_routes._summary_record
    inspected: list[str] = []

    def track_summary(directory: Path) -> object:
        inspected.append(directory.name)
        return original(directory)

    monkeypatch.setattr(evaluation_routes, "_summary_record", track_summary)

    page = await evaluation_routes.list_evaluations(_actor(), offset=1, limit=2)

    assert page.total == 4
    assert [item.run_id for item in page.items] == list(reversed(run_ids))[1:3]
    assert inspected == list(reversed(run_ids))[1:3]


@pytest.mark.parametrize(
    "summary_bytes",
    [
        (b'{"schema_version":"9.0.0","run_id":"' + UNKNOWN_RUN_ID.encode() + b'","value":NaN}'),
        (
            b'{"schema_version":"9.0.0","run_id":"'
            + UNKNOWN_RUN_ID.encode()
            + b'","value":Infinity}'
        ),
        (
            b'{"schema_version":"9.0.0","run_id":"'
            + UNKNOWN_RUN_ID.encode()
            + b'","run_id":"'
            + UNKNOWN_RUN_ID.encode()
            + b'"}'
        ),
    ],
)
@pytest.mark.asyncio
async def test_nonstandard_or_ambiguous_json_is_corrupt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    summary_bytes: bytes,
) -> None:
    directory = tmp_path / UNKNOWN_RUN_ID
    directory.mkdir()
    (directory / "summary.json").write_bytes(summary_bytes)
    monkeypatch.setattr(evaluation_routes, "_RESULTS_ROOT", tmp_path)

    latest = await evaluation_routes.latest_evaluation(_actor())

    assert latest.integrity_status == "corrupt"


@pytest.mark.asyncio
async def test_detail_surfaces_exact_byte_hash_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = _write_legacy_run(tmp_path, LEGACY_11_RUN_ID)
    with (directory / "run.json").open("ab") as handle:
        handle.write(b" ")
    monkeypatch.setattr(evaluation_routes, "_RESULTS_ROOT", tmp_path)

    detail = await evaluation_routes.get_evaluation(LEGACY_11_RUN_ID, _actor())

    assert detail.metadata.integrity_status == "hash_mismatch"
    assert detail.metadata.comparability_status == "unavailable"
    assert detail.current_run is None
    assert detail.legacy_run_metadata is None


@pytest.mark.asyncio
async def test_summary_and_run_ids_must_match_their_requested_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    summary_swapped = _write_legacy_run(tmp_path, LEGACY_10_RUN_ID)
    summary_payload = _read_json(summary_swapped / "summary.json")
    summary_payload["run_id"] = LEGACY_11_RUN_ID
    _write_json(summary_swapped / "summary.json", summary_payload)

    run_swapped = _write_legacy_run(tmp_path, LEGACY_11_RUN_ID)
    run_payload = _read_json(run_swapped / "run.json")
    run_payload["run_id"] = LEGACY_10_RUN_ID
    raw = _write_json(run_swapped / "run.json", run_payload)
    summary_payload = _read_json(run_swapped / "summary.json")
    summary_payload["raw_result_sha256"] = hashlib.sha256(raw).hexdigest()
    _write_json(run_swapped / "summary.json", summary_payload)
    monkeypatch.setattr(evaluation_routes, "_RESULTS_ROOT", tmp_path)

    entries = {item.run_id: item for item in evaluation_routes._all_history_entries()}
    detail = await evaluation_routes.get_evaluation(LEGACY_11_RUN_ID, _actor())

    assert entries[LEGACY_10_RUN_ID].integrity_status == "corrupt"
    assert entries[LEGACY_10_RUN_ID].schema_version == "1.0.0"
    assert detail.metadata.integrity_status == "corrupt"


@pytest.mark.asyncio
async def test_traversal_and_directory_symlinks_cannot_escape_the_fixed_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside-history"
    outside.mkdir(exist_ok=True)
    linked_run_id = "20260824T040000000000Z-deterministic-cccccccccccc"
    try:
        os.symlink(outside, tmp_path / linked_run_id, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks are unavailable: {exc}")
    monkeypatch.setattr(evaluation_routes, "_RESULTS_ROOT", tmp_path)

    with pytest.raises(NotFoundError):
        await evaluation_routes.get_evaluation("../summary.json", _actor())
    with pytest.raises(NotFoundError):
        await evaluation_routes.get_evaluation(linked_run_id, _actor())

    entries = evaluation_routes._all_history_entries()
    assert len(entries) == 1
    assert entries[0].run_id == linked_run_id
    assert entries[0].integrity_status == "corrupt"


@pytest.mark.asyncio
async def test_artifact_symlink_and_size_limit_are_reported_as_corrupt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / LEGACY_10_RUN_ID
    directory.mkdir()
    outside_summary = tmp_path / "outside-summary.json"
    outside_summary.write_bytes(b"{}")
    try:
        os.symlink(outside_summary, directory / "summary.json")
    except OSError as exc:
        pytest.skip(f"file symlinks are unavailable: {exc}")
    monkeypatch.setattr(evaluation_routes, "_RESULTS_ROOT", tmp_path)

    linked_entry = (await evaluation_routes.list_evaluations(_actor(), 0, 25)).items[0]
    assert linked_entry.integrity_status == "corrupt"

    (directory / "summary.json").unlink()
    (directory / "summary.json").write_bytes(b"{}")
    monkeypatch.setattr(evaluation_routes, "_MAX_RESULT_BYTES", 1)
    oversized_entry = (await evaluation_routes.list_evaluations(_actor(), 0, 25)).items[0]
    assert oversized_entry.integrity_status == "corrupt"
