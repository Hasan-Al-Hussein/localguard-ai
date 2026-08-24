#!/usr/bin/env python3
"""Validate upload-ready fixtures against their generated manifest."""

from __future__ import annotations

import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any

from docx import Document
from pypdf import PdfReader

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPOSITORY_ROOT / "fixtures" / "documents"
MANIFEST_PATH = FIXTURE_ROOT / "manifest.json"
MARKER_PATTERN = re.compile(r"\[(LG-(?:POL|ATK)-\d{3}:(?:H\d{2}|P\d{3}|L\d{3}))\]")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def check(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def validate_pdf(path: Path, document: dict[str, Any], errors: list[str]) -> int:
    check(path.read_bytes().startswith(b"%PDF-"), f"{path}: invalid PDF magic", errors)
    try:
        reader = PdfReader(str(path))
    except Exception as exc:  # pragma: no cover - exercised on corrupt fixtures
        errors.append(f"{path}: PDF could not be opened: {exc}")
        return 0
    check(not reader.is_encrypted, f"{path}: fixture PDF must not be encrypted", errors)
    page_text = [(page.extract_text() or "") for page in reader.pages]
    expected_pages = document["locations"]["_document"]["page_count"]
    check(len(page_text) == expected_pages, f"{path}: page count drift", errors)
    for marker, location in document["locations"].items():
        if marker == "_document":
            continue
        actual_pages = [index for index, text in enumerate(page_text, start=1) if marker in text]
        check(
            actual_pages == [location["page"]],
            f"{path}: marker {marker} pages {actual_pages}",
            errors,
        )
    combined = "\n".join(page_text)
    check("synthetic" in combined.casefold(), f"{path}: synthetic notice not extractable", errors)
    return len(reader.pages)


def validate_docx(path: Path, document: dict[str, Any], errors: list[str]) -> int:
    check(zipfile.is_zipfile(path), f"{path}: invalid DOCX ZIP container", errors)
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            check("[Content_Types].xml" in names, f"{path}: missing content types", errors)
            check("word/document.xml" in names, f"{path}: missing document.xml", errors)
            check(
                all(not name.startswith(("../", "/")) for name in names),
                f"{path}: unsafe ZIP entry",
                errors,
            )
    try:
        docx = Document(path)
    except Exception as exc:  # pragma: no cover - exercised on corrupt fixtures
        errors.append(f"{path}: DOCX could not be opened: {exc}")
        return 0
    paragraphs = [paragraph.text for paragraph in docx.paragraphs]
    expected_count = document["locations"]["_document"]["paragraph_count"]
    check(len(paragraphs) == expected_count, f"{path}: paragraph count drift", errors)
    for marker, location in document["locations"].items():
        if marker == "_document":
            continue
        actual = [index for index, text in enumerate(paragraphs, start=1) if marker in text]
        check(
            actual == [location["paragraph"]],
            f"{path}: marker {marker} paragraphs {actual}",
            errors,
        )
    check(
        "synthetic" in "\n".join(paragraphs).casefold(), f"{path}: synthetic notice missing", errors
    )
    return len(paragraphs)


def validate_txt(path: Path, document: dict[str, Any], errors: list[str]) -> int:
    raw = path.read_bytes()
    check(b"\x00" not in raw, f"{path}: TXT fixture contains a NUL byte", errors)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        errors.append(f"{path}: TXT fixture is not UTF-8: {exc}")
        return 0
    lines = text.splitlines()
    expected_count = document["locations"]["_document"]["line_count"]
    check(len(lines) == expected_count, f"{path}: line count drift", errors)
    for marker, location in document["locations"].items():
        if marker == "_document":
            continue
        actual = [index for index, line in enumerate(lines, start=1) if marker in line]
        expected = list(range(location["line_start"], location["line_end"] + 1))
        check(actual == expected, f"{path}: marker {marker} lines {actual}", errors)
    check("synthetic_notice:" in text.casefold(), f"{path}: synthetic notice missing", errors)
    return len(lines)


def main() -> int:
    errors: list[str] = []
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"FIXTURE VALIDATION FAILED\n{exc}", file=sys.stderr)
        return 1
    check(
        manifest.get("synthetic_only") is True, "manifest must declare synthetic_only=true", errors
    )
    documents = manifest.get("documents")
    check(isinstance(documents, list), "manifest documents must be an array", errors)
    if not isinstance(documents, list):
        documents = []
    check(len(documents) == 13, f"expected 13 generated documents, found {len(documents)}", errors)

    seen_ids: set[str] = set()
    declared_paths: set[Path] = set()
    format_counts: dict[str, int] = {"pdf": 0, "docx": 0, "txt": 0}
    location_count = 0
    for document in documents:
        source_id = document.get("source_id")
        check(
            isinstance(source_id, str) and source_id not in seen_ids,
            f"duplicate/invalid source ID {source_id}",
            errors,
        )
        if isinstance(source_id, str):
            seen_ids.add(source_id)
        relative_path = Path(document.get("path", ""))
        path = (REPOSITORY_ROOT / relative_path).resolve()
        check(
            path.is_relative_to(FIXTURE_ROOT),
            f"{relative_path}: generated path escapes fixture root",
            errors,
        )
        declared_paths.add(path)
        if not path.is_file():
            errors.append(f"{relative_path}: generated fixture is missing")
            continue
        check(path.stat().st_size == document.get("bytes"), f"{relative_path}: size drift", errors)
        check(
            sha256(path) == document.get("sha256"), f"{relative_path}: generated hash drift", errors
        )
        source_path = (REPOSITORY_ROOT / document.get("source_path", "")).resolve()
        check(source_path.is_file(), f"{relative_path}: canonical source is missing", errors)
        if source_path.is_file():
            check(
                sha256(source_path) == document.get("source_sha256"),
                f"{relative_path}: source hash drift",
                errors,
            )
        file_format = document.get("format")
        check(
            path.suffix.casefold() == f".{file_format}",
            f"{relative_path}: extension/format mismatch",
            errors,
        )
        if file_format in format_counts:
            format_counts[file_format] += 1
        locations = document.get("locations")
        check(
            isinstance(locations, dict) and "_document" in locations,
            f"{relative_path}: locations missing",
            errors,
        )
        if not isinstance(locations, dict):
            continue
        location_count += len(locations) - 1
        if file_format == "pdf":
            validate_pdf(path, document, errors)
        elif file_format == "docx":
            validate_docx(path, document, errors)
        elif file_format == "txt":
            validate_txt(path, document, errors)
        else:
            errors.append(f"{relative_path}: unsupported format {file_format}")

    actual_paths = {
        path.resolve()
        for path in FIXTURE_ROOT.rglob("*")
        if path.is_file() and path.suffix.casefold() in {".pdf", ".docx", ".txt"}
    }
    check(actual_paths == declared_paths, "generated binary/text set differs from manifest", errors)
    check(
        format_counts == {"pdf": 6, "docx": 4, "txt": 3},
        f"format counts are {format_counts}",
        errors,
    )

    if errors:
        print("FIXTURE VALIDATION FAILED", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("FIXTURE VALIDATION PASSED")
    print(f"documents={len(documents)}")
    print(
        f"formats=pdf:{format_counts['pdf']},docx:{format_counts['docx']},txt:{format_counts['txt']}"
    )
    print(f"stable_markers={location_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
