#!/usr/bin/env python3
"""Validate LocalGuard's synthetic corpus and deterministic gold dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPOSITORY_ROOT / "evals" / "dataset" / "source-manifest.json"
CASES_PATH = REPOSITORY_ROOT / "evals" / "dataset" / "cases.jsonl"
SCHEMA_PATH = REPOSITORY_ROOT / "evals" / "specs" / "evaluation-case.schema.json"

HASH_ALGORITHM = "sha256"
HASH_CANONICALIZATION = "raw_repository_bytes"
EXPECTED_HASHED_ARTIFACTS = {
    "evals/dataset/cases.jsonl",
    "evals/specs/dataset-spec.md",
    "evals/specs/evaluation-case.schema.json",
    "evals/specs/validate_dataset.py",
}

EXPECTED_SOURCE_COUNTS = {"clean": 8, "attack": 5}
EXPECTED_CATEGORY_COUNTS = {
    "grounded": 10,
    "insufficient": 5,
    "injection": 5,
    "action": 5,
}
EXPECTED_CASE_FIELDS = {
    "case_id",
    "category",
    "task_type",
    "user_role",
    "request",
    "corpus_scope",
    "expected_status",
    "expected_spans",
    "expected_claims",
    "expected_extractions",
    "expected_tool_trace",
    "expected_proposal",
    "approval_script",
    "missing_facts",
    "forbidden_outcomes",
}
EXPECTED_TASK_TYPES = {
    "grounded": {"question_answering", "structured_extraction"},
    "insufficient": {"insufficient_evidence"},
    "injection": {"prompt_injection"},
    "action": {"action_approval"},
}
EXPECTED_STATUSES = {
    "grounded": "answered",
    "insufficient": "unanswerable",
    "injection": "answered",
    "action": "approval_required",
}
CASE_PREFIXES = {
    "grounded": "LG-EVAL-GRD-",
    "insufficient": "LG-EVAL-INS-",
    "injection": "LG-EVAL-INJ-",
    "action": "LG-EVAL-ACT-",
}
ALLOWED_ROLES = {"viewer", "reviewer", "admin"}
ALLOWED_TOOLS = {
    "search_documents",
    "get_document_section",
    "propose_workflow_task",
    "list_pending_approvals",
    "get_audit_event",
}
READ_ONLY_TOOLS = {
    "search_documents",
    "get_document_section",
    "list_pending_approvals",
    "get_audit_event",
}
ALLOWED_FORBIDDEN_OUTCOMES = {
    "unsupported_claim_asserted",
    "invalid_citation_accepted",
    "document_instruction_followed",
    "role_escalated",
    "system_prompt_disclosed",
    "sensitive_configuration_disclosed",
    "external_network_request",
    "audit_suppressed",
    "forged_tool_call_executed",
    "proposal_created_without_user_action",
    "workflow_task_created_before_approval",
    "privileged_action_executed_without_approval",
    "proposal_payload_mutated_after_approval",
    "duplicate_task_created",
}

SOURCE_ID_PATTERN = re.compile(r"^LG-(?:POL|ATK)-\d{3}$")
CASE_ID_PATTERN = re.compile(r"^LG-EVAL-(?:GRD|INS|INJ|ACT)-\d{3}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
MARKER_PATTERN = re.compile(
    r"^\[(?P<marker>(?P<source>LG-(?:POL|ATK)-\d{3}):(?P<kind>H\d{2}|P\d{3}|L\d{3}))\]"
)
SOURCE_HEADER_PATTERN = re.compile(r"^SOURCE_ID:\s*(LG-(?:POL|ATK)-\d{3})\s*$", re.MULTILINE)
TARGET_FORMAT_PATTERN = re.compile(r"^TARGET_FORMAT:\s*(PDF|DOCX|TXT)\s*$", re.MULTILINE)

PRIVACY_PATTERNS = {
    "email address": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    "telephone number": re.compile(
        r"(?<!\w)(?:\+\d{1,3}[ .-])?(?:\(\d{3}\)[ .-]?|\d{3}[ .-])\d{3}[ .-]\d{4}(?!\w)"
    ),
    "government-style identifier": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "payment-card-like number": re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)"),
    "IP address": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "user-home path": re.compile(r"(?:[A-Z]:\\Users\\|/home/|/Users/)", re.IGNORECASE),
    "private key material": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "university-style identifier": re.compile(
        r"(?:[A-Z0-9.-]+\.ac\.ae|OneDrive\s+-\s+[A-Z0-9.-]+\.ac\.ae)", re.IGNORECASE
    ),
}


def add_error(errors: list[str], location: str, message: str) -> None:
    errors.append(f"{location}: {message}")


def read_json(path: Path, errors: list[str]) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        add_error(errors, str(path.relative_to(REPOSITORY_ROOT)), "file is missing")
    except json.JSONDecodeError as exc:
        add_error(
            errors,
            str(path.relative_to(REPOSITORY_ROOT)),
            f"invalid JSON at line {exc.lineno}: {exc.msg}",
        )
    return None


def repository_path(relative_value: str, location: str, errors: list[str]) -> Path | None:
    candidate = (REPOSITORY_ROOT / relative_value).resolve()
    if not candidate.is_relative_to(REPOSITORY_ROOT):
        add_error(errors, location, "path escapes the repository")
        return None
    return candidate


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source_file:
        for block in iter(lambda: source_file.read(64 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_file_hash(
    path: Path,
    expected_hash: Any,
    location: str,
    errors: list[str],
) -> None:
    if not isinstance(expected_hash, str) or not SHA256_PATTERN.fullmatch(expected_hash):
        add_error(errors, location, "sha256 must be a lowercase 64-character hexadecimal digest")
        return
    try:
        actual_hash = sha256_file(path)
    except FileNotFoundError:
        add_error(errors, location, f"hashed file is missing: {path.relative_to(REPOSITORY_ROOT)}")
        return
    except OSError as exc:
        add_error(errors, location, f"hashed file cannot be read: {exc}")
        return
    if actual_hash != expected_hash:
        add_error(
            errors,
            location,
            f"SHA-256 mismatch: expected {expected_hash}, calculated {actual_hash}",
        )


def validate_hash_contract(manifest: dict[str, Any], errors: list[str]) -> None:
    contract = manifest.get("hash_contract")
    if not isinstance(contract, dict):
        add_error(errors, "source-manifest.json", "hash_contract must be an object")
        return
    expected_fields = {"algorithm", "canonicalization", "artifacts"}
    if set(contract) != expected_fields:
        add_error(
            errors,
            "source-manifest.json hash_contract",
            f"fields must equal {sorted(expected_fields)}",
        )
    if contract.get("algorithm") != HASH_ALGORITHM:
        add_error(errors, "source-manifest.json hash_contract", "algorithm must be sha256")
    if contract.get("canonicalization") != HASH_CANONICALIZATION:
        add_error(
            errors,
            "source-manifest.json hash_contract",
            f"canonicalization must be {HASH_CANONICALIZATION}",
        )

    artifacts = contract.get("artifacts")
    if not isinstance(artifacts, dict):
        add_error(errors, "source-manifest.json hash_contract", "artifacts must be an object")
        return
    artifact_paths = set(artifacts)
    if artifact_paths != EXPECTED_HASHED_ARTIFACTS:
        add_error(
            errors,
            "source-manifest.json hash_contract artifacts",
            "paths must equal " + repr(sorted(EXPECTED_HASHED_ARTIFACTS)),
        )
    for relative_value, expected_hash in artifacts.items():
        if not isinstance(relative_value, str):
            add_error(
                errors,
                "source-manifest.json hash_contract artifacts",
                "artifact paths must be strings",
            )
            continue
        path = repository_path(
            relative_value,
            f"source-manifest.json hash_contract artifact {relative_value}",
            errors,
        )
        if path is not None:
            validate_file_hash(
                path,
                expected_hash,
                f"source-manifest.json hash_contract artifact {relative_value}",
                errors,
            )


def validate_privacy(path: Path, text: str, errors: list[str]) -> None:
    relative_path = str(path.relative_to(REPOSITORY_ROOT))
    for label, pattern in PRIVACY_PATTERNS.items():
        match = pattern.search(text)
        if match:
            add_error(errors, relative_path, f"possible {label} detected: {match.group(0)!r}")


def manifest_privacy_view(manifest: dict[str, Any]) -> str:
    sanitized = json.loads(json.dumps(manifest))
    sources = sanitized.get("sources")
    if isinstance(sources, list):
        for source in sources:
            if isinstance(source, dict) and "sha256" in source:
                source["sha256"] = "<validated-sha256>"
    contract = sanitized.get("hash_contract")
    artifacts = contract.get("artifacts", {}) if isinstance(contract, dict) else {}
    if isinstance(artifacts, dict):
        for path in artifacts:
            artifacts[path] = "<validated-sha256>"
    return json.dumps(sanitized, ensure_ascii=False)


def validate_sources(
    manifest: dict[str, Any], errors: list[str]
) -> tuple[dict[str, dict[str, Any]], set[str], Counter[str]]:
    sources = manifest.get("sources")
    if not isinstance(sources, list):
        add_error(errors, "source-manifest.json", "sources must be an array")
        return {}, set(), Counter()

    source_by_id: dict[str, dict[str, Any]] = {}
    all_markers: set[str] = set()
    kind_counts: Counter[str] = Counter()
    attack_patterns: set[str] = set()

    for index, source in enumerate(sources, start=1):
        location = f"source-manifest.json sources[{index}]"
        if not isinstance(source, dict):
            add_error(errors, location, "entry must be an object")
            continue

        source_id = source.get("source_id")
        kind = source.get("kind")
        relative_value = source.get("path")
        target_format = source.get("target_format")
        expected_hash = source.get("sha256")
        if not isinstance(source_id, str) or not SOURCE_ID_PATTERN.fullmatch(source_id):
            add_error(errors, location, "source_id is invalid")
            continue
        if source_id in source_by_id:
            add_error(errors, location, f"duplicate source_id {source_id}")
            continue
        source_by_id[source_id] = source

        if kind not in EXPECTED_SOURCE_COUNTS:
            add_error(errors, location, f"kind must be one of {sorted(EXPECTED_SOURCE_COUNTS)}")
        else:
            kind_counts[kind] += 1
        if kind == "clean" and not source_id.startswith("LG-POL-"):
            add_error(errors, location, "clean source_id must use LG-POL prefix")
        if kind == "attack" and not source_id.startswith("LG-ATK-"):
            add_error(errors, location, "attack source_id must use LG-ATK prefix")

        if target_format not in {"pdf", "docx", "txt"}:
            add_error(errors, location, "target_format must be pdf, docx, or txt")
        if not isinstance(relative_value, str):
            add_error(errors, location, "path must be a string")
            continue

        source_path = repository_path(relative_value, location, errors)
        if source_path is None:
            continue
        validate_file_hash(source_path, expected_hash, location, errors)
        try:
            text = source_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            add_error(errors, location, f"source file is missing: {relative_value}")
            continue
        except UnicodeDecodeError as exc:
            add_error(errors, location, f"source file is not valid UTF-8: {exc}")
            continue
        except OSError as exc:
            add_error(errors, location, f"source file cannot be read: {exc}")
            continue

        validate_privacy(source_path, text, errors)
        if "SYNTHETIC_NOTICE:" not in text:
            add_error(errors, relative_value, "SYNTHETIC_NOTICE is required")

        header_match = SOURCE_HEADER_PATTERN.search(text)
        if not header_match or header_match.group(1) != source_id:
            add_error(errors, relative_value, f"SOURCE_ID header must equal {source_id}")
        format_match = TARGET_FORMAT_PATTERN.search(text)
        if not format_match or format_match.group(1).lower() != target_format:
            add_error(
                errors, relative_value, f"TARGET_FORMAT header must equal {target_format.upper()}"
            )

        source_markers: list[str] = []
        marker_kinds: Counter[str] = Counter()
        for line in text.splitlines():
            marker_match = MARKER_PATTERN.match(line)
            if not marker_match:
                continue
            marker = marker_match.group("marker")
            marker_source = marker_match.group("source")
            marker_kind = marker_match.group("kind")[0]
            source_markers.append(marker)
            marker_kinds[marker_kind] += 1
            if marker_source != source_id:
                add_error(errors, relative_value, f"marker {marker} belongs to the wrong source")
            if marker in all_markers:
                add_error(errors, relative_value, f"duplicate marker {marker}")
            all_markers.add(marker)
        if len(source_markers) != len(set(source_markers)):
            add_error(errors, relative_value, "markers are not unique within the file")
        for required_kind in ("H", "P", "L"):
            if marker_kinds[required_kind] == 0:
                add_error(
                    errors, relative_value, f"at least one {required_kind} marker is required"
                )

        if kind == "attack":
            variant_of = source.get("variant_of")
            attack_pattern = source.get("attack_pattern")
            if not isinstance(variant_of, str) or not variant_of.startswith("LG-POL-"):
                add_error(errors, location, "attack source requires a clean variant_of ID")
            if not isinstance(attack_pattern, str) or not attack_pattern:
                add_error(errors, location, "attack source requires attack_pattern")
            elif attack_pattern in attack_patterns:
                add_error(errors, location, f"duplicate attack_pattern {attack_pattern}")
            else:
                attack_patterns.add(attack_pattern)
            if f"VARIANT_OF: {variant_of}" not in text:
                add_error(errors, relative_value, "VARIANT_OF header does not match the manifest")
            if f"ATTACK_PATTERN: {attack_pattern}" not in text:
                add_error(
                    errors, relative_value, "ATTACK_PATTERN header does not match the manifest"
                )

    for kind, expected_count in EXPECTED_SOURCE_COUNTS.items():
        if kind_counts[kind] != expected_count:
            add_error(
                errors,
                "source-manifest.json",
                f"expected {expected_count} {kind} sources, found {kind_counts[kind]}",
            )

    clean_ids = {
        source_id for source_id, item in source_by_id.items() if item.get("kind") == "clean"
    }
    for source_id, source in source_by_id.items():
        if source.get("kind") == "attack" and source.get("variant_of") not in clean_ids:
            add_error(
                errors,
                f"source-manifest.json {source_id}",
                "variant_of does not resolve to a clean source",
            )

    declared_paths_by_kind = {
        kind: {
            source["path"]
            for source in sources
            if isinstance(source, dict)
            and source.get("kind") == kind
            and isinstance(source.get("path"), str)
        }
        for kind in EXPECTED_SOURCE_COUNTS
    }
    source_directories = {
        "clean": REPOSITORY_ROOT / "fixtures" / "source-documents",
        "attack": REPOSITORY_ROOT / "fixtures" / "attacks",
    }
    for kind, directory in source_directories.items():
        actual_paths = {
            path.relative_to(REPOSITORY_ROOT).as_posix()
            for path in directory.glob("*.md")
            if path.is_file()
        }
        if actual_paths != declared_paths_by_kind[kind]:
            missing_from_manifest = actual_paths - declared_paths_by_kind[kind]
            missing_from_disk = declared_paths_by_kind[kind] - actual_paths
            if missing_from_manifest:
                add_error(
                    errors,
                    str(directory.relative_to(REPOSITORY_ROOT)),
                    f"undeclared files: {sorted(missing_from_manifest)}",
                )
            if missing_from_disk:
                add_error(
                    errors,
                    str(directory.relative_to(REPOSITORY_ROOT)),
                    f"declared files missing from disk: {sorted(missing_from_disk)}",
                )

    return source_by_id, all_markers, kind_counts


def load_cases(errors: list[str]) -> list[dict[str, Any]]:
    try:
        text = CASES_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        add_error(errors, "evals/dataset/cases.jsonl", "file is missing")
        return []

    validate_privacy(CASES_PATH, text, errors)
    cases: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            add_error(errors, f"cases.jsonl:{line_number}", f"invalid JSON: {exc.msg}")
            continue
        if not isinstance(value, dict):
            add_error(errors, f"cases.jsonl:{line_number}", "case must be an object")
            continue
        cases.append(value)
    return cases


def build_schema_validator(
    schema: dict[str, Any], errors: list[str]
) -> Draft202012Validator | None:
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        add_error(
            errors, "evaluation-case.schema.json", f"invalid Draft 2020-12 schema: {exc.message}"
        )
        return None
    return Draft202012Validator(schema, format_checker=FormatChecker())


def json_pointer(path_parts: Any) -> str:
    escaped = [str(part).replace("~", "~0").replace("/", "~1") for part in path_parts]
    return "/" + "/".join(escaped) if escaped else "/"


def validate_case_schemas(
    cases: list[dict[str, Any]],
    validator: Draft202012Validator | None,
    errors: list[str],
) -> set[int]:
    invalid_lines: set[int] = set()
    if validator is None:
        return set(range(1, len(cases) + 1))
    for line_number, case in enumerate(cases, start=1):
        case_id = case.get("case_id", f"line-{line_number}")
        schema_errors = sorted(
            validator.iter_errors(case),
            key=lambda issue: tuple(str(part) for part in issue.absolute_path),
        )
        if schema_errors:
            invalid_lines.add(line_number)
        for issue in schema_errors:
            add_error(
                errors,
                f"cases.jsonl:{line_number} {case_id}",
                f"schema {json_pointer(issue.absolute_path)}: {issue.message}",
            )
    return invalid_lines


def validate_case(
    case: dict[str, Any],
    line_number: int,
    source_by_id: dict[str, dict[str, Any]],
    all_markers: set[str],
    errors: list[str],
) -> None:
    case_id = case.get("case_id", f"line-{line_number}")
    location = f"cases.jsonl:{line_number} {case_id}"
    fields = set(case)
    missing_fields = EXPECTED_CASE_FIELDS - fields
    extra_fields = fields - EXPECTED_CASE_FIELDS
    if missing_fields:
        add_error(errors, location, f"missing fields: {sorted(missing_fields)}")
    if extra_fields:
        add_error(errors, location, f"unexpected fields: {sorted(extra_fields)}")

    if not isinstance(case_id, str) or not CASE_ID_PATTERN.fullmatch(case_id):
        add_error(errors, location, "case_id is invalid")
    category = case.get("category")
    if category not in EXPECTED_CATEGORY_COUNTS:
        add_error(errors, location, "category is invalid")
        return
    if isinstance(case_id, str) and not case_id.startswith(CASE_PREFIXES[category]):
        add_error(errors, location, f"case_id prefix does not match category {category}")
    if case.get("task_type") not in EXPECTED_TASK_TYPES[category]:
        add_error(errors, location, f"task_type does not match category {category}")
    if case.get("expected_status") != EXPECTED_STATUSES[category]:
        add_error(errors, location, f"expected_status must be {EXPECTED_STATUSES[category]}")
    if case.get("user_role") not in ALLOWED_ROLES:
        add_error(errors, location, "user_role is invalid")
    if not isinstance(case.get("request"), str) or not case["request"].strip():
        add_error(errors, location, "request must be a non-empty string")

    corpus_scope = case.get("corpus_scope")
    if not isinstance(corpus_scope, list) or not corpus_scope:
        add_error(errors, location, "corpus_scope must be a non-empty array")
        corpus_scope = []
    elif len(corpus_scope) != len(set(corpus_scope)):
        add_error(errors, location, "corpus_scope must not contain duplicates")
    for source_id in corpus_scope:
        if source_id not in source_by_id:
            add_error(errors, location, f"unknown corpus source {source_id}")

    expected_spans = case.get("expected_spans")
    if not isinstance(expected_spans, list):
        add_error(errors, location, "expected_spans must be an array")
        expected_spans = []
    case_span_ids: set[str] = set()
    for span in expected_spans:
        if not isinstance(span, dict) or set(span) != {"source_id", "marker_id"}:
            add_error(
                errors, location, "each expected span must contain only source_id and marker_id"
            )
            continue
        source_id = span.get("source_id")
        marker_id = span.get("marker_id")
        if source_id not in corpus_scope:
            add_error(errors, location, f"span source {source_id} is outside corpus_scope")
        if marker_id not in all_markers:
            add_error(errors, location, f"unknown marker {marker_id}")
        if isinstance(marker_id, str) and not marker_id.startswith(f"{source_id}:"):
            add_error(errors, location, f"marker {marker_id} does not belong to {source_id}")
        if marker_id in case_span_ids:
            add_error(errors, location, f"duplicate expected marker {marker_id}")
        if isinstance(marker_id, str):
            case_span_ids.add(marker_id)

    for collection_name, id_field in (
        ("expected_claims", "claim_id"),
        ("expected_extractions", "extraction_id"),
    ):
        collection = case.get(collection_name)
        if not isinstance(collection, list):
            add_error(errors, location, f"{collection_name} must be an array")
            continue
        seen_ids: set[str] = set()
        for item in collection:
            if not isinstance(item, dict):
                add_error(errors, location, f"{collection_name} entries must be objects")
                continue
            item_id = item.get(id_field)
            if not isinstance(item_id, str) or not item_id:
                add_error(errors, location, f"{collection_name} entry has invalid {id_field}")
            elif item_id in seen_ids:
                add_error(errors, location, f"duplicate {id_field} {item_id}")
            else:
                seen_ids.add(item_id)
            span_ids = item.get("span_ids")
            if not isinstance(span_ids, list) or not span_ids:
                add_error(errors, location, f"{item_id} must have supporting span_ids")
            elif not set(span_ids).issubset(case_span_ids):
                add_error(errors, location, f"{item_id} references spans outside expected_spans")

    trace = case.get("expected_tool_trace")
    if not isinstance(trace, list):
        add_error(errors, location, "expected_tool_trace must be an array")
        trace = []
    for expected_step, trace_item in enumerate(trace, start=1):
        if not isinstance(trace_item, dict):
            add_error(errors, location, "tool trace entries must be objects")
            continue
        tool_name = trace_item.get("tool_name")
        mode = trace_item.get("mode")
        if trace_item.get("step") != expected_step:
            add_error(errors, location, "tool trace steps must be contiguous and one-based")
        if tool_name not in ALLOWED_TOOLS:
            add_error(errors, location, f"unknown tool {tool_name}")
        if tool_name in READ_ONLY_TOOLS and mode != "read_only":
            add_error(errors, location, f"{tool_name} must be marked read_only")
        if tool_name == "propose_workflow_task" and mode != "proposal_only":
            add_error(errors, location, "propose_workflow_task must be marked proposal_only")

    forbidden_outcomes = case.get("forbidden_outcomes")
    if not isinstance(forbidden_outcomes, list) or not forbidden_outcomes:
        add_error(errors, location, "forbidden_outcomes must be a non-empty array")
        forbidden_outcomes = []
    if len(forbidden_outcomes) != len(set(forbidden_outcomes)):
        add_error(errors, location, "forbidden_outcomes must be unique")
    unknown_outcomes = set(forbidden_outcomes) - ALLOWED_FORBIDDEN_OUTCOMES
    if unknown_outcomes:
        add_error(errors, location, f"unknown forbidden outcomes: {sorted(unknown_outcomes)}")

    missing_facts = case.get("missing_facts")
    if not isinstance(missing_facts, list):
        add_error(errors, location, "missing_facts must be an array")
        missing_facts = []
    proposal = case.get("expected_proposal")
    approval_script = case.get("approval_script")
    if not isinstance(approval_script, list):
        add_error(errors, location, "approval_script must be an array")
        approval_script = []

    if category == "grounded":
        if not case_span_ids:
            add_error(errors, location, "grounded case requires evidence spans")
        if not case.get("expected_claims") and not case.get("expected_extractions"):
            add_error(errors, location, "grounded case requires claims or extractions")
        if proposal is not None or approval_script:
            add_error(
                errors, location, "grounded case cannot contain a proposal or approval script"
            )
    elif category == "insufficient":
        if case_span_ids or case.get("expected_claims") or case.get("expected_extractions"):
            add_error(errors, location, "insufficient case cannot contain supported evidence")
        if not missing_facts:
            add_error(errors, location, "insufficient case requires missing_facts")
        if proposal is not None or approval_script:
            add_error(
                errors, location, "insufficient case cannot contain a proposal or approval script"
            )
    elif category == "injection":
        if not case_span_ids or not case.get("expected_claims"):
            add_error(errors, location, "injection case must retain useful evidence and claims")
        if any(
            source_by_id.get(source_id, {}).get("kind") != "attack" for source_id in corpus_scope
        ):
            add_error(
                errors, location, "injection case corpus_scope must contain only attack sources"
            )
        required_outcomes = {
            "document_instruction_followed",
            "privileged_action_executed_without_approval",
        }
        if not required_outcomes.issubset(set(forbidden_outcomes)):
            add_error(errors, location, f"injection case must forbid {sorted(required_outcomes)}")
        if proposal is not None or approval_script:
            add_error(
                errors, location, "injection case cannot contain a proposal or approval script"
            )
    elif category == "action":
        if case.get("user_role") not in {"reviewer", "admin"}:
            add_error(errors, location, "action case requires reviewer or admin role")
        if not isinstance(proposal, dict):
            add_error(errors, location, "action case requires expected_proposal")
        else:
            proposal_spans = proposal.get("source_span_ids")
            if not isinstance(proposal_spans, list) or not set(proposal_spans).issubset(
                case_span_ids
            ):
                add_error(
                    errors, location, "proposal source_span_ids must be supported expected spans"
                )
            if (
                proposal.get("approval_required") is not True
                or proposal.get("initial_status") != "pending"
            ):
                add_error(errors, location, "proposal must begin pending and require approval")
        if not approval_script:
            add_error(errors, location, "action case requires approval_script")
        if not trace or trace[-1].get("tool_name") != "propose_workflow_task":
            add_error(errors, location, "action tool trace must end with propose_workflow_task")
        if "workflow_task_created_before_approval" not in forbidden_outcomes:
            add_error(errors, location, "action case must forbid pre-approval task creation")
        for expected_step, decision in enumerate(approval_script, start=1):
            if not isinstance(decision, dict):
                add_error(errors, location, "approval script entries must be objects")
                continue
            if decision.get("step") != expected_step:
                add_error(errors, location, "approval steps must be contiguous and one-based")
            if decision.get("decision") not in {"approve", "edit", "reject", "expire", "replay"}:
                add_error(errors, location, "approval decision is invalid")
            if decision.get("expected_task_count") not in {0, 1}:
                add_error(errors, location, "expected_task_count must be zero or one")
        if isinstance(proposal, dict) and approval_script:
            final_count = approval_script[-1].get("expected_task_count")
            if proposal.get("expected_final_task_count") != final_count:
                add_error(
                    errors,
                    location,
                    "proposal expected_final_task_count must match the final approval step",
                )

    if category != "action" and any(
        item.get("tool_name") == "propose_workflow_task" for item in trace if isinstance(item, dict)
    ):
        add_error(errors, location, "non-action case cannot call propose_workflow_task")


def validate_cases(
    cases: list[dict[str, Any]],
    source_by_id: dict[str, dict[str, Any]],
    all_markers: set[str],
    schema_invalid_lines: set[int],
    errors: list[str],
) -> Counter[str]:
    case_ids: set[str] = set()
    category_counts: Counter[str] = Counter()
    referenced_sources: set[str] = set()

    for line_number, case in enumerate(cases, start=1):
        case_id = case.get("case_id")
        if isinstance(case_id, str):
            if case_id in case_ids:
                add_error(errors, f"cases.jsonl:{line_number}", f"duplicate case_id {case_id}")
            case_ids.add(case_id)
        category = case.get("category")
        if isinstance(category, str):
            category_counts[category] += 1
        corpus_scope = case.get("corpus_scope")
        if isinstance(corpus_scope, list):
            referenced_sources.update(item for item in corpus_scope if isinstance(item, str))
        if line_number not in schema_invalid_lines:
            validate_case(case, line_number, source_by_id, all_markers, errors)

    if len(cases) != sum(EXPECTED_CATEGORY_COUNTS.values()):
        add_error(errors, "cases.jsonl", f"expected 25 cases, found {len(cases)}")
    for category, expected_count in EXPECTED_CATEGORY_COUNTS.items():
        if category_counts[category] != expected_count:
            add_error(
                errors,
                "cases.jsonl",
                f"expected {expected_count} {category} cases, found {category_counts[category]}",
            )

    grounded_task_types = {
        case.get("task_type") for case in cases if case.get("category") == "grounded"
    }
    if grounded_task_types != {"question_answering", "structured_extraction"}:
        add_error(
            errors,
            "cases.jsonl",
            "grounded cases must include both question_answering and structured_extraction",
        )

    unreferenced_sources = set(source_by_id) - referenced_sources
    if unreferenced_sources:
        add_error(
            errors,
            "cases.jsonl",
            f"sources are not referenced by any case: {sorted(unreferenced_sources)}",
        )
    return category_counts


def run_negative_self_tests(
    cases: list[dict[str, Any]],
    schema_validator: Draft202012Validator,
    manifest: dict[str, Any],
) -> list[str]:
    failures: list[str] = []

    schema_probe = next((case for case in cases if case.get("expected_claims")), None)
    if schema_probe is None:
        failures.append("schema mutation probe requires a case with expected_claims")
    else:
        mutated_case = json.loads(json.dumps(schema_probe))
        mutated_case["expected_claims"][0]["predicate"] = 7
        schema_errors: list[str] = []
        invalid_lines = validate_case_schemas([mutated_case], schema_validator, schema_errors)
        if invalid_lines != {1} or not schema_errors:
            failures.append("Draft 2020-12 validator accepted an integer claim predicate")

    mutated_source_manifest = json.loads(json.dumps(manifest))
    mutated_sources = mutated_source_manifest.get("sources", [])
    if not mutated_sources:
        failures.append("source hash mutation probe requires at least one source")
    else:
        mutated_sources[0]["sha256"] = "0" * 64
        source_errors: list[str] = []
        validate_sources(mutated_source_manifest, source_errors)
        if not any("SHA-256 mismatch" in error for error in source_errors):
            failures.append("source hash mutation was not rejected")

    mutated_artifact_manifest = json.loads(json.dumps(manifest))
    artifacts = mutated_artifact_manifest.get("hash_contract", {}).get("artifacts", {})
    if not artifacts:
        failures.append("artifact hash mutation probe requires tracked artifacts")
    else:
        first_artifact = sorted(artifacts)[0]
        artifacts[first_artifact] = "0" * 64
        artifact_errors: list[str] = []
        validate_hash_contract(mutated_artifact_manifest, artifact_errors)
        if not any("SHA-256 mismatch" in error for error in artifact_errors):
            failures.append("artifact hash mutation was not rejected")

    return failures


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the LocalGuard synthetic corpus and deterministic gold dataset."
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="also prove that schema and hash mutations fail closed without changing files",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    errors: list[str] = []
    schema = read_json(SCHEMA_PATH, errors)
    schema_validator: Draft202012Validator | None = None
    if isinstance(schema, dict):
        schema_validator = build_schema_validator(schema, errors)
        schema_required = set(schema.get("required", []))
        if schema_required != EXPECTED_CASE_FIELDS:
            add_error(
                errors,
                "evaluation-case.schema.json",
                "required fields do not match validator contract",
            )

    manifest = read_json(MANIFEST_PATH, errors)
    if not isinstance(manifest, dict):
        manifest = {}
    else:
        validate_privacy(MANIFEST_PATH, manifest_privacy_view(manifest), errors)
        if manifest.get("synthetic_only") is not True:
            add_error(errors, "source-manifest.json", "synthetic_only must be true")
        validate_hash_contract(manifest, errors)

    source_by_id, all_markers, source_counts = validate_sources(manifest, errors)
    cases = load_cases(errors)
    schema_invalid_lines = validate_case_schemas(cases, schema_validator, errors)
    category_counts = validate_cases(
        cases,
        source_by_id,
        all_markers,
        schema_invalid_lines,
        errors,
    )

    if errors:
        print(f"VALIDATION FAILED ({len(errors)} errors)")
        for error in errors:
            print(f"- {error}")
        return 1

    if args.self_test:
        if schema_validator is None:
            print("SELF-TEST FAILED")
            print("- schema validator is unavailable")
            return 1
        self_test_failures = run_negative_self_tests(cases, schema_validator, manifest)
        if self_test_failures:
            print(f"SELF-TEST FAILED ({len(self_test_failures)} errors)")
            for failure in self_test_failures:
                print(f"- {failure}")
            return 1

    print("VALIDATION PASSED")
    print(f"clean_sources={source_counts['clean']}")
    print(f"attack_sources={source_counts['attack']}")
    print(f"stable_markers={len(all_markers)}")
    print(f"cases={len(cases)}")
    print(
        "categories="
        + ",".join(f"{name}:{category_counts[name]}" for name in EXPECTED_CATEGORY_COUNTS)
    )
    print("privacy_findings=0")
    print(f"source_hashes_verified={len(source_by_id)}")
    print(f"artifact_hashes_verified={len(EXPECTED_HASHED_ARTIFACTS)}")
    if args.self_test:
        print("negative_schema_mutation=rejected")
        print("negative_source_hash_mutation=rejected")
        print("negative_artifact_hash_mutation=rejected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
