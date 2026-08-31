"""Bounded document validation, extraction, stable anchoring, and chunking."""

from __future__ import annotations

import hashlib
import io
import os
import re
import unicodedata
import uuid
import zipfile
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from docx import Document as DocxDocument
from fastapi import UploadFile
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from .config import Settings
from .errors import UnsafeUploadError

PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TXT_MIME = "text/plain"
_ALLOWED_MEDIA = {".pdf": PDF_MIME, ".docx": DOCX_MIME, ".txt": TXT_MIME}
_SAFE_STORAGE_KEY = re.compile(r"^[0-9a-f]{32}\.(pdf|docx|txt)$")


@dataclass(frozen=True, slots=True)
class ValidatedUpload:
    original_filename: str
    title: str
    extension: str
    media_type: str
    content: bytes
    sha256: str


@dataclass(frozen=True, slots=True)
class ParsedAnchor:
    stable_key: str
    kind: str
    label: str
    ordinal: int
    text: str
    start_offset: int = 0

    @property
    def end_offset(self) -> int:
        return self.start_offset + len(self.text)


@dataclass(frozen=True, slots=True)
class ChunkDraft:
    stable_id: str
    anchor_key: str
    ordinal: int
    start_offset: int
    end_offset: int
    content: str
    content_sha256: str


async def validate_upload(upload: UploadFile, settings: Settings) -> ValidatedUpload:
    filename = _safe_display_filename(upload.filename or "")
    extension = Path(filename).suffix.lower()
    expected_media = _ALLOWED_MEDIA.get(extension)
    if expected_media is None:
        raise UnsafeUploadError(
            "unsupported_file_type", "Only PDF, DOCX, and TXT files are allowed"
        )
    supplied_media = (upload.content_type or "").split(";", maxsplit=1)[0].strip().lower()
    if supplied_media != expected_media:
        raise UnsafeUploadError(
            "media_type_mismatch", "The filename and declared media type do not agree"
        )

    content = await _read_bounded(upload, settings.max_upload_bytes)
    _validate_magic(extension, content)
    if extension == ".docx":
        _validate_docx_archive(content, settings)
    elif extension == ".txt":
        _decode_text(content)
    return ValidatedUpload(
        original_filename=filename,
        title=Path(filename).stem[:300],
        extension=extension,
        media_type=expected_media,
        content=content,
        sha256=hashlib.sha256(content).hexdigest(),
    )


async def _read_bounded(upload: UploadFile, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(min(64 * 1024, max_bytes + 1 - total))
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise UnsafeUploadError("file_too_large", "File exceeds the 10 MB upload limit")
        chunks.append(chunk)
    if total == 0:
        raise UnsafeUploadError("empty_file", "The uploaded file is empty")
    return b"".join(chunks)


def _safe_display_filename(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).replace("\\", "/")
    filename = PurePosixPath(normalized).name.strip()
    if not filename or filename in {".", ".."} or len(filename) > 300:
        raise UnsafeUploadError("invalid_filename", "The filename is invalid")
    if any(ord(character) < 32 for character in filename):
        raise UnsafeUploadError("invalid_filename", "The filename contains control characters")
    return filename


def _validate_magic(extension: str, content: bytes) -> None:
    if extension == ".pdf" and not content.startswith(b"%PDF-"):
        raise UnsafeUploadError("content_type_mismatch", "The file is not a valid PDF")
    if extension == ".docx" and not content.startswith(b"PK"):
        raise UnsafeUploadError("content_type_mismatch", "The file is not a valid DOCX archive")
    if extension == ".txt" and (content.startswith(b"%PDF-") or content.startswith(b"PK")):
        raise UnsafeUploadError("content_type_mismatch", "The file is not plain text")


def _validate_docx_archive(content: bytes, settings: Settings) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entries = archive.infolist()
            names = {entry.filename for entry in entries}
            if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                raise UnsafeUploadError("invalid_docx", "Required DOCX parts are missing")
            if len(entries) > settings.max_docx_entries:
                raise UnsafeUploadError(
                    "docx_too_complex", "DOCX contains too many archive entries"
                )
            expanded = 0
            for entry in entries:
                path = PurePosixPath(entry.filename)
                if path.is_absolute() or ".." in path.parts or "\\" in entry.filename:
                    raise UnsafeUploadError(
                        "unsafe_docx_path", "DOCX contains an unsafe archive path"
                    )
                if entry.flag_bits & 0x1:
                    raise UnsafeUploadError(
                        "encrypted_docx", "Encrypted DOCX files are not supported"
                    )
                expanded += entry.file_size
                if expanded > settings.max_docx_expanded_bytes:
                    raise UnsafeUploadError(
                        "docx_expansion_limit", "DOCX expands beyond the safe limit"
                    )
                if entry.file_size and entry.compress_size == 0:
                    raise UnsafeUploadError("docx_compression_limit", "DOCX has an unsafe entry")
                if (
                    entry.compress_size
                    and entry.file_size / entry.compress_size > settings.max_docx_compression_ratio
                ):
                    raise UnsafeUploadError(
                        "docx_compression_limit", "DOCX compression ratio is unsafe"
                    )
            bad_entry = archive.testzip()
            if bad_entry is not None:
                raise UnsafeUploadError("corrupt_docx", "DOCX archive integrity check failed")
    except UnsafeUploadError:
        raise
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        raise UnsafeUploadError("corrupt_docx", "The DOCX archive is corrupt") from exc


def parse_document(upload: ValidatedUpload, settings: Settings) -> list[ParsedAnchor]:
    if upload.extension == ".pdf":
        anchors = _parse_pdf(upload.content, settings)
    elif upload.extension == ".docx":
        anchors = _parse_docx(upload.content, settings)
    else:
        anchors = _parse_txt(upload.content, settings)
    if not anchors or not any(anchor.text.strip() for anchor in anchors):
        raise UnsafeUploadError("no_extractable_text", "No extractable text was found")
    extracted = sum(len(anchor.text) for anchor in anchors)
    if extracted > settings.max_extracted_characters:
        raise UnsafeUploadError("extracted_text_limit", "Extracted text exceeds the safe limit")
    return anchors


def _parse_pdf(content: bytes, settings: Settings) -> list[ParsedAnchor]:
    try:
        reader = PdfReader(io.BytesIO(content), strict=True)
        if reader.is_encrypted:
            raise UnsafeUploadError("encrypted_pdf", "Encrypted PDF files are not supported")
        if len(reader.pages) > settings.max_pdf_pages:
            raise UnsafeUploadError("pdf_page_limit", "PDF exceeds the 100-page limit")
        anchors = []
        for page_number, page in enumerate(reader.pages, start=1):
            text = _normalize_extracted_text(page.extract_text() or "")
            anchors.append(
                ParsedAnchor(
                    stable_key=f"page:{page_number}",
                    kind="pdf_page",
                    label=f"Page {page_number}",
                    ordinal=page_number,
                    text=text,
                )
            )
        return anchors
    except UnsafeUploadError:
        raise
    except (PdfReadError, OSError, ValueError, TypeError) as exc:
        raise UnsafeUploadError("corrupt_pdf", "The PDF could not be parsed safely") from exc


def _parse_docx(content: bytes, settings: Settings) -> list[ParsedAnchor]:
    try:
        document = DocxDocument(io.BytesIO(content))
    except (ValueError, KeyError, OSError, zipfile.BadZipFile) as exc:
        raise UnsafeUploadError("corrupt_docx", "The DOCX could not be parsed safely") from exc
    paragraphs = document.paragraphs
    if len(paragraphs) > settings.max_docx_paragraphs:
        raise UnsafeUploadError("docx_paragraph_limit", "DOCX contains too many paragraphs")
    anchors: list[ParsedAnchor] = []
    section_number = 1
    section_label = "Document"
    paragraph_in_section = 0
    for paragraph in paragraphs:
        text = _normalize_extracted_text(paragraph.text)
        if not text:
            continue
        style_name = (paragraph.style.name if paragraph.style else "").casefold()
        if style_name.startswith("heading"):
            if anchors:
                section_number += 1
            section_label = text[:300]
            paragraph_in_section = 0
        paragraph_in_section += 1
        ordinal = len(anchors) + 1
        anchors.append(
            ParsedAnchor(
                stable_key=f"section:{section_number}:paragraph:{paragraph_in_section}",
                kind="docx_paragraph",
                label=f"{section_label}: paragraph {paragraph_in_section}",
                ordinal=ordinal,
                text=text,
            )
        )
    return anchors


def _parse_txt(content: bytes, settings: Settings) -> list[ParsedAnchor]:
    decoded = (
        unicodedata.normalize("NFC", _decode_text(content))
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )
    lines = decoded.split("\n")
    if len(lines) > settings.max_text_lines:
        raise UnsafeUploadError("text_line_limit", "Text file contains too many lines")
    anchors: list[ParsedAnchor] = []
    for start in range(0, len(lines), 50):
        normalized_lines = [_normalize_line(line) for line in lines[start : start + 50]]
        retained = [index for index, line in enumerate(normalized_lines) if line]
        if not retained:
            continue
        first_retained = retained[0]
        last_retained = retained[-1]
        block = "\n".join(normalized_lines[first_retained : last_retained + 1])
        first_line = start + first_retained + 1
        last_line = start + last_retained + 1
        anchors.append(
            ParsedAnchor(
                stable_key=f"lines:{first_line}-{last_line}",
                kind="text_lines",
                label=f"Lines {first_line}-{last_line}",
                ordinal=len(anchors) + 1,
                text=block,
            )
        )
    return anchors


def _normalize_line(value: str) -> str:
    safe = "".join(character for character in value if ord(character) >= 32 or character == "\t")
    return " ".join(safe.split())


def _decode_text(content: bytes) -> str:
    if b"\x00" in content:
        raise UnsafeUploadError("binary_text", "TXT file contains binary data")
    try:
        decoded = content.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as exc:
        raise UnsafeUploadError(
            "invalid_text_encoding", "TXT files must use UTF-8 encoding"
        ) from exc
    controls = sum(1 for char in decoded if ord(char) < 32 and char not in {"\n", "\r", "\t", "\f"})
    if controls > max(2, len(decoded) // 100):
        raise UnsafeUploadError("binary_text", "TXT file contains excessive control data")
    return decoded


def _normalize_extracted_text(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value).replace("\r\n", "\n").replace("\r", "\n")
    normalized = "".join(char for char in normalized if ord(char) >= 32 or char in {"\n", "\t"})
    lines = [" ".join(line.split()) for line in normalized.split("\n")]
    return "\n".join(lines).strip()


def build_chunks(
    revision_id: uuid.UUID,
    anchors: list[ParsedAnchor],
    *,
    max_characters: int = 1200,
    overlap: int = 160,
) -> list[ChunkDraft]:
    if max_characters < 200 or not 0 <= overlap < max_characters:
        raise ValueError("invalid chunking limits")
    chunks: list[ChunkDraft] = []
    ordinal = 0
    for anchor in anchors:
        cursor = 0
        while cursor < len(anchor.text):
            tentative_end = min(cursor + max_characters, len(anchor.text))
            end = _prefer_boundary(anchor.text, cursor, tentative_end)
            if end <= cursor:
                end = tentative_end
            raw_content = anchor.text[cursor:end]
            leading = len(raw_content) - len(raw_content.lstrip())
            trailing = len(raw_content) - len(raw_content.rstrip())
            content = raw_content.strip()
            if content:
                ordinal += 1
                content_start = cursor + leading
                content_end = end - trailing
                content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
                stable_material = (
                    f"{revision_id}:{anchor.stable_key}:{content_start}:{content_end}:{content_hash}"
                ).encode()
                chunks.append(
                    ChunkDraft(
                        stable_id=hashlib.sha256(stable_material).hexdigest(),
                        anchor_key=anchor.stable_key,
                        ordinal=ordinal,
                        start_offset=content_start,
                        end_offset=content_end,
                        content=content,
                        content_sha256=content_hash,
                    )
                )
            if end >= len(anchor.text):
                break
            cursor = max(cursor + 1, end - overlap)
    return chunks


def _prefer_boundary(text: str, start: int, tentative_end: int) -> int:
    if tentative_end == len(text):
        return tentative_end
    floor = start + (tentative_end - start) // 2
    for delimiter in ("\n", ". ", "; ", " "):
        position = text.rfind(delimiter, floor, tentative_end)
        if position >= floor:
            return position + len(delimiter)
    return tentative_end


class PrivateUploadStore:
    """Opaque, non-web-served upload storage with atomic publication."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.files = self.root / "files"
        self.quarantine = self.root / "quarantine"

    def prepare(self) -> None:
        for directory in (self.root, self.files, self.quarantine):
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            with suppress(OSError):
                directory.chmod(0o700)

    def store(self, upload: ValidatedUpload) -> str:
        self.prepare()
        storage_key = f"{uuid.uuid4().hex}{upload.extension}"
        temporary = self.quarantine / f"{uuid.uuid4().hex}.part"
        destination = self.files / storage_key
        try:
            with temporary.open("xb") as handle:
                handle.write(upload.content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, destination)
            with suppress(OSError):
                destination.chmod(0o600)
        finally:
            temporary.unlink(missing_ok=True)
        return storage_key

    def read(self, storage_key: str, max_bytes: int) -> bytes:
        path = self._safe_path(storage_key)
        size = path.stat().st_size
        if size > max_bytes:
            raise UnsafeUploadError(
                "stored_file_too_large", "Stored file exceeds its configured limit"
            )
        return path.read_bytes()

    def delete(self, storage_key: str) -> None:
        self._safe_path(storage_key).unlink(missing_ok=True)

    def _safe_path(self, storage_key: str) -> Path:
        if not _SAFE_STORAGE_KEY.fullmatch(storage_key):
            raise UnsafeUploadError("invalid_storage_key", "Stored file identifier is invalid")
        path = (self.files / storage_key).resolve()
        if path.parent != self.files.resolve():
            raise UnsafeUploadError("invalid_storage_key", "Stored file identifier is invalid")
        return path
