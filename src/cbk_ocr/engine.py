from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

import logging

import pdfplumber

logger = logging.getLogger(__name__)


@dataclass
class OcrPage:
    page_number: int
    text: str


@dataclass
class OcrResult:
    pages: List[OcrPage]

    @property
    def plain_text(self) -> str:
        return "\n\n".join(page.text for page in self.pages if page.text)


class TextFirstOcrEngine:
    """Simple text-first OCR engine using pdfplumber only.

    This is designed so that OCR backends (e.g. ocrmypdf + tesseract) can be
    plugged in later for scanned PDFs, while keeping the interface stable.
    """

    def extract(self, pdf_path: Path) -> OcrResult:
        pages: List[OcrPage] = []
        pdf_path = pdf_path.resolve()
        logger.info("OCR extracting text: %s", pdf_path)
        try:
            with pdfplumber.open(str(pdf_path)) as pdf:
                for idx, page in enumerate(pdf.pages, start=1):
                    text = page.extract_text() or ""
                    pages.append(OcrPage(page_number=idx, text=text))
        except Exception as exc:
            logger.exception("Failed to extract text from %s: %s", pdf_path, exc)
            raise
        return OcrResult(pages=pages)

