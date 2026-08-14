"""Local-disk file storage, behind a small interface so swapping to S3-style
storage later touches only this module, not pipeline/API code."""
from pathlib import Path

from fastapi import UploadFile

from app.config import get_settings


async def save_upload(submission_id: str, role: str, file: UploadFile) -> str:
    """role: 'teacher' or 'student'. Returns the saved file's path as a string."""
    return save_bytes(submission_id, role, file.filename, await file.read())


def save_bytes(submission_id: str, role: str, filename: str, contents: bytes) -> str:
    dest_dir = get_settings().storage_root_path / submission_id / role
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / filename
    dest_path.write_bytes(contents)
    return str(dest_path)


def read_bytes(path: str) -> bytes:
    return Path(path).read_bytes()
