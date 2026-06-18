from __future__ import annotations
import argparse
from pathlib import Path
import fitz

# --------------------------------------------------------------------------- #
# Document text templates (clean, consistent values across the bundle)
# --------------------------------------------------------------------------- #
LC_TEXT = """IRREVOCABLE DOCUMENTARY CREDIT
Issuing Bank: First Commercial Bank
L/C Number: LC-2024-00177
Date of Issue: 2024-01-05
Expiry Date: 2024-02-15
Credit Amount: USD 100,000.00
Applicant: Northwind Imports Ltd
Beneficiary: Acme Trading Co
Port of Loading: Shanghai
Port of Discharge: Rotterdam
Latest Shipment Date: 2024-01-25
Partial Shipment: prohibited
Transhipment: prohibited
Presentation Period: 21 days
Goods: 1000 units cotton t-shirts
"""

INVOICE_TEXT = """COMMERCIAL INVOICE
Invoice No: INV-5567
Seller (Beneficiary): Acme Trading Co
Buyer (Applicant): Northwind Imports Ltd
Description of Goods: 1000 units cotton t-shirts
Unit Price: USD 100.00
Total Amount: USD 100,000.00
"""

BOL_TEXT = """BILL OF LADING
B/L No: BL-99812
Shipper: Acme Trading Co
Consignee: Northwind Imports Ltd
Port of Loading: Shanghai
Port of Discharge: Rotterdam
Shipped on Board Date: 2024-01-20
Description: 1000 units cotton t-shirts
"""

PACKING_TEXT = """PACKING LIST
Seller: Acme Trading Co
Number of Packages: 50 cartons
Net Weight: 500 kg
Gross Weight: 560 kg
Description: 1000 units cotton t-shirts
"""

COO_TEXT = """CERTIFICATE OF ORIGIN
Country of Origin: China
Exporter: Acme Trading Co
Chamber of Commerce: Shanghai CoC
Description: 1000 units cotton t-shirts
"""

INSPECTION_TEXT = """INSPECTION CERTIFICATE
Pre-shipment Inspection
Inspected for: Northwind Imports Ltd
Result: Goods conform to specification
Description: 1000 units cotton t-shirts
"""

MANIFEST = """bundle_id: bundle_01_clean
jurisdiction: eu
documents:
  - file: lc.pdf
    type: letter_of_credit
  - file: invoice.pdf
    type: commercial_invoice
  - file: bill_of_lading.pdf
    type: bill_of_lading
  - file: packing_list.pdf
    type: packing_list
  - file: certificate_of_origin.pdf
    type: certificate_of_origin
  - file: inspection_certificate.pdf
    type: inspection_certificate
sanctions_policy: sanctions_policy.yaml
"""

SANCTIONS_POLICY = """# Per-bundle sanctions policy override (transaction-specific).
sanctions:
  match_threshold: 90
"""

_DOCS = {
    "lc.pdf": LC_TEXT,
    "invoice.pdf": INVOICE_TEXT,
    "bill_of_lading.pdf": BOL_TEXT,
    "packing_list.pdf": PACKING_TEXT,
    "certificate_of_origin.pdf": COO_TEXT,
    "inspection_certificate.pdf": INSPECTION_TEXT,
}


def _write_text_pdf(path: Path, text: str) -> None:
    """Born-digital PDF with a real, selectable text layer."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 60), text, fontsize=11, fontname="helv")
    doc.save(path)
    doc.close()


def _write_scanned_pdf(path: Path, text: str) -> None:
    """Image-only, MODERATELY degraded PDF. Goal: no text layer, OCR confidence
    dips below the low-confidence cutoff (so fields flag for review and the LLM
    fallback fires) but the text stays legible enough that the LLM can recover
    it. Too much noise => OCR returns garbage the model can't read; too little
    => confidence stays high and the fallback never triggers."""
    import io as _io

    from PIL import Image, ImageFilter

    tmp = fitz.open()
    page = tmp.new_page()
    page.insert_text((50, 60), text, fontsize=12, fontname="helv")
    pix = page.get_pixmap(dpi=110)
    tmp.close()

    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("L")
    # Light blur: keeps OCR text legible (so the LLM fallback can recover it).
    # The image-only PDF has no text layer, so it routes to OCR regardless; the
    # low-confidence FLAG comes from the policy's OCR confidence ceiling, not from
    # destroying legibility. This makes scenario 8 reproducible across machines.
    img = img.filter(ImageFilter.GaussianBlur(radius=0.7))

    buf = _io.BytesIO()
    img.save(buf, format="PNG")

    out = fitz.open()
    opage = out.new_page(width=pix.width, height=pix.height)
    opage.insert_image(opage.rect, stream=buf.getvalue())
    out.save(path)
    out.close()


def make_lc_only(base: Path) -> Path:
    d = base / "lc_only"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "lc_only_001.pdf"
    _write_text_pdf(p, LC_TEXT)
    return p


def make_clean_bundle(base: Path) -> Path:
    d = base / "bundle_01_clean"
    d.mkdir(parents=True, exist_ok=True)
    for name, text in _DOCS.items():
        _write_text_pdf(d / name, text)
    (d / "manifest.yaml").write_text(MANIFEST, encoding="utf-8")
    (d / "sanctions_policy.yaml").write_text(SANCTIONS_POLICY, encoding="utf-8")
    return d


def make_low_ocr_bundle(base: Path) -> Path:
    d = base / "bundle_08_low_ocr"
    d.mkdir(parents=True, exist_ok=True)
    for name, text in _DOCS.items():
        if name == "invoice.pdf":
            _write_scanned_pdf(d / name, INVOICE_TEXT)  # image-only → OCR path
        else:
            _write_text_pdf(d / name, text)
    (d / "manifest.yaml").write_text(MANIFEST.replace("bundle_01_clean", "bundle_08_low_ocr"), encoding="utf-8")
    (d / "sanctions_policy.yaml").write_text(SANCTIONS_POLICY, encoding="utf-8")
    return d


def make_bl_expiry_bundle(base: Path) -> Path:
    """Scenario 2: B/L shipped-on-board date AFTER the L/C expiry -> discrepancy."""
    d = base / "bundle_02_bl_expiry"
    d.mkdir(parents=True, exist_ok=True)
    bad_bol = BOL_TEXT.replace("Shipped on Board Date: 2024-01-20",
                               "Shipped on Board Date: 2024-03-01")  # after expiry 2024-02-15
    for name, text in _DOCS.items():
        _write_text_pdf(d / name, bad_bol if name == "bill_of_lading.pdf" else text)
    (d / "manifest.yaml").write_text(MANIFEST.replace("bundle_01_clean", "bundle_02_bl_expiry"), encoding="utf-8")
    (d / "sanctions_policy.yaml").write_text(SANCTIONS_POLICY, encoding="utf-8")
    return d


def make_amount_tolerance_bundle(base: Path) -> Path:
    """Scenario 3: invoice amount above L/C value beyond tolerance."""
    d = base / "bundle_03_amount_tolerance"
    d.mkdir(parents=True, exist_ok=True)
    bad_inv = INVOICE_TEXT.replace("Total Amount: USD 100,000.00", "Total Amount: USD 130,000.00") \
                          .replace("Unit Price: USD 100.00", "Unit Price: USD 130.00")
    for name, text in _DOCS.items():
        _write_text_pdf(d / name, bad_inv if name == "invoice.pdf" else text)
    (d / "manifest.yaml").write_text(MANIFEST.replace("bundle_01_clean", "bundle_03_amount_tolerance"), encoding="utf-8")
    (d / "sanctions_policy.yaml").write_text(SANCTIONS_POLICY, encoding="utf-8")
    return d


def make_sanctions_bundle(base: Path) -> Path:
    """Scenario 6: beneficiary matches a sanctions list entry -> freeze/refuse."""
    d = base / "bundle_06_sanctions_hit"
    d.mkdir(parents=True, exist_ok=True)
    bad_lc = LC_TEXT.replace("Beneficiary: Acme Trading Co", "Beneficiary: Darkstar Shipping Ltd")
    bad_inv = INVOICE_TEXT.replace("Seller (Beneficiary): Acme Trading Co",
                                   "Seller (Beneficiary): Darkstar Shipping Ltd")
    for name, text in _DOCS.items():
        if name == "lc.pdf":
            _write_text_pdf(d / name, bad_lc)
        elif name == "invoice.pdf":
            _write_text_pdf(d / name, bad_inv)
        else:
            _write_text_pdf(d / name, text)
    (d / "manifest.yaml").write_text(MANIFEST.replace("bundle_01_clean", "bundle_06_sanctions_hit"), encoding="utf-8")
    (d / "sanctions_policy.yaml").write_text(SANCTIONS_POLICY, encoding="utf-8")
    return d


def make_currency_mismatch_bundle(base: Path) -> Path:
    """Scenario: invoice currency (EUR) differs from L/C currency (USD)."""
    d = base / "bundle_04_currency_mismatch"
    d.mkdir(parents=True, exist_ok=True)
    bad_inv = INVOICE_TEXT.replace("Total Amount: USD 100,000.00", "Total Amount: EUR 100,000.00")
    for name, text in _DOCS.items():
        _write_text_pdf(d / name, bad_inv if name == "invoice.pdf" else text)
    (d / "manifest.yaml").write_text(MANIFEST.replace("bundle_01_clean", "bundle_04_currency_mismatch"), encoding="utf-8")
    (d / "sanctions_policy.yaml").write_text(SANCTIONS_POLICY, encoding="utf-8")
    return d


def make_name_variation_bundle(base: Path) -> Path:
    """Scenario: invoice seller name differs from L/C beneficiary beyond the
    fuzzy threshold (tests cross-document party matching)."""
    d = base / "bundle_05_name_variation"
    d.mkdir(parents=True, exist_ok=True)
    bad_inv = INVOICE_TEXT.replace("Seller (Beneficiary): Acme Trading Co",
                                   "Seller (Beneficiary): Globex Industrial Exports Ltd")
    for name, text in _DOCS.items():
        _write_text_pdf(d / name, bad_inv if name == "invoice.pdf" else text)
    (d / "manifest.yaml").write_text(MANIFEST.replace("bundle_01_clean", "bundle_05_name_variation"), encoding="utf-8")
    (d / "sanctions_policy.yaml").write_text(SANCTIONS_POLICY, encoding="utf-8")
    return d


def make_late_presentation_bundle(base: Path) -> Path:
    """Scenario 7: documents presented more than 21 days after shipment
    (UCP 600 Art. 14c). Presentation date comes from the manifest."""
    d = base / "bundle_07_late_presentation"
    d.mkdir(parents=True, exist_ok=True)
    for name, text in _DOCS.items():
        _write_text_pdf(d / name, text)  # clean docs; lateness is in the manifest
    manifest = (MANIFEST.replace("bundle_01_clean", "bundle_07_late_presentation")
                + "presentation_date: 2024-02-14\n")  # shipped 2024-01-20 -> 25 days > 21
    (d / "manifest.yaml").write_text(manifest, encoding="utf-8")
    (d / "sanctions_policy.yaml").write_text(SANCTIONS_POLICY, encoding="utf-8")
    return d


def make_multi_discrepancy_bundle(base: Path) -> Path:
    """Scenario 9: several discrepancies at once (amount over tolerance +
    B/L after expiry + currency mismatch)."""
    d = base / "bundle_09_multi_discrepancy"
    d.mkdir(parents=True, exist_ok=True)
    bad_inv = INVOICE_TEXT.replace("Total Amount: USD 100,000.00", "Total Amount: EUR 130,000.00")
    bad_bol = BOL_TEXT.replace("Shipped on Board Date: 2024-01-20", "Shipped on Board Date: 2024-03-01")
    for name, text in _DOCS.items():
        if name == "invoice.pdf":
            _write_text_pdf(d / name, bad_inv)
        elif name == "bill_of_lading.pdf":
            _write_text_pdf(d / name, bad_bol)
        else:
            _write_text_pdf(d / name, text)
    (d / "manifest.yaml").write_text(MANIFEST.replace("bundle_01_clean", "bundle_09_multi_discrepancy"), encoding="utf-8")
    (d / "sanctions_policy.yaml").write_text(SANCTIONS_POLICY, encoding="utf-8")
    return d


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="tests/bundles", help="base output directory")
    args = ap.parse_args()
    base = Path(args.out)
    base.mkdir(parents=True, exist_ok=True)
    builders = [
        make_lc_only, make_clean_bundle, make_bl_expiry_bundle, make_currency_mismatch_bundle,
        make_name_variation_bundle, make_sanctions_bundle, make_late_presentation_bundle,
        make_low_ocr_bundle, make_multi_discrepancy_bundle, make_amount_tolerance_bundle,
    ]
    print("Wrote:")
    for b in builders:
        print("  ", b(base))


if __name__ == "__main__":
    main()
