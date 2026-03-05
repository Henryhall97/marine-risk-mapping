"""Media file serving endpoints.

GET /api/v1/media/{submission_id}/photo  — Serve the stored photo
GET /api/v1/media/{submission_id}/audio  — Serve the stored audio
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/media", tags=["media"])

_UPLOAD_ROOT = Path("data/uploads/submissions")
_AVATAR_ROOT = Path("data/uploads/avatars")

_PHOTO_MEDIA_TYPES: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
}

_AUDIO_MEDIA_TYPES: dict[str, str] = {
    ".wav": "audio/wav",
    ".flac": "audio/flac",
    ".mp3": "audio/mpeg",
    ".aif": "audio/aiff",
    ".aiff": "audio/aiff",
}


def _find_media(
    submission_id: str,
    prefix: str,
    allowed: dict[str, str],
) -> tuple[Path, str]:
    """Locate a media file on disk and return (path, media_type)."""
    folder = _UPLOAD_ROOT / submission_id
    if not folder.is_dir():
        raise HTTPException(404, "Media not found")

    for child in folder.iterdir():
        if child.stem == prefix and child.suffix.lower() in allowed:
            mt = allowed[child.suffix.lower()]
            return child, mt

    raise HTTPException(404, f"No {prefix} file for this submission")


@router.get("/{submission_id}/photo")
def get_photo(submission_id: str) -> FileResponse:
    """Serve the submitted photo for a sighting."""
    path, media_type = _find_media(submission_id, "photo", _PHOTO_MEDIA_TYPES)
    return FileResponse(
        path,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/{submission_id}/audio")
def get_audio(submission_id: str) -> FileResponse:
    """Serve the submitted audio for a sighting."""
    path, media_type = _find_media(submission_id, "audio", _AUDIO_MEDIA_TYPES)
    return FileResponse(
        path,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/avatar/{user_id}")
def get_avatar(user_id: int) -> FileResponse:
    """Serve a user's avatar image."""
    folder = _AVATAR_ROOT / str(user_id)
    if not folder.is_dir():
        raise HTTPException(404, "No avatar")

    for child in folder.iterdir():
        if child.stem == "avatar" and child.suffix.lower() in _PHOTO_MEDIA_TYPES:
            mt = _PHOTO_MEDIA_TYPES[child.suffix.lower()]
            return FileResponse(
                child,
                media_type=mt,
                headers={"Cache-Control": "public, max-age=3600"},
            )

    raise HTTPException(404, "No avatar")
