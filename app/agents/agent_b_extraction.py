from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Any
from app.agents.agent_a_intake import _EXPECTED_BUNDLE_DOCS, _resolve_inputs
from app.config import ROOT_DIR, get_settings
from app.llm import extractor as llm_extractor
from app.parsing.extraction_router import route_document
from app.parsing.field_extraction import extract_value
from app.parsing.pdf_parser import ParsedDocument
from app.schemas.common import DocumentType
from app.schemas.extraction import DocumentExtraction, ExtractedDocs, ExtractedField
from app.tools.evidence_tool import make_bbox
from app.tools.policy_loader import load_policy
from app.utils.io import write_csv, write_json

# Per-document-type field specs: name -> (label patterns, value kind).
# The label-driven extractor (with validation) handles SWIFT "(Field NN)" tags
# and values on the next line.
_FIELD_SPECS: dict[DocumentType, dict[str, tuple[list[str], str]]] = {
    DocumentType.LETTER_OF_CREDIT: {
        "lc_number": ([r"documentary credit number", r"letter of credit number",
                       r"credit number", r"l/?c number", r"credit no"], "id"),
        "issue_date": ([r"date of issue", r"issue date"], "date"),
        "expiry_date": ([r"expiry date and place", r"date of expiry", r"expiry date", r"expiry"], "date"),
        "total_amount": ([r"currency\s*/\s*amount", r"credit amount", r"total amount", r"amount"], "amount"),
        "currency": ([r"currency\s*/\s*amount", r"currency", r"credit amount", r"amount"], "currency"),
        "beneficiary": ([r"beneficiary"], "name"),
        "applicant": ([r"applicant"], "name"),
        "port_of_loading": ([r"port of loading"], "text"),
        "port_of_discharge": ([r"port of discharge"], "text"),
        "goods_description": ([r"description of goods", r"goods"], "text"),
    },
    DocumentType.COMMERCIAL_INVOICE: {
        "invoice_number": ([r"invoice number", r"invoice no"], "id"),
        "seller": ([r"seller\s*/\s*exporter", r"seller", r"exporter"], "name"),
        "buyer": ([r"buyer\s*/\s*importer", r"buyer", r"importer"], "name"),
        "total_amount": ([r"total invoice amount", r"total amount", r"grand total", r"amount due", r"invoice total"], "amount"),
        "currency": ([r"total invoice amount", r"total amount", r"amount due", r"currency"], "currency"),
        "goods_description": ([r"description of goods", r"description of", r"goods"], "text"),
    },
    DocumentType.BILL_OF_LADING: {
        "bl_number": ([r"bill of lading number", r"b/?l number", r"b/?l no"], "id"),
        "shipper": ([r"shipper"], "name"),
        "consignee": ([r"consignee"], "name"),
        "shipped_on_board_date": ([r"date shipped on board", r"shipped on board date",
                                   r"shipped on board"], "date"),
        "port_of_loading": ([r"port of loading"], "text"),
        "port_of_discharge": ([r"port of discharge"], "text"),
        "goods_description": ([r"description"], "text"),
    },
    DocumentType.PACKING_LIST: {
        "number_of_packages": ([r"total cartons", r"number of packages", r"total quantity"], "text"),
        "net_weight": ([r"total net weight", r"net weight"], "text"),
        "goods_description": ([r"description"], "text"),
    },
    DocumentType.CERTIFICATE_OF_ORIGIN: {
        "country_of_origin": ([r"country of origin"], "text"),
        "exporter": ([r"exporter"], "name"),
        "goods_description": ([r"description of goods", r"description"], "text"),
    },
    DocumentType.INSPECTION_CERTIFICATE: {
        "result": ([r"conclusion", r"result"], "text"),
        "goods_description": ([r"goods inspected", r"description"], "text"),
    },
}


def _load_synthetic_defaults() -> dict[str, dict[str, Any]]:
    path = ROOT_DIR / "app" / "data" / "synthetic" / "defaults.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _confidence_for(matched: bool, parsed: ParsedDocument, ocr_ceiling: float) -> float:
    if not matched:
        return 0.0
    if parsed.method == "ocr":
        # Scanned-sourced fields are inherently less trustworthy than born-digital;
        # cap them below the review cutoff so they're verified (and the LLM fallback
        # can assist). Deterministic and independent of the exact OCR confidence.
        return round(min(ocr_ceiling, parsed.mean_confidence), 2)
    return 0.95  # clean born-digital match


def _find_bbox(parsed: ParsedDocument, value: str):
    if not value:
        return None
    token = value.split()[0]
    for page in parsed.pages:
        for w in page.words:
            if token.lower() in w.text.lower():
                return make_bbox(w.page, w.x0, w.y0, w.x1, w.y1)
    return None


def _extract_one_document(
    source_file: str,
    parsed: ParsedDocument,
    doc_type: DocumentType,
    cutoff: float,
    ocr_ceiling: float,
    use_llm: bool,
) -> tuple[DocumentExtraction, list[dict]]:
    text = parsed.full_text
    specs = _FIELD_SPECS.get(doc_type, {})
    fields: list[ExtractedField] = []
    llm_log: list[dict] = []

    for field_name, (labels, kind) in specs.items():
        value = extract_value(text, labels, kind)
        confidence = _confidence_for(value is not None, parsed, ocr_ceiling)
        bbox = _find_bbox(parsed, value) if value else None
        low = confidence < cutoff
        llm_derived = False

        # LLM fallback only for low-confidence fields, only when enabled.
        if low and use_llm:
            guess = llm_extractor.extract_field(field_name, doc_type.value, text)
            if guess is not None and guess.value:
                value = guess.value
                confidence = round(min(0.9, guess.confidence), 2)
                low = confidence < cutoff
                llm_derived = True
                llm_log.append({"field": field_name, "doc": source_file, "value": value})

        fields.append(ExtractedField(
            name=field_name, value=value, confidence=confidence,
            source_file=source_file, document_type=doc_type, bbox=bbox,
            low_confidence=low, llm_derived=llm_derived,
        ))

    return DocumentExtraction(source_file=source_file, document_type=doc_type, fields=fields), llm_log


def _synthetic_document(doc_type: DocumentType, defaults: dict) -> DocumentExtraction:
    values = defaults.get(doc_type.value, {})
    fields = [
        ExtractedField(
            name=name, value=(str(v) if v is not None else None), confidence=0.3,
            source_file=f"<synthetic:{doc_type.value}>", document_type=doc_type,
            bbox=None, low_confidence=True, llm_derived=False,
        )
        for name, v in values.items()
    ]
    return DocumentExtraction(
        source_file=f"<synthetic:{doc_type.value}>", document_type=doc_type,
        synthetic=True, fields=fields,
    )


def run_agent_b(state: dict[str, Any], run_dir: str | Path | None = None) -> dict[str, Any]:
    settings = get_settings()
    policy = load_policy(state.get("jurisdiction"))
    cutoff = float(policy.get("low_confidence_cutoff", 0.75))
    ocr_ceiling = float(policy.get("ocr_field_confidence_ceiling", 0.70))
    use_llm = settings.use_llm
    run_id = state.get("run_id", "run")

    # Resolve document paths and their classified types (from Agent A's context).
    _is_bundle, doc_paths, _manifest = _resolve_inputs(state["input_path"])
    path_by_name = {p.name: p for p in doc_paths}
    classified = state.get("context_packet", {}).get("documents", [])

    documents: list[DocumentExtraction] = []
    llm_log: list[dict] = []
    present_types: set[DocumentType] = set()

    for entry in classified:
        name = entry["source_file"]
        dtype = DocumentType(entry["document_type"])
        path = path_by_name.get(name)
        if path is None or not path.exists():
            continue
        parsed = route_document(path).document
        doc_ext, log = _extract_one_document(name, parsed, dtype, cutoff, ocr_ceiling, use_llm)
        documents.append(doc_ext)
        llm_log.extend(log)
        present_types.add(dtype)

    # Synthetic fallback for missing expected documents (bundles only).
    if state.get("is_bundle"):
        defaults = _load_synthetic_defaults()
        for missing in _EXPECTED_BUNDLE_DOCS - present_types:
            if missing == DocumentType.LETTER_OF_CREDIT:
                continue  # never synthesize the L/C itself
            documents.append(_synthetic_document(missing, defaults))

    extracted = ExtractedDocs(run_id=str(run_id), documents=documents)

    low_conf_fields = [f for f in extracted.all_fields() if f.low_confidence]

    if run_dir is not None:
        run_dir = Path(run_dir)
        write_json(run_dir / "extracted_docs.json", extracted)
        # Flat CSV (stable column order)
        rows = [
            {
                "source_file": f.source_file, "document_type": f.document_type,
                "field": f.name, "value": f.value, "confidence": f.confidence,
                "low_confidence": f.low_confidence, "llm_derived": f.llm_derived,
            }
            for f in extracted.all_fields()
        ]
        write_csv(
            run_dir / "extracted_docs.csv",
            ["source_file", "document_type", "field", "value", "confidence", "low_confidence", "llm_derived"],
            rows,
        )

    return {
        "extracted_docs": extracted.model_dump(mode="json"),
        "trace": [{
            "agent": "agent_b_extraction",
            "documents": len(documents),
            "fields": len(extracted.all_fields()),
            "low_confidence_fields": len(low_conf_fields),
            "llm_fallbacks": len(llm_log),
            "use_llm": use_llm,
        }],
    }