from __future__ import annotations
import io
from pathlib import Path
from app.config import get_settings
from app.parsing.pdf_parser import ParsedDocument, ParsedPage, ParsedWord, render_page_png


def _configure_tesseract() -> "object | None":
    """Point pytesseract at the binary (Windows often needs an explicit path).
    Returns the pytesseract module, or None if it can't be imported."""
    try:
        import pytesseract
    except ImportError:
        return None
    cmd = get_settings().tesseract_cmd
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd
    return pytesseract


def ocr_pdf(path: str | Path, dpi: int = 200) -> ParsedDocument:
    path = Path(path)
    pytesseract = _configure_tesseract()
    if pytesseract is None:
        return ParsedDocument(
            source_file=path.name, page_count=0, method="ocr_unavailable",
            mean_confidence=0.0, notes=["pytesseract not importable"],
        )

    try:
        from PIL import Image
    except ImportError:
        return ParsedDocument(
            source_file=path.name, page_count=0, method="ocr_unavailable",
            mean_confidence=0.0, notes=["Pillow not importable"],
        )

    # Determine page count via a render attempt; reuse fitz through pdf_parser helper.
    import fitz
    doc = fitz.open(path)
    n_pages = doc.page_count
    doc.close()

    pages: list[ParsedPage] = []
    confidences: list[float] = []
    try:
        for pno in range(n_pages):
            png = render_page_png(path, pno, dpi=dpi)
            image = Image.open(io.BytesIO(png))
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
            words: list[ParsedWord] = []
            for i, text in enumerate(data["text"]):
                if not text.strip():
                    continue
                conf_raw = float(data["conf"][i])
                conf = max(0.0, conf_raw) / 100.0
                if conf_raw >= 0:
                    confidences.append(conf)
                x, y, w, h = (data["left"][i], data["top"][i], data["width"][i], data["height"][i])
                words.append(
                    ParsedWord(text=text, x0=x, y0=y, x1=x + w, y1=y + h, page=pno, confidence=conf)
                )
            raw = pytesseract.image_to_string(image)
            pages.append(ParsedPage(page=pno, width=image.width, height=image.height,
                                    words=words, raw_text=raw))
    except Exception as exc:  # TesseractNotFoundError, etc. — degrade, don't crash
        return ParsedDocument(
            source_file=path.name, page_count=0, method="ocr_unavailable",
            mean_confidence=0.0, notes=[f"OCR failed: {type(exc).__name__}: {exc}"],
        )

    mean_conf = round(sum(confidences) / len(confidences), 4) if confidences else 0.0
    return ParsedDocument(
        source_file=path.name, page_count=len(pages), pages=pages, method="ocr",
        coordinate_space="image_pixels", mean_confidence=mean_conf,
    )
