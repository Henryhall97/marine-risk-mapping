"""Security helpers shared across the API.

Three concerns live here:

1. **UUID validation** — every path parameter that names an on-disk
   directory (submission_id, event_id) must be checked against the
   UUID regex *before* it is joined to a filesystem root. Without
   this, a request like
   ``GET /api/v1/media/..%2F..%2Fetc%2Fpasswd/photo`` could escape
   the upload root if any proxy decoded the path before FastAPI did.
2. **Containment check** — ``safe_subpath`` resolves the candidate
   path and confirms it remains inside the configured root, as a
   second line of defence.
3. **Magic-byte sniffing** — every upload endpoint trusts the
   client-supplied ``Content-Type`` header and filename extension.
   A ``.jpg``-named file containing arbitrary bytes is accepted and
   stored. ``sniff_mime`` inspects the first 16 bytes against a
   compact table of header signatures and ``validate_upload_bytes``
   raises a 415 if the declared kind doesn't match what's on disk.

The helpers are deliberately dependency-free (no libmagic, no
filetype/python-magic) so they work in the slim runtime container
without an extra apt package.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from fastapi import HTTPException

# ── UUID validation ─────────────────────────────────────────

# RFC 4122 — accepts any version (1–5) and any variant. Lower-case
# only; database UUIDs are returned in lower-case form by Postgres
# ``::text`` casts.
_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def validate_uuid_or_404(value: str, *, name: str = "id") -> str:
    """Return ``value`` if it is a valid UUID, else raise 404.

    Returning 404 (not 400) keeps probe-based reconnaissance
    indistinguishable from a real miss.
    """
    if not isinstance(value, str) or not _UUID_RE.match(value.lower()):
        raise HTTPException(status_code=404, detail=f"{name} not found")
    return value.lower()


# ── Path containment ────────────────────────────────────────


def safe_subpath(root: Path, *parts: str) -> Path:
    """Join ``parts`` under ``root`` and verify the result stays inside.

    Defence-in-depth on top of ``validate_uuid_or_404``. Any attempt
    to escape via ``..`` segments or absolute-path components raises
    a 404 (treated as a missing file, not a security event leaked to
    the caller).
    """
    candidate = root.joinpath(*parts).resolve()
    root_resolved = root.resolve()
    if not candidate.is_relative_to(root_resolved):
        raise HTTPException(status_code=404, detail="Not found")
    return candidate


# ── Magic-byte sniffing ─────────────────────────────────────

# Map of recognised file kinds to canonical MIME type. The first
# entry whose ``matches`` predicate returns True wins.
#
# Predicates inspect ``head`` (at least 16 bytes). We deliberately
# accept only formats the application already advertises, so the
# table is short.

_Kind = Literal["image", "audio", "document"]


def _is_jpeg(h: bytes) -> bool:
    return h[:3] == b"\xff\xd8\xff"


def _is_png(h: bytes) -> bool:
    return h[:8] == b"\x89PNG\r\n\x1a\n"


def _is_webp(h: bytes) -> bool:
    return h[:4] == b"RIFF" and h[8:12] == b"WEBP"


def _is_tiff(h: bytes) -> bool:
    return h[:4] in (b"II*\x00", b"MM\x00*")


def _is_wav(h: bytes) -> bool:
    return h[:4] == b"RIFF" and h[8:12] == b"WAVE"


def _is_flac(h: bytes) -> bool:
    return h[:4] == b"fLaC"


def _is_aiff(h: bytes) -> bool:
    return h[:4] == b"FORM" and h[8:12] in (b"AIFF", b"AIFC")


def _is_mp3(h: bytes) -> bool:
    # ID3v2 tag or a raw MPEG audio frame sync. The frame sync byte
    # pattern is 11 bits of 1s; checking the second byte's high
    # nibble against the documented values is enough to discriminate
    # MP3 from random binary noise.
    if h[:3] == b"ID3":
        return True
    return len(h) >= 2 and h[0] == 0xFF and (h[1] & 0xE0) == 0xE0


def _is_pdf(h: bytes) -> bool:
    return h[:5] == b"%PDF-"


def _is_doc(h: bytes) -> bool:
    # Legacy compound file binary (Word 97–2003 .doc).
    return h[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def _is_zip(h: bytes) -> bool:
    # .docx is a ZIP container. We can't cheaply confirm it really
    # contains a Word document without opening the archive, so we
    # accept the ZIP signature for .docx uploads.
    return h[:4] in (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")


_IMAGE_SNIFFERS: tuple[tuple[str, Callable[[bytes], bool]], ...] = (
    ("image/jpeg", _is_jpeg),
    ("image/png", _is_png),
    ("image/webp", _is_webp),
    ("image/tiff", _is_tiff),
)

_AUDIO_SNIFFERS: tuple[tuple[str, Callable[[bytes], bool]], ...] = (
    ("audio/wav", _is_wav),
    ("audio/flac", _is_flac),
    ("audio/aiff", _is_aiff),
    ("audio/mpeg", _is_mp3),
)

_DOCUMENT_SNIFFERS: tuple[tuple[str, Callable[[bytes], bool]], ...] = (
    # Documents allow image extensions too — credential evidence can
    # be a photograph of a permit.
    ("image/jpeg", _is_jpeg),
    ("image/png", _is_png),
    ("image/webp", _is_webp),
    ("application/pdf", _is_pdf),
    ("application/msword", _is_doc),
    (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        _is_zip,
    ),
)


def sniff_mime(data: bytes, kind: _Kind) -> str | None:
    """Return the detected MIME for ``data`` or ``None`` if unknown.

    Only signatures for the application's accepted formats are
    consulted; anything else returns ``None``.
    """
    if len(data) < 12:
        return None
    table = {
        "image": _IMAGE_SNIFFERS,
        "audio": _AUDIO_SNIFFERS,
        "document": _DOCUMENT_SNIFFERS,
    }[kind]
    for mime, predicate in table:
        if predicate(data):
            return mime
    return None


def validate_upload_bytes(
    data: bytes,
    *,
    kind: _Kind,
    declared_content_type: str | None = None,
) -> str:
    """Validate ``data`` matches one of the accepted ``kind`` signatures.

    Returns the sniffed MIME on success. Raises 415 on mismatch.

    If ``declared_content_type`` is provided we additionally verify
    it agrees with what we sniffed (loose match — ``image/jpg`` vs
    ``image/jpeg`` is tolerated).
    """
    mime = sniff_mime(data, kind)
    if mime is None:
        raise HTTPException(
            status_code=415,
            detail=(
                f"File content does not match an accepted {kind} format. "
                "The file extension or Content-Type header may be "
                "misleading."
            ),
        )
    if declared_content_type:
        declared = declared_content_type.lower().split(";", 1)[0].strip()
        # Normalise a couple of common aliases before comparing.
        declared = {
            "image/jpg": "image/jpeg",
            "audio/x-wav": "audio/wav",
            "audio/wave": "audio/wav",
            "audio/x-flac": "audio/flac",
            "audio/mp3": "audio/mpeg",
            "audio/x-aiff": "audio/aiff",
        }.get(declared, declared)
        # Allow document endpoints to accept image MIME types too.
        accepted = {mime}
        if kind == "document" and mime.startswith("image/"):
            accepted.add(mime)
        if declared and declared != mime and declared not in accepted:
            raise HTTPException(
                status_code=415,
                detail=(
                    f"Declared Content-Type {declared!r} does not match "
                    f"actual file contents ({mime})."
                ),
            )
    return mime
