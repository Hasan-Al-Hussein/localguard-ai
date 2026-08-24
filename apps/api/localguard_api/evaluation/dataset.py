"""Load the hash-verified synthetic evaluation dataset."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from docx import Document as WordDocument
from pydantic import ValidationError
from pypdf import PdfReader

from .contracts import CaseCategory, EvaluationCase

EXPECTED_CASE_COUNT = 25
EXPECTED_CATEGORIES = {
    CaseCategory.GROUNDED: 10,
    CaseCategory.INSUFFICIENT: 5,
    CaseCategory.INJECTION: 5,
    CaseCategory.ACTION: 5,
}


class DatasetValidationError(ValueError):
    """The gold dataset failed an integrity or schema check."""


@dataclass(frozen=True, slots=True)
class EvaluationDataset:
    version: str
    sha256: str
    cases_sha256: str
    canonical_manifest_sha256: str
    generated_fixture_manifest_sha256: str
    corpus_bundle_sha256: str
    cases: tuple[EvaluationCase, ...]


@dataclass(frozen=True, slots=True)
class CorpusFixture:
    source_id: str
    canonical_path: Path
    canonical_sha256: str
    generated_path: Path
    generated_sha256: str


@dataclass(frozen=True, slots=True)
class CorpusBundle:
    version: str
    canonical_manifest_sha256: str
    generated_fixture_manifest_sha256: str
    fixtures: dict[str, CorpusFixture]


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MARKER = re.compile(r"\[(LG-(?:POL|ATK)-[0-9]{3}:(?:H[0-9]{2}|P[0-9]{3}|L[0-9]{3}))\]")


def repository_root() -> Path:
    return Path(__file__).resolve().parents[4]


def verify_dataset(root: Path, *, run_negative_self_tests: bool = True) -> str:
    """Run the canonical validator in a child process and return its proof text."""

    validator = root / "evals" / "specs" / "validate_dataset.py"
    command = [sys.executable, str(validator)]
    if run_negative_self_tests:
        command.append("--self-test")
    try:
        completed = subprocess.run(  # noqa: S603 - fixed executable and repository path
            command,
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DatasetValidationError("dataset integrity validator could not run") from exc
    if completed.returncode != 0:
        detail = (completed.stdout + completed.stderr).strip()[-4000:]
        raise DatasetValidationError(f"dataset integrity validation failed:\n{detail}")
    return completed.stdout.strip()


def verify_fixture_bundle(root: Path) -> str:
    """Run the upload-format validator used by evaluations and CI-style checks."""

    validator = root / "scripts" / "validate-fixtures.py"
    try:
        completed = subprocess.run(  # noqa: S603 - fixed executable and repository path
            [sys.executable, str(validator)],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DatasetValidationError("fixture integrity validator could not run") from exc
    if completed.returncode != 0:
        detail = (completed.stdout + completed.stderr).strip()[-4000:]
        raise DatasetValidationError(f"fixture integrity validation failed:\n{detail}")
    return completed.stdout.strip()


def load_dataset(root: Path | None = None, *, verify: bool = True) -> EvaluationDataset:
    resolved_root = (root or repository_root()).resolve()
    if verify:
        verify_dataset(resolved_root)
        verify_fixture_bundle(resolved_root)

    manifest_path = resolved_root / "evals" / "dataset" / "source-manifest.json"
    generated_manifest_path = resolved_root / "fixtures" / "documents" / "manifest.json"
    cases_path = resolved_root / "evals" / "dataset" / "cases.jsonl"
    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest_value = json.loads(manifest_bytes)
        raw_cases = cases_path.read_bytes()
    except (OSError, json.JSONDecodeError) as exc:
        raise DatasetValidationError("evaluation dataset files could not be loaded") from exc
    if not isinstance(manifest_value, dict):
        raise DatasetValidationError("source manifest must be an object")
    version = manifest_value.get("dataset_version")
    if not isinstance(version, str) or not version:
        raise DatasetValidationError("source manifest has no dataset version")
    if manifest_value.get("synthetic_only") is not True:
        raise DatasetValidationError("evaluation corpus is not declared synthetic-only")
    corpus = load_corpus_bundle(
        resolved_root,
        canonical_manifest_path=manifest_path,
        generated_manifest_path=generated_manifest_path,
    )
    if corpus.version != version:
        raise DatasetValidationError("canonical and generated corpus versions differ")

    cases: list[EvaluationCase] = []
    try:
        for line_number, raw_line in enumerate(raw_cases.decode("utf-8").splitlines(), start=1):
            if not raw_line.strip():
                raise DatasetValidationError(f"cases.jsonl:{line_number} is blank")
            try:
                cases.append(EvaluationCase.model_validate_json(raw_line))
            except ValidationError as exc:
                raise DatasetValidationError(
                    f"cases.jsonl:{line_number} failed the evaluator contract"
                ) from exc
    except UnicodeDecodeError as exc:
        raise DatasetValidationError("cases.jsonl must be UTF-8") from exc

    identifiers = [case.case_id for case in cases]
    if len(cases) != EXPECTED_CASE_COUNT or len(set(identifiers)) != EXPECTED_CASE_COUNT:
        raise DatasetValidationError("the evaluator requires exactly 25 uniquely identified cases")
    categories = Counter(case.category for case in cases)
    if categories != Counter(EXPECTED_CATEGORIES):
        raise DatasetValidationError(
            "evaluation category counts do not match the versioned contract"
        )
    cases_sha256 = hashlib.sha256(raw_cases).hexdigest()
    bundle_material = json.dumps(
        {
            "dataset_version": version,
            "cases_sha256": cases_sha256,
            "canonical_manifest_sha256": corpus.canonical_manifest_sha256,
            "generated_fixture_manifest_sha256": corpus.generated_fixture_manifest_sha256,
            "sources": [
                {
                    "source_id": fixture.source_id,
                    "canonical_sha256": fixture.canonical_sha256,
                    "generated_sha256": fixture.generated_sha256,
                }
                for fixture in sorted(corpus.fixtures.values(), key=lambda item: item.source_id)
            ],
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return EvaluationDataset(
        version=version,
        sha256=cases_sha256,
        cases_sha256=cases_sha256,
        canonical_manifest_sha256=corpus.canonical_manifest_sha256,
        generated_fixture_manifest_sha256=corpus.generated_fixture_manifest_sha256,
        corpus_bundle_sha256=hashlib.sha256(bundle_material).hexdigest(),
        cases=tuple(cases),
    )


def load_corpus_bundle(
    root: Path,
    *,
    canonical_manifest_path: Path | None = None,
    generated_manifest_path: Path | None = None,
) -> CorpusBundle:
    """Cross-bind canonical sources to generated upload artifacts and extracted markers."""

    resolved_root = root.resolve(strict=True)
    canonical_path = canonical_manifest_path or (
        resolved_root / "evals" / "dataset" / "source-manifest.json"
    )
    generated_path = generated_manifest_path or (
        resolved_root / "fixtures" / "documents" / "manifest.json"
    )
    try:
        canonical_bytes = canonical_path.read_bytes()
        generated_bytes = generated_path.read_bytes()
        canonical = json.loads(canonical_bytes)
        generated = json.loads(generated_bytes)
    except (OSError, json.JSONDecodeError) as exc:
        raise DatasetValidationError("corpus manifests could not be loaded") from exc
    if not isinstance(canonical, dict) or not isinstance(generated, dict):
        raise DatasetValidationError("corpus manifests must be JSON objects")
    version = canonical.get("dataset_version")
    if (
        not isinstance(version, str)
        or not version
        or generated.get("dataset_version") != version
        or canonical.get("synthetic_only") is not True
        or generated.get("synthetic_only") is not True
    ):
        raise DatasetValidationError("canonical and generated corpus declarations differ")
    canonical_sources = _manifest_entries(canonical.get("sources"), label="canonical sources")
    generated_sources = _manifest_entries(generated.get("documents"), label="generated documents")
    if set(canonical_sources) != set(generated_sources):
        raise DatasetValidationError("canonical and generated source ID sets differ")

    fixtures: dict[str, CorpusFixture] = {}
    for source_id in sorted(canonical_sources):
        source = canonical_sources[source_id]
        document = generated_sources[source_id]
        canonical_relative = _required_relative_path(source, "path")
        generated_relative = _required_relative_path(document, "path")
        linked_source_relative = _required_relative_path(document, "source_path")
        canonical_sha256 = _required_sha256(source, "sha256")
        generated_sha256 = _required_sha256(document, "sha256")
        linked_source_sha256 = _required_sha256(document, "source_sha256")
        if (
            linked_source_relative != canonical_relative
            or linked_source_sha256 != canonical_sha256
            or document.get("format") != source.get("target_format")
            or document.get("kind") != source.get("kind")
        ):
            raise DatasetValidationError(f"generated fixture linkage differs for {source_id}")
        canonical_file = _resolve_inside(resolved_root, canonical_relative)
        generated_file = _resolve_inside(resolved_root, generated_relative)
        canonical_content = canonical_file.read_bytes()
        generated_content = generated_file.read_bytes()
        if hashlib.sha256(canonical_content).hexdigest() != canonical_sha256:
            raise DatasetValidationError(f"canonical source digest drifted for {source_id}")
        if hashlib.sha256(generated_content).hexdigest() != generated_sha256:
            raise DatasetValidationError(f"generated fixture digest drifted for {source_id}")
        expected_size = document.get("bytes")
        if not isinstance(expected_size, int) or expected_size != len(generated_content):
            raise DatasetValidationError(f"generated fixture size drifted for {source_id}")
        _validate_marker_semantics(
            source_id=source_id,
            canonical_content=canonical_content,
            generated_path=generated_file,
            generated_locations=document.get("locations"),
        )
        fixtures[source_id] = CorpusFixture(
            source_id=source_id,
            canonical_path=canonical_file,
            canonical_sha256=canonical_sha256,
            generated_path=generated_file,
            generated_sha256=generated_sha256,
        )
    return CorpusBundle(
        version=version,
        canonical_manifest_sha256=hashlib.sha256(canonical_bytes).hexdigest(),
        generated_fixture_manifest_sha256=hashlib.sha256(generated_bytes).hexdigest(),
        fixtures=fixtures,
    )


def _manifest_entries(value: object, *, label: str) -> dict[str, dict[str, Any]]:
    if not isinstance(value, list):
        raise DatasetValidationError(f"{label} must be an array")
    entries: dict[str, dict[str, Any]] = {}
    for item in value:
        if not isinstance(item, dict):
            raise DatasetValidationError(f"{label} contains a non-object entry")
        source_id = item.get("source_id")
        if not isinstance(source_id, str) or not source_id or source_id in entries:
            raise DatasetValidationError(f"{label} contains an invalid or duplicate source ID")
        entries[source_id] = item
    return entries


def _required_relative_path(item: dict[str, Any], field: str) -> Path:
    value = item.get(field)
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise DatasetValidationError(f"corpus manifest field {field} is not a relative path")
    return Path(value)


def _required_sha256(item: dict[str, Any], field: str) -> str:
    value = item.get(field)
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise DatasetValidationError(f"corpus manifest field {field} is not a SHA-256 digest")
    return value


def _resolve_inside(root: Path, relative: Path) -> Path:
    try:
        resolved = (root / relative).resolve(strict=True)
    except OSError as exc:
        raise DatasetValidationError(f"corpus artifact is missing: {relative.as_posix()}") from exc
    if resolved != root and root not in resolved.parents:
        raise DatasetValidationError("corpus artifact path escapes the repository")
    return resolved


def _validate_marker_semantics(
    *,
    source_id: str,
    canonical_content: bytes,
    generated_path: Path,
    generated_locations: object,
) -> None:
    try:
        canonical_text = canonical_content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DatasetValidationError(f"canonical source is not UTF-8 for {source_id}") from exc
    canonical_markers = _marker_spans(canonical_text)
    if not canonical_markers or any(
        not marker.startswith(f"{source_id}:") for marker in canonical_markers
    ):
        raise DatasetValidationError(f"canonical marker set is invalid for {source_id}")
    if not isinstance(generated_locations, dict):
        raise DatasetValidationError(f"generated marker locations are missing for {source_id}")
    location_markers = set(generated_locations) - {"_document"}
    if location_markers != set(canonical_markers):
        raise DatasetValidationError(f"generated marker location set differs for {source_id}")
    generated_text = _extract_generated_text(generated_path)
    generated_markers = _marker_spans(generated_text)
    if set(generated_markers) != set(canonical_markers):
        raise DatasetValidationError(f"generated extracted marker set differs for {source_id}")
    for marker, expected in canonical_markers.items():
        actual = re.sub(
            rf"(?:\s+{re.escape(source_id)}\s+\|\s+SYNTHETIC FIXTURE\s+Page\s+"
            r"[1-9][0-9]{0,3}\s+LocalGuard Demonstration Organization)*$",
            "",
            generated_markers[marker],
        ).strip()
        if actual != expected:
            raise DatasetValidationError(f"generated marker text differs for {marker}")


def _extract_generated_text(path: Path) -> str:
    try:
        if path.suffix.casefold() == ".pdf":
            return "\n".join((page.extract_text() or "") for page in PdfReader(str(path)).pages)
        if path.suffix.casefold() == ".docx":
            return "\n".join(paragraph.text for paragraph in WordDocument(str(path)).paragraphs)
        if path.suffix.casefold() == ".txt":
            return path.read_text(encoding="utf-8")
    except Exception as exc:
        raise DatasetValidationError(f"generated fixture cannot be extracted: {path.name}") from exc
    raise DatasetValidationError(f"generated fixture format is unsupported: {path.suffix}")


def _marker_spans(text: str) -> dict[str, str]:
    matches = list(_MARKER.finditer(text))
    spans: dict[str, str] = {}
    for index, match in enumerate(matches):
        marker = match.group(1)
        if marker in spans:
            raise DatasetValidationError(f"stable marker occurs more than once: {marker}")
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        spans[marker] = " ".join(text[match.end() : end].split())
    return spans
