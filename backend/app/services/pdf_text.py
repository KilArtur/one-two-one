"""Извлечение текстового слоя из загруженных PDF-документов."""

from __future__ import annotations

import io

from pypdf import PdfReader
from pypdf.errors import PyPdfError

MAX_DOCUMENT_CHARS = 40000
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024


class PdfExtractionError(Exception):
    """Файл не читается как PDF или не содержит текстового слоя."""


def extract_pdf_text(data: bytes) -> str:
    """Извлекает текстовый слой PDF; сканы без текста считаются нечитаемыми."""
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
    except (PyPdfError, ValueError) as exc:
        raise PdfExtractionError("Не удалось прочитать PDF") from exc
    text = "\n".join(pages).strip()
    if not text:
        raise PdfExtractionError("В PDF нет текстового слоя — нужен файл с текстом, не скан")
    return text[:MAX_DOCUMENT_CHARS]
