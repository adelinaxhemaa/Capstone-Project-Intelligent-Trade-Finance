from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import fitz


@dataclass
class ParsedWord:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    page: int
    confidence: float = 1.0  # 1.0 for born-digital text; <1 for OCR


@dataclass
class ParsedPage:
    page: int
    width: float
    height: float
    words: list[ParsedWord] = field(default_factory=list)
    raw_text: str = ""  # layout-preserving text (keeps line breaks) for regex extraction

    @property
    def text(self) -> str:
        return self.raw_text if self.raw_text else " ".join(w.text for w in self.words)


@dataclass
class ParsedDocument:
    source_file: str
    page_count: int
    pages: list[ParsedPage] = field(default_factory=list)
    method: str = "pdf"          # "pdf" | "ocr" | "ocr_unavailable"
    coordinate_space: str = "pdf_points"  # or "image_pixels" for OCR
    mean_confidence: float = 1.0
    notes: list[str] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        return "\n".join(p.text for p in self.pages)

    @property
    def word_count(self) -> int:
        return sum(len(p.words) for p in self.pages)


def parse_pdf(path: str | Path) -> ParsedDocument:
    """Extract text + word-level bounding boxes from a born-digital PDF."""
    path = Path(path)
    doc = fitz.open(path)
    pages: list[ParsedPage] = []
    try:
        for pno in range(doc.page_count):
            page = doc.load_page(pno)
            rect = page.rect
            words_raw = page.get_text("words")  # (x0,y0,x1,y1, word, block, line, wno)
            words = [
                ParsedWord(
                    text=w[4], x0=w[0], y0=w[1], x1=w[2], y1=w[3], page=pno, confidence=1.0
                )
                for w in words_raw
            ]
            pages.append(ParsedPage(
                page=pno, width=rect.width, height=rect.height,
                words=words, raw_text=page.get_text("text"),
            ))
    finally:
        doc.close()
    return ParsedDocument(
        source_file=path.name,
        page_count=len(pages),
        pages=pages,
        method="pdf",
        coordinate_space="pdf_points",
        mean_confidence=1.0,
    )


def render_page_png(path: str | Path, page_number: int, dpi: int = 200) -> bytes:
    """Render one PDF page to PNG bytes (used by the OCR path)."""
    doc = fitz.open(path)
    try:
        pix = doc.load_page(page_number).get_pixmap(dpi=dpi)
        return pix.tobytes("png")
    finally:
        doc.close()
