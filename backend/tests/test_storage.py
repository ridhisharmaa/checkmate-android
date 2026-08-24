"""Regression tests for upload filename handling.

Two bugs these pin down, both stemming from joining a client-supplied filename
straight onto the destination directory:
  * "../../.." segments escaped the storage root entirely;
  * two uploads sharing a name resolved to one path, so the second silently
    overwrote the first and a page vanished with no error.
"""
import os
from pathlib import Path

import pytest

from app.storage.local import safe_filename, save_bytes


@pytest.fixture()
def storage_root(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    from app.config import get_settings

    get_settings.cache_clear()  # Settings is lru_cached; drop the previous root
    yield tmp_path
    get_settings.cache_clear()


def test_same_filename_twice_keeps_both_pages(storage_root):
    first = save_bytes("sub1", "student", 0, "image.jpg", b"PAGE ONE")
    second = save_bytes("sub1", "student", 1, "image.jpg", b"PAGE TWO")

    assert first != second
    assert Path(first).read_bytes() == b"PAGE ONE"
    assert Path(second).read_bytes() == b"PAGE TWO"


def test_traversal_in_filename_stays_inside_storage_root(storage_root, tmp_path):
    # Aim the traversal at a sibling of the storage root, so the assertion is about
    # this test's own directory rather than some shared global path.
    escape_target = tmp_path.parent / "escaped_here.txt"
    depth = len(storage_root.resolve().parts)
    path = Path(save_bytes("sub2", "teacher", 0, f"{'../' * depth}{escape_target}", b"escaped"))

    assert storage_root.resolve() in path.resolve().parents
    assert not escape_target.exists()


@pytest.mark.parametrize(
    "raw",
    [
        "../../etc/passwd",
        "/absolute/path/key.pdf",
        "..",
        "...",
        "",
        None,
        "sheet with spaces.png",
        "wéird*chars?.jpeg",
    ],
)
def test_safe_filename_always_yields_one_harmless_segment(raw):
    name = safe_filename(raw)

    assert name, "must never be empty"
    assert os.sep not in name and "/" not in name
    assert name == Path(name).name
    assert not name.startswith(".")


def test_safe_filename_preserves_the_extension():
    # file_utils dispatches PDF vs image on the suffix, so it has to survive.
    assert safe_filename("answer key.pdf").endswith(".pdf")
    assert safe_filename("../../scan.PNG").endswith(".PNG")


def test_stored_pdf_keeps_its_suffix(storage_root):
    path = save_bytes("sub3", "teacher", 2, "my key.pdf", b"%PDF-1.4")

    assert Path(path).suffix.lower() == ".pdf"
    assert Path(path).name.startswith("002_")
