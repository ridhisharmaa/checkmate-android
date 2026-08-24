"""Local-disk file storage, behind a small interface so swapping to S3-style
storage later touches only this module, not pipeline/API code."""
import re
from pathlib import Path

from fastapi import UploadFile

from app.config import get_settings

_UNSAFE_CHARS_RE = re.compile(r"[^A-Za-z0-9._-]+")
_MAX_STEM_LEN = 80


def safe_filename(filename: str | None, fallback_suffix: str = ".bin") -> str:
    """Reduce a client-supplied filename to a single harmless path segment.

    Upload filenames come from the client and are not trustworthy: PurePath joining
    on "../../etc/x" happily escapes the storage root. Take the basename only, drop
    anything that isn't a plain filename character, and never return an empty string
    or a name that is all dots.
    """
    name = Path(filename or "").name  # strips directories AND any traversal segments
    name = _UNSAFE_CHARS_RE.sub("_", name).lstrip(".")
    if not name:
        return f"upload{fallback_suffix}"

    stem, dot, suffix = name.rpartition(".")
    if not dot:  # no extension
        return name[:_MAX_STEM_LEN]
    return f"{stem[:_MAX_STEM_LEN]}.{suffix}" if stem else f"upload.{suffix}"


async def save_upload(submission_id: str, role: str, index: int, file: UploadFile) -> str:
    """role: 'teacher' or 'student'. Returns the saved file's path as a string."""
    return save_bytes(submission_id, role, index, file.filename, await file.read())


def save_bytes(submission_id: str, role: str, index: int, filename: str | None, contents: bytes) -> str:
    """`index` is the file's position within its role, and is prefixed onto the stored
    name. Two uploads sharing a filename (phone cameras and scanners reuse names freely)
    previously resolved to the same path, so the second silently overwrote the first and
    a page went missing with no error anywhere.
    """
    dest_dir = get_settings().storage_root_path / submission_id / role
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"{index:03d}_{safe_filename(filename)}"
    dest_path.write_bytes(contents)
    return str(dest_path)


def read_bytes(path: str) -> bytes:
    return Path(path).read_bytes()
