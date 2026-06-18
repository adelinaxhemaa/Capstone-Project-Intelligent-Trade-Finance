from __future__ import annotations
from typing import Any
from app.schemas.common import DocumentType, Severity
from app.schemas.findings import EvidencePointer, Finding, FindingType
from app.schemas.matching import FieldMatch, MatchType
from app.tools.calculator_tool import within_tolerance
from app.tools.fuzzy_match_tool import similarity
from app.utils.ids import finding_id

# Goods-description fuzzy band: below MATCH it's a potential mismatch; within the
# [AMBIGUOUS, MATCH) band the agent may ask the LLM to flag for review.
AMBIGUOUS_LOW = 50.0


def _field(extracted: dict[str, Any], doc_type: str, field_name: str) -> str | None:
    for doc in extracted.get("documents", []):
        if doc["document_type"] != doc_type:
            continue
        for f in doc["fields"]:
            if f["name"] == field_name and f.get("confidence", 0) > 0 and f.get("value"):
                return f["value"]
    return None


def _finding(ftype: FindingType, severity: Severity, title: str, detail: str,
             doc_type: DocumentType, field_name: str) -> Finding:
    fid = finding_id(ftype.value, field_name, detail)
    return Finding(
        id=fid, type=ftype, severity=severity, title=title, description=detail,
        source_agent="agent_d_matching",
        evidence=[EvidencePointer(source_file=field_name, document_type=doc_type, field_name=field_name)],
        recommendation="Reconcile the documents or obtain a corrected one.",
    )


def compare(
    extracted: dict[str, Any],
    context: dict[str, Any],
    policy: dict[str, Any],
) -> tuple[list[FieldMatch], list[Finding]]:
    matches: list[FieldMatch] = []
    findings: list[Finding] = []
    tol = float(policy.get("amount_tolerance_pct", 5.0))
    name_threshold = float(policy.get("fuzzy", {}).get("name_match_threshold", 85))

    lc = "letter_of_credit"
    inv = "commercial_invoice"

    # 1. Amount (L/C vs invoice) within tolerance
    lc_amt = _field(extracted, lc, "total_amount")
    inv_amt = _field(extracted, inv, "total_amount")
    if lc_amt and inv_amt:
        ok, diff = within_tolerance(inv_amt, lc_amt, tol)
        fm = FieldMatch(
            field_name="amount", match_type=MatchType.TOLERANCE, matched=ok,
            values={"letter_of_credit": lc_amt, "commercial_invoice": inv_amt},
            score=None, detail=f"diff={round(diff, 2) if diff is not None else 'n/a'}% (tol {tol}%)",
        )
        if not ok:
            f = _finding(FindingType.TOLERANCE_BREACH, Severity.MAJOR,
                         "Invoice amount outside L/C tolerance",
                         f"Invoice {inv_amt} vs L/C {lc_amt} (diff {round(diff,2) if diff is not None else '?'}%, tol {tol}%).",
                         DocumentType.COMMERCIAL_INVOICE, "amount")
            fm.finding_id = f.id
            findings.append(f)
        matches.append(fm)

    # 2. Currency (exact)
    lc_cur = _field(extracted, lc, "currency")
    inv_cur = _field(extracted, inv, "currency")
    if lc_cur and inv_cur:
        ok = lc_cur.strip().upper() == inv_cur.strip().upper()
        fm = FieldMatch(field_name="currency", match_type=MatchType.EXACT, matched=ok,
                        values={"letter_of_credit": lc_cur, "commercial_invoice": inv_cur})
        if not ok:
            f = _finding(FindingType.CROSS_DOC_MISMATCH, Severity.MAJOR,
                         "Currency mismatch", f"L/C {lc_cur} vs invoice {inv_cur}.",
                         DocumentType.COMMERCIAL_INVOICE, "currency")
            fm.finding_id = f.id
            findings.append(f)
        matches.append(fm)

    # 3. Beneficiary (L/C) vs seller (invoice) — fuzzy
    lc_ben = _field(extracted, lc, "beneficiary")
    inv_sell = _field(extracted, inv, "seller")
    if lc_ben and inv_sell:
        sc = similarity(lc_ben, inv_sell)
        ok = sc >= name_threshold
        fm = FieldMatch(field_name="beneficiary_name", match_type=MatchType.FUZZY, matched=ok,
                        values={"letter_of_credit": lc_ben, "commercial_invoice": inv_sell},
                        score=round(sc / 100, 3), detail=f"fuzzy={sc:.0f} (threshold {name_threshold:.0f})")
        if not ok:
            f = _finding(FindingType.CROSS_DOC_MISMATCH, Severity.MAJOR,
                         "Beneficiary/seller name mismatch",
                         f"L/C beneficiary '{lc_ben}' vs invoice seller '{inv_sell}' (fuzzy {sc:.0f}).",
                         DocumentType.COMMERCIAL_INVOICE, "beneficiary_name")
            fm.finding_id = f.id
            findings.append(f)
        matches.append(fm)

    # 4. Ports (L/C vs B/L)
    for fld in ("port_of_loading", "port_of_discharge"):
        a = _field(extracted, lc, fld)
        b = _field(extracted, "bill_of_lading", fld)
        if a and b:
            sc = similarity(a, b)
            ok = sc >= 80
            fm = FieldMatch(field_name=fld, match_type=MatchType.FUZZY, matched=ok,
                            values={"letter_of_credit": a, "bill_of_lading": b},
                            score=round(sc / 100, 3))
            if not ok:
                f = _finding(FindingType.CROSS_DOC_MISMATCH, Severity.MINOR,
                             f"{fld} mismatch", f"L/C '{a}' vs B/L '{b}'.",
                             DocumentType.BILL_OF_LADING, fld)
                fm.finding_id = f.id
                findings.append(f)
            matches.append(fm)

    return matches, findings


def goods_description_pair(extracted: dict[str, Any]) -> tuple[str | None, str | None, float | None]:
    """Return (lc_desc, invoice_desc, fuzzy_score) for the optional semantic flag."""
    a = _field(extracted, "letter_of_credit", "goods_description")
    b = _field(extracted, "commercial_invoice", "goods_description")
    if not a or not b:
        return a, b, None
    return a, b, similarity(a, b)