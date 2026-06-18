"""Agent E — Sanctions Screening.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.rules import sanctions_lists
from app.schemas.common import DocumentType, RiskLevel, Severity
from app.schemas.findings import EvidencePointer, Finding, FindingType
from app.schemas.sanctions import (
    EntityType,
    ListSource,
    SanctionsHit,
    SanctionsScreen,
    ScreenedEntity,
)
from app.tools.policy_loader import load_policy
from app.utils.ids import finding_id
from app.utils.io import write_json


def _field(extracted: dict[str, Any], doc_type: str, field_name: str) -> str | None:
    for doc in extracted.get("documents", []):
        if doc["document_type"] != doc_type:
            continue
        for f in doc["fields"]:
            if f["name"] == field_name and f.get("confidence", 0) > 0 and f.get("value"):
                return f["value"]
    return None


def _collect_entities(extracted: dict[str, Any], context: dict[str, Any]) -> list[ScreenedEntity]:
    seen: set[str] = set()
    entities: list[ScreenedEntity] = []

    def add(name: str | None, etype: EntityType):
        if name and name.strip() and name.strip().lower() not in seen:
            seen.add(name.strip().lower())
            entities.append(ScreenedEntity(name=name.strip(), entity_type=etype))

    for p in context.get("parties", []):
        add(p.get("name"), EntityType.PARTY)
    add(_field(extracted, "commercial_invoice", "seller"), EntityType.PARTY)
    add(_field(extracted, "commercial_invoice", "buyer"), EntityType.PARTY)
    add(_field(extracted, "bill_of_lading", "shipper"), EntityType.PARTY)
    add(_field(extracted, "bill_of_lading", "consignee"), EntityType.PARTY)
    add(_field(extracted, "certificate_of_origin", "exporter"), EntityType.PARTY)
    add(_field(extracted, "certificate_of_origin", "country_of_origin"), EntityType.COUNTRY)
    return entities


def run_agent_e(state: dict[str, Any], run_dir: str | Path | None = None) -> dict[str, Any]:
    extracted = state.get("extracted_docs", {})
    context = state.get("context_packet", {})
    policy = load_policy(state.get("jurisdiction"))
    run_id = state.get("run_id", "run")
    threshold = float(policy.get("sanctions", {}).get("match_threshold", 90))

    entities = _collect_entities(extracted, context)
    hits: list[SanctionsHit] = []
    findings: list[Finding] = []
    country_risk: dict[str, RiskLevel] = {}

    for ent in entities:
        # 1. Sanctions list screening (parties only)
        if ent.entity_type == EntityType.PARTY:
            for h in sanctions_lists.screen_name(ent.name, threshold):
                hit = SanctionsHit(
                    entity=ent, list_source=ListSource(h["source"]),
                    matched_name=h["matched_name"], score=h["score"],
                    detail=f"'{ent.name}' ~ '{h['matched_name']}' ({h['source']})",
                    recommendation="Freeze and escalate to compliance.",
                )
                fid = finding_id(FindingType.SANCTIONS_HIT.value, ent.name, h["matched_name"])
                hit.finding_id = fid
                hits.append(hit)
                findings.append(Finding(
                    id=fid, type=FindingType.SANCTIONS_HIT, severity=Severity.CRITICAL,
                    title="Sanctions list match", description=hit.detail,
                    source_agent="agent_e_sanctions",
                    evidence=[EvidencePointer(source_file=ent.name, document_type=DocumentType.UNKNOWN)],
                    recommendation="Freeze the transaction and escalate.",
                ))

            # adverse media (sample)
            for entry in sanctions_lists.adverse_media_hits(ent.name, threshold):
                findings.append(Finding(
                    id=finding_id("adverse_media", ent.name, entry),
                    type=FindingType.OTHER, severity=Severity.MAJOR,
                    title="Adverse media match (sample)",
                    description=f"'{ent.name}' matches adverse-media sample entry '{entry}'.",
                    source_agent="agent_e_sanctions",
                    evidence=[EvidencePointer(source_file=ent.name, document_type=DocumentType.UNKNOWN)],
                    recommendation="Enhanced due diligence.",
                ))

        # 2. Country risk
        if ent.entity_type == EntityType.COUNTRY:
            tier = sanctions_lists.country_risk_tier(ent.name, policy)
            if tier:
                country_risk[ent.name] = RiskLevel(tier)
                if tier == "high":
                    findings.append(Finding(
                        id=finding_id("country_risk", ent.name, tier),
                        type=FindingType.OTHER, severity=Severity.MAJOR,
                        title="High-risk country", description=f"Country '{ent.name}' is high-risk.",
                        source_agent="agent_e_sanctions",
                        evidence=[EvidencePointer(source_file=ent.name, document_type=DocumentType.CERTIFICATE_OF_ORIGIN)],
                        recommendation="Apply enhanced due diligence / check embargo status.",
                    ))

    # 3. Dual-use goods controls (scan goods descriptions)
    for dt in ("letter_of_credit", "commercial_invoice", "bill_of_lading"):
        goods = _field(extracted, dt, "goods_description")
        terms = sanctions_lists.dual_use_terms(goods or "", policy)
        if terms:
            findings.append(Finding(
                id=finding_id("dual_use", dt, ",".join(terms)),
                type=FindingType.OTHER, severity=Severity.MAJOR,
                title="Possible dual-use goods",
                description=f"Goods description in {dt} contains dual-use terms: {', '.join(terms)}.",
                source_agent="agent_e_sanctions",
                evidence=[EvidencePointer(source_file="goods_description", document_type=DocumentType(dt))],
                recommendation="Verify export-control licensing.",
            ))
            break

    screen = SanctionsScreen(
        run_id=str(run_id), screened=entities, hits=hits,
        country_risk=country_risk, findings=findings,
    )

    if run_dir is not None:
        write_json(Path(run_dir) / "sanctions_screen.json", screen)

    return {
        "sanctions_screen": screen.model_dump(mode="json"),
        "findings": [f.model_dump(mode="json") for f in findings],
        "trace": [{
            "agent": "agent_e_sanctions",
            "entities_screened": len(entities),
            "hits": len(hits),
            "active_hit": screen.has_active_hit,
            "findings": len(findings),
        }],
    }
