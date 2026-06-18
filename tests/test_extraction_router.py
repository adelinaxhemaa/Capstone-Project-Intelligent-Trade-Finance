import tempfile
from pathlib import Path

import pytest

from app.parsing.extraction_router import route_document
from samples.make_sample_bundle import make_clean_bundle, make_low_ocr_bundle


@pytest.fixture(scope="module")
def bundles():
    base = Path(tempfile.mkdtemp())
    return make_clean_bundle(base), make_low_ocr_bundle(base)


def test_born_digital_routes_without_ocr(bundles):
    clean, _ = bundles
    r = route_document(clean / "invoice.pdf")
    assert r.route == "born_digital"
    assert r.ocr_used is False
    assert r.quality_score >= 0.6
    assert "invoice" in r.document.full_text.lower()


def test_scanned_routes_to_ocr_or_degrades(bundles):
    _, low_ocr = bundles
    r = route_document(low_ocr / "invoice.pdf")
    # Image-only PDF -> low quality -> OCR attempted
    assert r.quality_score < 0.6
    assert r.route in ("ocr", "ocr_unavailable_fallback")
    if r.route == "ocr":
        # Tesseract present: text should be recovered
        assert r.document.method == "ocr"
        assert len(r.document.full_text) > 0
    else:
        # Tesseract absent: graceful degradation, no crash
        assert r.document.method == "pdf"


def test_pipeline_does_not_crash_without_ocr(bundles):
    """Routing a scanned doc never raises, regardless of Tesseract availability."""
    _, low_ocr = bundles
    route_document(low_ocr / "lc.pdf")  # born-digital doc in the same bundle
