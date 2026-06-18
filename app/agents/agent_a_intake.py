"""Agent A — Document Intake & Context.

Responsibilities:
  - detect single-L/C vs Trade Bundle; validate the manifest; flag non-compliant
    formats and a missing required document set
  - classify each document (verifying against any manifest-declared type)
  - pull the key L/C terms into a ContextPacket (light, regex-based — Agent B does
    full per-document field extraction later)
  - build the universal EvidenceIndex (field -> document + page + bbox)
  - apply intake risk heuristics (high-risk jurisdiction, unusual document set)

Writes context_packet.json + evidence_index.json into the run dir and returns a
state update for the LangGraph pipeline.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from app.parsing import classifier
from app.parsing.extraction_router import route_document
from app.parsing.field_extraction import extract_value
from app.parsing.pdf_parser import ParsedDocument, ParsedWord
from app.schemas.common import DocumentType, Severity
from app.schemas.context import (
    ClassifiedDocument,
    ContextPacket,
    EvidenceIndex,
    EvidenceItem,
    LCTerms,
    Party,
    ShipmentParams,
)
from app.schemas.findings import EvidencePointer, Finding, FindingType
from app.tools.policy_loader import load_policy
from app.utils.dates import normalize_date
from app.utils.ids import finding_id
from app.utils.io import write_json

# Documents we expect in a full Trade Bundle (for the "unusual set" risk check).
_EXPECTED_BUNDLE_DOCS = {
    DocumentType.LETTER_OF_CREDIT,
    DocumentType.COMMERCIAL_INVOICE,
    DocumentType.BILL_OF_LADING,
    DocumentType.PACKING_LIST,
    DocumentType.CERTIFICATE_OF_ORIGIN,
}

_ALLOWED_SUFFIXES = {".pdf"}  # documents must be PDFs; yaml/policy files handled separately


def _presentation_days(text: str) -> int | None:
    """Presentation period in days, e.g. 'Presentation Period: 21 days' or
    'within 21 calendar days after the shipment date'."""
    m = re.search(r"(?:presentation period[:\-\s]+|within\s+)(\d{1,3})\s*(?:calendar\s*)?days",
                  text, flags=re.IGNORECASE)
    return int(m.group(1)) if m else None


def _first_word_bbox(parsed: ParsedDocument, needle: str) -> ParsedWord | None:
    needle = needle.lower()
    for page in parsed.pages:
        for w in page.words:
            if needle in w.text.lower():
                return w
    return None


def _extract_lc_terms(parsed: ParsedDocument) -> tuple[LCTerms, list[Party], ShipmentParams]:
    text = parsed.full_text
    amount = extract_value(text, [r"currency\s*/\s*amount", r"credit amount", r"total amount", r"amount"], "amount")
    currency = extract_value(text, [r"currency\s*/\s*amount", r"currency", r"credit amount", r"amount"], "currency")
    amount_val = None
    if amount:
        try:
            amount_val = float(amount.replace(",", ""))
        except ValueError:
            amount_val = None

    pres = _presentation_days(text)
    lc = LCTerms(
        lc_number=extract_value(text, [r"documentary credit number", r"letter of credit number",
                                       r"credit number", r"l/?c number", r"credit no"], "id"),
        issue_date=extract_value(text, [r"date of issue", r"issue date"], "date"),
        expiry_date=extract_value(text, [r"expiry date and place", r"date of expiry",
                                         r"expiry date", r"expiry"], "date"),
        amount=amount_val,
        currency=currency,
        presentation_period_days=pres,
    )

    parties: list[Party] = []
    ben = extract_value(text, [r"beneficiary"], "name")
    app = extract_value(text, [r"applicant"], "name")
    if ben:
        parties.append(Party(name=ben, role="beneficiary"))
    if app:
        parties.append(Party(name=app, role="applicant"))

    partial = extract_value(text, [r"partial shipment", r"partial shipments"], "flag")
    trans = extract_value(text, [r"transhipment", r"transshipment"], "flag")
    shipment = ShipmentParams(
        latest_shipment_date=extract_value(text, [r"latest shipment date", r"latest shipment"], "date"),
        partial_shipment_allowed=(partial == "allowed") if partial else None,
        transhipment_allowed=(trans == "allowed") if trans else None,
    )
    return lc, parties, shipment


# --------------------------------------------------------------------------- #
# Input resolution
# --------------------------------------------------------------------------- #
def _doc_entry_name(entry: Any) -> str | None:
    """Pull a filename from a manifest 'documents' entry of any common shape:
    a plain string, or a dict keyed by file/filename/name/path."""
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        for key in ("file", "filename", "name", "path"):
            if entry.get(key):
                return str(entry[key])
    return None


def _doc_entry_type(entry: Any) -> str | None:
    if isinstance(entry, dict):
        for key in ("type", "doc_type", "document_type"):
            if entry.get(key):
                return str(entry[key])
    return None


def manifest_hints(manifest: dict[str, Any]) -> dict[str, str | None]:
    """filename -> declared type, tolerant of manifest shape."""
    hints: dict[str, str | None] = {}
    for entry in manifest.get("documents", []) or []:
        name = _doc_entry_name(entry)
        if name:
            hints[Path(name).name] = _doc_entry_type(entry)
    return hints


def _load_manifest(folder: Path) -> dict[str, Any]:
    """Find manifest.yaml in the folder or its parent; tolerate parse errors."""
    for candidate in (folder / "manifest.yaml", folder.parent / "manifest.yaml"):
        if candidate.exists():
            try:
                data = yaml.safe_load(candidate.read_text(encoding="utf-8"))
                return data if isinstance(data, dict) else {}
            except yaml.YAMLError:
                return {}
    return {}


def _resolve_inputs(input_path: str | Path) -> tuple[bool, list[Path], dict[str, Any]]:
    """Return (is_bundle, document_paths, manifest_dict). Raises FileNotFoundError
    if the path doesn't exist (clearer than silently treating it as a file)."""
    p = Path(input_path)
    if not p.exists():
        raise FileNotFoundError(f"Input path does not exist: {p}")

    if p.is_dir():
        manifest = _load_manifest(p)
        docs: list[Path] = []
        for entry in manifest.get("documents", []) or []:
            name = _doc_entry_name(entry)
            if name:
                docs.append(p / Path(name).name)
        # No usable manifest entries (or different shape) -> glob every PDF.
        if not docs:
            docs = sorted(p.glob("*.pdf"))
        return True, docs, manifest
    # single file
    return False, [p], {}


# --------------------------------------------------------------------------- #
# Main entry point
# --------------------------------------------------------------------------- #
def run_agent_a(input_path: str | Path, run_dir: str | Path | None = None) -> dict[str, Any]:
    is_bundle, doc_paths, manifest = _resolve_inputs(input_path)
    jurisdiction = (manifest.get("jurisdiction") or None)
    run_id = manifest.get("bundle_id", "run")

    findings: list[Finding] = []
    classified: list[ClassifiedDocument] = []
    evidence_items: list[EvidenceItem] = []
    hints = manifest_hints(manifest)

    lc_terms = LCTerms()
    parties: list[Party] = []
    shipment = ShipmentParams()

    for path in doc_paths:
        # Format check
        if path.suffix.lower() not in _ALLOWED_SUFFIXES:
            findings.append(Finding(
                id=finding_id(FindingType.FORMAT.value, path.name, "bad_format"),
                type=FindingType.FORMAT, severity=Severity.MAJOR,
                title="Non-compliant document format",
                description=f"{path.name} is not a PDF and cannot be examined.",
                source_agent="agent_a_intake",
                evidence=[EvidencePointer(source_file=path.name, document_type=DocumentType.UNKNOWN)],
                recommendation="Resubmit this document as a PDF.",
            ))
            continue
        if not path.exists():
            findings.append(Finding(
                id=finding_id(FindingType.FORMAT.value, path.name, "missing_file"),
                type=FindingType.FORMAT, severity=Severity.MAJOR,
                title="Declared document missing",
                description=f"Manifest lists {path.name} but the file was not found.",
                source_agent="agent_a_intake",
                evidence=[EvidencePointer(source_file=path.name, document_type=DocumentType.UNKNOWN)],
            ))
            continue

        routed = route_document(path)
        parsed = routed.document
        dtype = classifier.classify(parsed, manifest_hint=hints.get(path.name))
        classified.append(ClassifiedDocument(
            source_file=path.name, document_type=dtype, page_count=parsed.page_count
        ))

        # Manifest type mismatch
        declared = hints.get(path.name)
        if declared and declared != dtype.value:
            findings.append(Finding(
                id=finding_id(FindingType.FORMAT.value, path.name, "type_mismatch"),
                type=FindingType.FORMAT, severity=Severity.MINOR,
                title="Document type mismatch",
                description=f"{path.name} declared as '{declared}' but classified as '{dtype.value}'.",
                source_agent="agent_a_intake",
                evidence=[EvidencePointer(source_file=path.name, document_type=dtype)],
            ))

        # Pull L/C terms from the L/C
        if dtype == DocumentType.LETTER_OF_CREDIT:
            lc_terms, parties, shipment = _extract_lc_terms(parsed)
            for fld in ("lc_number", "expiry_date", "amount"):
                value = getattr(lc_terms, fld, None)
                if value is not None:
                    w = _first_word_bbox(parsed, str(value).split()[0]) if value else None
                    bbox = None
                    if w:
                        from app.tools.evidence_tool import make_bbox
                        bbox = make_bbox(w.page, w.x0, w.y0, w.x1, w.y1)
                    evidence_items.append(EvidenceItem(
                        field_name=fld, source_file=path.name, document_type=dtype, bbox=bbox,
                        text_snippet=str(value),
                    ))

    # Risk heuristics
    risk_flags: list[str] = []
    policy = load_policy(jurisdiction)
    high_risk = set(policy.get("country_risk", {}).get("high", []))
    for party in parties:
        if party.country and party.country.upper() in high_risk:
            risk_flags.append(f"high_risk_jurisdiction:{party.country}")
    if is_bundle:
        present = {c.document_type for c in classified}
        missing = _EXPECTED_BUNDLE_DOCS - present
        if missing:
            risk_flags.append("unusual_document_set")
            findings.append(Finding(
                id=finding_id(FindingType.OTHER.value, "bundle", "missing_docs"),
                type=FindingType.OTHER, severity=Severity.MINOR,
                title="Incomplete document set",
                description="Bundle is missing expected documents: "
                            + ", ".join(sorted(m.value for m in missing)),
                source_agent="agent_a_intake",
                recommendation="Confirm whether the missing documents are required for this credit.",
            ))

    context = ContextPacket(
        run_id=str(run_id),
        documents=classified,
        lc_terms=lc_terms,
        parties=parties,
        shipment=shipment,
        presentation_date=normalize_date(manifest.get("presentation_date")),
        applicable_rules=["UCP600"] + (["eUCP"] if jurisdiction else []),
        risk_flags=risk_flags,
    )
    evidence_index = EvidenceIndex(run_id=str(run_id), items=evidence_items)

    if run_dir is not None:
        run_dir = Path(run_dir)
        write_json(run_dir / "context_packet.json", context)
        write_json(run_dir / "evidence_index.json", evidence_index)

    return {
        "is_bundle": is_bundle,
        "jurisdiction": jurisdiction,
        "context_packet": context.model_dump(mode="json"),
        "evidence_index": evidence_index.model_dump(mode="json"),
        "findings": [f.model_dump(mode="json") for f in findings],
        "trace": [{"agent": "agent_a_intake", "documents": len(classified),
                   "findings": len(findings), "risk_flags": risk_flags}],
    }
