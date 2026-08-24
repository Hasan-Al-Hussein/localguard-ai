"""Read-only, version-aware API for generated evaluation evidence."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .dependencies import get_current_user, require_roles
from .errors import NotFoundError
from .evaluation.reporting import EvaluationSummary
from .evaluation.runner import RESULT_SCHEMA_VERSION, EvaluationRun
from .models import Role, User

evaluation_router = APIRouter(
    dependencies=[Depends(get_current_user)],
    tags=["evaluations"],
)
ReviewerRead = Annotated[User, Depends(require_roles(Role.REVIEWER, Role.ADMIN))]
_RUN_ID = re.compile(r"^[0-9]{8}T[0-9]{12}Z-(?:deterministic|ollama)-[0-9a-f]{12}$")
_RESULTS_ROOT = (Path.cwd() / "evals" / "results").resolve()
_MAX_RESULT_BYTES = 20 * 1024 * 1024
_LEGACY_SCHEMA_VERSIONS = frozenset({"1.0.0", "1.1.0"})

ComparabilityStatus = Literal["current", "legacy_metadata_only", "unavailable"]
IntegrityStatus = Literal[
    "summary_verified",
    "run_verified",
    "corrupt",
    "unsupported_schema",
    "hash_mismatch",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvaluationHistoryEntry(StrictModel):
    """Schema-stable metadata; unavailable values remain explicitly null."""

    schema_version: str | None = Field(default=None, max_length=32)
    run_id: str
    dataset_version: str | None = Field(default=None, max_length=80)
    dataset_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    requested_provider: Literal["fake", "ollama"] | None = None
    runtime_provider: Literal["deterministic", "ollama"] | None = None
    completed_case_count: int | None = Field(default=None, ge=0)
    case_count: int | None = Field(default=None, ge=0)
    safety_passed: bool | None = None
    quality_passed: bool | None = None
    run_passed: bool | None = None
    raw_result_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    comparability_status: ComparabilityStatus
    comparability_note: str
    integrity_status: IntegrityStatus
    integrity_note: str


class LegacyEvaluationRunMetadata(StrictModel):
    """Run metadata available in legacy files without projecting them into 1.2."""

    schema_version: Literal["1.0.0", "1.1.0"]
    run_id: str
    started_at: datetime
    completed_at: datetime
    wall_clock_ms: float = Field(ge=0)
    warmup_completed: bool


class EvaluationHistoryDetail(StrictModel):
    metadata: EvaluationHistoryEntry
    current_run: EvaluationRun | None = None
    legacy_run_metadata: LegacyEvaluationRunMetadata | None = None


class EvaluationHistoryList(StrictModel):
    items: list[EvaluationHistoryEntry]
    total: int
    offset: int
    limit: int


class _StoredEnvelope(StrictModel):
    model_config = ConfigDict(extra="allow")

    schema_version: str = Field(min_length=1, max_length=32)
    run_id: str


class _CommonAggregate(StrictModel):
    model_config = ConfigDict(extra="allow")

    completed_case_count: int = Field(ge=0)
    case_count: int = Field(ge=0)


class _CommonGates(StrictModel):
    model_config = ConfigDict(extra="allow")

    safety_passed: bool
    quality_passed: bool | None
    run_passed: bool


class _LegacySummary(StrictModel):
    model_config = ConfigDict(extra="allow")

    schema_version: Literal["1.0.0", "1.1.0"]
    run_id: str
    dataset_version: str = Field(min_length=1, max_length=80)
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    requested_provider: Literal["fake", "ollama"]
    runtime_provider: Literal["deterministic", "ollama"]
    raw_result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    aggregate: _CommonAggregate
    gates: _CommonGates


class _LegacyRun(StrictModel):
    model_config = ConfigDict(extra="allow")

    schema_version: Literal["1.0.0", "1.1.0"]
    run_id: str
    dataset_version: str = Field(min_length=1, max_length=80)
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    requested_provider: Literal["fake", "ollama"]
    runtime_provider: Literal["deterministic", "ollama"]
    started_at: datetime
    completed_at: datetime
    wall_clock_ms: float = Field(ge=0)
    warmup_completed: bool
    aggregate: _CommonAggregate
    gates: _CommonGates


class _OverviewSummary(StrictModel):
    run_id: str
    runtime_provider: Literal["deterministic", "ollama"]
    aggregate: _CommonAggregate
    gates: _CommonGates


class _StoredArtifactError(ValueError):
    """A safe, expected failure while inspecting stored evaluation evidence."""


class _SummaryRecord:
    __slots__ = ("entry", "summary")

    def __init__(
        self,
        entry: EvaluationHistoryEntry,
        summary: EvaluationSummary | _LegacySummary | None,
    ) -> None:
        self.entry = entry
        self.summary = summary


@evaluation_router.get("/evaluations", response_model=EvaluationHistoryList)
async def list_evaluations(
    actor: ReviewerRead,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> EvaluationHistoryList:
    del actor
    candidates = _run_candidates()
    return EvaluationHistoryList(
        items=[
            _summary_record(directory).entry for directory in candidates[offset : offset + limit]
        ],
        total=len(candidates),
        offset=offset,
        limit=limit,
    )


@evaluation_router.get("/evaluations/latest", response_model=EvaluationHistoryEntry)
async def latest_evaluation(actor: ReviewerRead) -> EvaluationHistoryEntry:
    del actor
    record = _latest_summary_record()
    if record is None:
        raise NotFoundError("Evaluation result")
    return record.entry


@evaluation_router.get("/evaluations/{run_id}", response_model=EvaluationHistoryDetail)
async def get_evaluation(run_id: str, actor: ReviewerRead) -> EvaluationHistoryDetail:
    del actor
    directory = _run_directory(run_id)
    record = _summary_record(directory)
    if record.summary is None:
        return EvaluationHistoryDetail(metadata=record.entry)

    try:
        raw_bytes, raw_payload = _read_bounded_object(directory / "run.json", directory)
    except _StoredArtifactError:
        return EvaluationHistoryDetail(metadata=_invalid_detail_entry(record.entry, "corrupt"))

    digest = hashlib.sha256(raw_bytes).hexdigest()
    if digest != record.summary.raw_result_sha256:
        return EvaluationHistoryDetail(
            metadata=_invalid_detail_entry(record.entry, "hash_mismatch")
        )

    try:
        envelope = _StoredEnvelope.model_validate(raw_payload)
        if envelope.run_id != run_id or envelope.schema_version != record.entry.schema_version:
            raise _StoredArtifactError("run identity differs from its summary")
        if envelope.schema_version == RESULT_SCHEMA_VERSION:
            current_run = EvaluationRun.model_validate(raw_payload)
            summary_matches = isinstance(
                record.summary, EvaluationSummary
            ) and _current_summary_matches_run(
                record.summary, current_run, raw_result_sha256=digest
            )
            if not summary_matches:
                raise _StoredArtifactError("summary metadata differs from its run")
            return EvaluationHistoryDetail(
                metadata=_verified_detail_entry(record.entry),
                current_run=current_run,
            )
        legacy_run = _LegacyRun.model_validate(raw_payload)
        if not isinstance(record.summary, _LegacySummary) or not _legacy_summary_matches_run(
            record.summary, legacy_run
        ):
            raise _StoredArtifactError("summary metadata differs from its run")
        return EvaluationHistoryDetail(
            metadata=_verified_detail_entry(record.entry),
            legacy_run_metadata=LegacyEvaluationRunMetadata(
                schema_version=legacy_run.schema_version,
                run_id=legacy_run.run_id,
                started_at=legacy_run.started_at,
                completed_at=legacy_run.completed_at,
                wall_clock_ms=legacy_run.wall_clock_ms,
                warmup_completed=legacy_run.warmup_completed,
            ),
        )
    except (ValidationError, _StoredArtifactError):
        return EvaluationHistoryDetail(metadata=_invalid_detail_entry(record.entry, "corrupt"))


def load_latest_summary() -> _OverviewSummary | None:
    """Return only verified, supported summary fields used by the overview route."""

    record = _latest_summary_record()
    if record is None:
        return None
    summary = record.summary
    if summary is None:
        return None
    return _OverviewSummary(
        run_id=summary.run_id,
        runtime_provider=summary.runtime_provider,
        aggregate=_CommonAggregate.model_validate(summary.aggregate, from_attributes=True),
        gates=_CommonGates.model_validate(summary.gates, from_attributes=True),
    )


def load_latest_history_entry() -> EvaluationHistoryEntry | None:
    """Expose integrity state to the overview without inventing unavailable metrics."""

    record = _latest_summary_record()
    return record.entry if record is not None else None


def _all_history_entries() -> list[EvaluationHistoryEntry]:
    return [_summary_record(directory).entry for directory in _run_candidates()]


def _latest_summary_record() -> _SummaryRecord | None:
    # Timestamp-prefixed run directories are authoritative; latest.json is only a mutable alias.
    candidates = _run_candidates()
    return _summary_record(candidates[0]) if candidates else None


def _run_candidates() -> list[Path]:
    if not _RESULTS_ROOT.is_dir():
        return []
    try:
        candidates = [child for child in _RESULTS_ROOT.iterdir() if _is_run_id(child.name)]
    except OSError:
        return []
    return sorted(candidates, key=lambda item: item.name, reverse=True)


def _summary_record(directory: Path) -> _SummaryRecord:
    expected_run_id = directory.name
    if directory.is_symlink() or not directory.is_dir():
        return _SummaryRecord(_unavailable_entry(expected_run_id, "corrupt"), None)
    schema_version: str | None = None
    try:
        _, payload = _read_bounded_object(directory / "summary.json", directory)
        envelope = _StoredEnvelope.model_validate(payload)
        schema_version = envelope.schema_version
        if envelope.run_id != expected_run_id:
            raise _StoredArtifactError("summary identity differs from its directory")
        if envelope.schema_version == RESULT_SCHEMA_VERSION:
            summary: EvaluationSummary | _LegacySummary = EvaluationSummary.model_validate(payload)
        elif envelope.schema_version in _LEGACY_SCHEMA_VERSIONS:
            summary = _LegacySummary.model_validate(payload)
        else:
            return _SummaryRecord(
                _unavailable_entry(
                    expected_run_id,
                    "unsupported_schema",
                    schema_version=envelope.schema_version,
                ),
                None,
            )
        return _SummaryRecord(_entry_from_summary(summary), summary)
    except (ValidationError, _StoredArtifactError):
        return _SummaryRecord(
            _unavailable_entry(
                expected_run_id,
                "corrupt",
                schema_version=schema_version,
            ),
            None,
        )


def _entry_from_summary(summary: EvaluationSummary | _LegacySummary) -> EvaluationHistoryEntry:
    is_current = summary.schema_version == RESULT_SCHEMA_VERSION
    return EvaluationHistoryEntry(
        schema_version=summary.schema_version,
        run_id=summary.run_id,
        dataset_version=summary.dataset_version,
        dataset_sha256=summary.dataset_sha256,
        requested_provider=summary.requested_provider,
        runtime_provider=summary.runtime_provider,
        completed_case_count=summary.aggregate.completed_case_count,
        case_count=summary.aggregate.case_count,
        safety_passed=summary.gates.safety_passed,
        quality_passed=summary.gates.quality_passed,
        run_passed=summary.gates.run_passed,
        raw_result_sha256=summary.raw_result_sha256,
        comparability_status="current" if is_current else "legacy_metadata_only",
        comparability_note=(
            f"Schema {RESULT_SCHEMA_VERSION} uses the current evaluation contract."
            if is_current
            else (
                f"Schema {summary.schema_version} is metadata-only and its metrics must not be "
                f"compared directly with schema {RESULT_SCHEMA_VERSION}."
            )
        ),
        integrity_status="summary_verified",
        integrity_note=(
            "The summary schema and directory identity were verified; open the detail endpoint "
            "to verify the exact run bytes."
        ),
    )


def _unavailable_entry(
    run_id: str,
    status: Literal["corrupt", "unsupported_schema"],
    *,
    schema_version: str | None = None,
) -> EvaluationHistoryEntry:
    if status == "unsupported_schema":
        integrity_note = "The stored summary uses an unsupported evaluation schema."
        comparability_note = "Metric comparability is unavailable for this schema."
    else:
        integrity_note = "The stored summary is missing, unsafe, malformed, or identity-mismatched."
        comparability_note = "Metric comparability cannot be established from this summary."
    return EvaluationHistoryEntry(
        schema_version=schema_version,
        run_id=run_id,
        comparability_status="unavailable",
        comparability_note=comparability_note,
        integrity_status=status,
        integrity_note=integrity_note,
    )


def _verified_detail_entry(entry: EvaluationHistoryEntry) -> EvaluationHistoryEntry:
    return entry.model_copy(
        update={
            "integrity_status": "run_verified",
            "integrity_note": (
                "The summary and run schemas, identities, and exact run-byte digest were verified."
            ),
        }
    )


def _invalid_detail_entry(
    entry: EvaluationHistoryEntry,
    status: Literal["corrupt", "hash_mismatch"],
) -> EvaluationHistoryEntry:
    note = (
        "The exact run bytes do not match the digest recorded by the summary."
        if status == "hash_mismatch"
        else "The stored run is missing, unsafe, malformed, or identity-mismatched."
    )
    return entry.model_copy(
        update={
            "comparability_status": "unavailable",
            "comparability_note": "Metric comparability cannot be established for this run.",
            "integrity_status": status,
            "integrity_note": note,
        }
    )


def _current_summary_matches_run(
    summary: EvaluationSummary,
    run: EvaluationRun,
    *,
    raw_result_sha256: str,
) -> bool:
    expected_payload: dict[str, object] = {}
    for field_name in EvaluationSummary.model_fields:
        if field_name == "raw_result_sha256":
            expected_payload[field_name] = raw_result_sha256
            continue
        if not hasattr(run, field_name):
            return False
        expected_payload[field_name] = getattr(run, field_name)
    try:
        expected = EvaluationSummary.model_validate(expected_payload)
    except ValidationError:
        return False
    return summary == expected


def _legacy_summary_matches_run(
    summary: _LegacySummary,
    run: _LegacyRun,
) -> bool:
    return (
        summary.schema_version == run.schema_version
        and summary.run_id == run.run_id
        and summary.dataset_version == run.dataset_version
        and summary.dataset_sha256 == run.dataset_sha256
        and summary.requested_provider == run.requested_provider
        and summary.runtime_provider == run.runtime_provider
        and summary.aggregate.completed_case_count == run.aggregate.completed_case_count
        and summary.aggregate.case_count == run.aggregate.case_count
        and summary.gates.safety_passed == run.gates.safety_passed
        and summary.gates.quality_passed == run.gates.quality_passed
        and summary.gates.run_passed == run.gates.run_passed
    )


def _run_directory(run_id: str) -> Path:
    if not _is_run_id(run_id):
        raise NotFoundError("Evaluation run")
    candidate = _RESULTS_ROOT / run_id
    if candidate.is_symlink():
        raise NotFoundError("Evaluation run")
    try:
        directory = candidate.resolve(strict=True)
    except OSError as exc:
        raise NotFoundError("Evaluation run") from exc
    if directory.parent != _RESULTS_ROOT or not directory.is_dir():
        raise NotFoundError("Evaluation run")
    return directory


def _is_run_id(value: str) -> bool:
    if _RUN_ID.fullmatch(value) is None:
        return False
    try:
        datetime.strptime(value[:22], "%Y%m%dT%H%M%S%fZ")
    except ValueError:
        return False
    return True


def _read_bounded_object(path: Path, expected_directory: Path) -> tuple[bytes, dict[str, object]]:
    if path.is_symlink():
        raise _StoredArtifactError("stored artifact is a symbolic link")
    try:
        resolved = path.resolve(strict=True)
        if resolved.parent != expected_directory or not resolved.is_file():
            raise _StoredArtifactError("stored artifact is outside its run directory")
        with resolved.open("rb") as handle:
            payload_bytes = handle.read(_MAX_RESULT_BYTES + 1)
    except OSError as exc:
        raise _StoredArtifactError("stored artifact could not be read") from exc
    if not payload_bytes or len(payload_bytes) > _MAX_RESULT_BYTES:
        raise _StoredArtifactError("stored artifact size is invalid")
    try:
        payload = json.loads(
            payload_bytes,
            object_pairs_hook=_unique_json_object,
            parse_constant=_reject_nonstandard_json_constant,
        )
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise _StoredArtifactError("stored artifact is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise _StoredArtifactError("stored artifact root is not an object")
    return payload_bytes, payload


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("stored artifact contains a duplicate JSON field")
        value[key] = item
    return value


def _reject_nonstandard_json_constant(value: str) -> None:
    raise ValueError(f"stored artifact contains the nonstandard JSON constant {value}")
