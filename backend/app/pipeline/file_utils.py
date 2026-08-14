"""Turns uploaded files (PDF or image) into a flat list of PNG page images, ready
to hand to a vision model. PDF rendering uses PyMuPDF — no external poppler binary
needed, which matters on Windows dev machines.
"""
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image
import io

_RENDER_DPI = 200
_MAX_DIMENSION = 2200  # downscale very large phone-camera photos; vision APIs cap input size


def load_pages_as_images(file_paths: list[str]) -> list[bytes]:
    pages: list[bytes] = []
    for path_str in file_paths:
        path = Path(path_str)
        if path.suffix.lower() == ".pdf":
            pages.extend(_render_pdf(path))
        else:
            pages.append(_load_image(path))
    return pages


def _render_pdf(path: Path) -> list[bytes]:
    out: list[bytes] = []
    doc = fitz.open(path)
    try:
        zoom = _RENDER_DPI / 72
        matrix = fitz.Matrix(zoom, zoom)
        for page in doc:
            pix = page.get_pixmap(matrix=matrix)
            out.append(_downscale(pix.tobytes("png")))
    finally:
        doc.close()
    return out


def _load_image(path: Path) -> bytes:
    with Image.open(path) as img:
        return _downscale(_to_png_bytes(img))


def _to_png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def _downscale(png_bytes: bytes) -> bytes:
    with Image.open(io.BytesIO(png_bytes)) as img:
        if max(img.size) <= _MAX_DIMENSION:
            return png_bytes
        scale = _MAX_DIMENSION / max(img.size)
        new_size = (int(img.width * scale), int(img.height * scale))
        resized = img.convert("RGB").resize(new_size, Image.LANCZOS)
        return _to_png_bytes(resized)
