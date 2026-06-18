"""UCP 600 / eUCP rule checks (pure functions).
"""

from __future__ import annotations

from typing import Any

from app.schemas.common import DocumentType, Severity
from app.schemas.findings import EvidencePointer, Finding, FindingType
from app.schemas.ucp import UCPCheck
from app.utils.dates import days_between, parse_date
from app.utils.ids import finding_id


_MANDATORY: dict[DocumentType, list[str]] = {
    DocumentType.LETTER_OF_CREDIT: ["lc_number", "expiry_date", "total_amount"],
    DocumentType.COMMERCIAL_INVOICE: ["invoice_number", "total_amount", "goods_description"],
    DocumentType.BILL_OF_LADING: ["bl_number", "shipped_on_board_date"],
    DocumentType.CERTIFICATE_OF_ORIGIN: ["country_of_origin"],
}


def _field(extracted: dict[str, Any], doc_type: str, field_name: str) -> str | None:
    """First value for (doc_type, field_name) with confidence > 0."""
    for doc in extracted.get("documents", []):
        if doc["document_type"] != doc_type:
            continue
        for f in doc["fields"]:
            if f["name"] == field_name and f.get("confidence", 0) > 0 and f.get("value"):
                return f["value"]
    return None


def _check(rule_id: str, article: str, description: str, passed: bool, detail: str) -> UCPCheck:
    return UCPCheck(rule_id=rule_id, article=article, description=description,
                    passed=passed, detail=detail)


def run_checks(
    extracted: dict[str, Any],
    context: dict[str, Any],
    policy: dict[str, Any],
) -> tuple[list[UCPCheck], list[Finding]]:
    checks: list[UCPCheck] = []
    findings: list[Finding] = []

    lc_terms = context.get("lc_terms", {})
    expiry = lc_terms.get("expiry_date")
    latest_shipment = context.get("shipment", {}).get("latest_shipment_date")
    presentation_days = lc_terms.get("presentation_period_days") or policy.get("presentation_period_days", 21)
    shipment_date = _field(extracted, "bill_of_lading", "shipped_on_board_date")
    presentation_date = context.get("presentation_date")  # optional, set by manifest

    def add_fail(rule_id, article, desc, detail, severity, ftype, evidence_field=None, doc_type=DocumentType.BILL_OF_LADING):
        checks.append(_check(rule_id, article, desc, False, detail))
        fid = finding_id(ftype.value, rule_id, detail)
        checks[-1].finding_id = fid
        findings.append(Finding(
            id=fid, type=ftype, severity=severity, title=desc, description=detail,
            source_agent="agent_c_ucp",
            evidence=[EvidencePointer(source_file=str(evidence_field or rule_id), document_type=doc_type)],
            recommendation="Review against the L/C terms.",
        ))

    # 1. Expiry present
    if expiry:
        checks.append(_check("expiry_present", "UCP600 Art. 6", "Credit has an expiry date", True, f"expiry={expiry}"))
    else:
        add_fail("expiry_present", "UCP600 Art. 6", "Credit has an expiry date",
                 "No expiry date found on the L/C.", Severity.MAJOR, FindingType.UCP_VIOLATION,
                 doc_type=DocumentType.LETTER_OF_CREDIT)

    # 2. Shipment on/before expiry
    if shipment_date and expiry:
        delta = days_between(shipment_date, expiry)
        if delta is not None and delta < 0:
            add_fail("shipment_before_expiry", "UCP600 Art. 6", "Shipment on or before credit expiry",
                     f"Shipment {shipment_date} is after credit expiry {expiry}.",
                     Severity.MAJOR, FindingType.UCP_VIOLATION)
        else:
            checks.append(_check("shipment_before_expiry", "UCP600 Art. 6",
                                 "Shipment on or before credit expiry", True,
                                 f"shipment={shipment_date}, expiry={expiry}"))
    else:
        checks.append(_check("shipment_before_expiry", "UCP600 Art. 6",
                             "Shipment on or before credit expiry", True,
                             "not evaluated (missing shipment or expiry date)"))

    # 3. Latest shipment date
    if shipment_date and latest_shipment:
        delta = days_between(shipment_date, latest_shipment)
        if delta is not None and delta < 0:
            add_fail("latest_shipment_date", "UCP600 Art. 6", "Shipment within latest shipment date",
                     f"Shipment {shipment_date} is after latest shipment date {latest_shipment}.",
                     Severity.MAJOR, FindingType.UCP_VIOLATION)
        else:
            checks.append(_check("latest_shipment_date", "UCP600 Art. 6",
                                 "Shipment within latest shipment date", True,
                                 f"shipment={shipment_date}, latest={latest_shipment}"))
    else:
        checks.append(_check("latest_shipment_date", "UCP600 Art. 6",
                             "Shipment within latest shipment date", True,
                             "not evaluated (missing date)"))

    # 4. Presentation period (21-day rule) — only if a presentation date is known
    if shipment_date and presentation_date:
        delta = days_between(shipment_date, presentation_date)
        if delta is not None and delta > int(presentation_days):
            add_fail("presentation_period", "UCP600 Art. 14(c)",
                     f"Presented within {presentation_days} days of shipment",
                     f"Presented {delta} days after shipment (limit {presentation_days}).",
                     Severity.MAJOR, FindingType.UCP_VIOLATION)
        else:
            checks.append(_check("presentation_period", "UCP600 Art. 14(c)",
                                 f"Presented within {presentation_days} days of shipment", True,
                                 f"{delta} days after shipment"))
    else:
        checks.append(_check("presentation_period", "UCP600 Art. 14(c)",
                             f"Presented within {presentation_days} days of shipment", True,
                             "not evaluated (no presentation date)"))

    return checks, findings


def mandatory_field_checks(extracted: dict[str, Any]) -> tuple[list[UCPCheck], list[Finding]]:
    checks: list[UCPCheck] = []
    findings: list[Finding] = []
    present_types = {d["document_type"] for d in extracted.get("documents", [])}

    for dtype, required in _MANDATORY.items():
        if dtype.value not in present_types:
            continue
        for field_name in required:
            value = _field(extracted, dtype.value, field_name)
            if value:
                checks.append(_check(
                    f"mandatory:{dtype.value}.{field_name}", "UCP600 Art. 14",
                    f"Mandatory field present: {dtype.value}.{field_name}", True, "present"))
            else:
                fid = finding_id(FindingType.FORMAT.value, f"{dtype.value}.{field_name}", "missing")
                checks.append(UCPCheck(
                    rule_id=f"mandatory:{dtype.value}.{field_name}", article="UCP600 Art. 14",
                    description=f"Mandatory field present: {dtype.value}.{field_name}",
                    passed=False, detail="missing", finding_id=fid))
                findings.append(Finding(
                    id=fid, type=FindingType.FORMAT, severity=Severity.MAJOR,
                    title="Mandatory field missing",
                    description=f"Required field '{field_name}' is missing from {dtype.value}.",
                    source_agent="agent_c_ucp",
                    evidence=[EvidencePointer(source_file=dtype.value, document_type=dtype)],
                    recommendation="Obtain a corrected document containing this field.",
                ))
    return checks, findings
