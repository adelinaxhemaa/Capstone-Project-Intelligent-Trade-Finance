# Intelligent Trade Finance

A deterministic, multi-agent pipeline that automates documentary-credit examination and
settlement routing. It ingests a Trade Bundle (or a single Letter of Credit), extracts
structured fields from born-digital or scanned PDFs, validates UCP 600 compliance, reconciles
every document against the others, screens all parties for sanctions, and reaches a settlement
decision — with every conclusion traced back to the page it came from.

The examination core is **100% rule-based and reproducible**: identical inputs always produce
identical decisions. An optional LLM layer can assist extraction and narration when enabled, but
it never decides a verdict.

---

## What it does

```
Intake → Extraction → UCP 600 → Cross-Doc Matching → Sanctions → Triage & Decision
  A          B           C            D                  E              H
```

Two conditional routes implement intelligent handling: a low-confidence extraction diverts
through manual review, and an active sanctions hit diverts through a freeze branch before the
decision.

| Agent | Responsibility |
|-------|----------------|
| **A — Intake & Context** | Classifies documents, validates the manifest, builds the context packet and evidence index, applies risk heuristics. |
| **B — Field Extraction** | Born-digital text via PyMuPDF; scanned pages routed to OCR; confidence scoring, bounding boxes, synthetic fallback, low-confidence flags. |
| **C — UCP 600 Compliance** | Presentation period, expiry, partial shipment, transhipment, mandatory fields. |
| **D — Cross-Document Matching** | Descriptions, quantities, amounts, dates, and named parties across all documents (fuzzy + tolerance checks). |
| **E — Sanctions Screening** | Parties, vessels, and countries against OFAC / EU / UN lists, plus PEP and country-risk checks. |
| **H — Triage & Orchestration** | Merges, deduplicates and ranks findings, reaches the decision, drafts the SWIFT message, finalizes the audit log. |

**Decisions:** `HONOUR`, `REFUSE`, `ESCALATE`, `MANUAL_REVIEW`.

### Run artifacts (written to `runs/<run_id>/`)

`extracted_docs.json` (+ `.csv`), `ucp_result.json`, `match_result.json`,
`sanctions_screen.json`, `discrepancies.md`, `swift_draft.txt`, `final_decision.json`,
`audit_log.md`, `metrics.json`, `posting_payload.json`, `run_metadata.json`, plus a
human-readable `reports/run_report.md`.

---

## Quick start

You need **Python 3.10+**.

```bash
# 1. (recommended) virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. install dependencies
pip install -r requirements.txt

# 3. run the one-command demo (uses the bundled sample data)
python demo.py

# 4. launch the dashboard
streamlit run app/ui/streamlit_app.py
#   → open http://localhost:8501
```

The sample bundles under `tests/bundles/` are included, so the demo and the UI work
immediately after install. To regenerate them (or create additional scenarios):

```bash
python samples/make_sample_bundle.py
```

### OCR (optional, for scanned documents)

Born-digital PDFs need nothing extra. To exercise the scanned-document path you need the
Tesseract binary installed at the OS level:

- macOS: `brew install tesseract`
- Ubuntu/Debian: `sudo apt-get install tesseract-ocr`
- Windows: install the Tesseract installer and add it to PATH (or set `TESSERACT_CMD` in `.env`).

If Tesseract is not installed, the pipeline degrades gracefully: scanned fields are marked
low-confidence and routed to manual review rather than crashing.

### LLM assist (optional)

The system runs fully offline with no API key. To enable the optional extraction/narration
assist:

```bash
cp .env.example .env          # set USE_LLM=true and your provider key
pip install -r requirements-llm.txt
```

UCP verdicts, sanctions decisions, and the final settlement call remain rule-based regardless.

---

## Using the dashboard

The Streamlit app is the primary surface. From the sidebar you:

1. Pick a sample bundle, or upload your own `.zip` Trade Bundle or single `.pdf` L/C.
2. Click **Examine documents**.

You then get the decision stamp and rationale, headline metrics, and tabbed detail:

- **Findings** — severity profile, per-document extraction confidence, and each discrepancy with its evidence pointer.
- **Pipeline** — findings raised at each agent stage plus the full execution trace.
- **Documents** — every extracted field with value, confidence, page, and source.
- **UCP 600** — the rule-by-rule compliance audit.
- **Matching** — cross-document field comparisons.
- **Sanctions** — screening summary and any hits.
- **Artifacts** — download every run artifact, plus the rendered run report.

A session portfolio chart accumulates the decisions from every bundle you examine.

---

## Commands

```bash
python demo.py                              # deterministic end-to-end demo
streamlit run app/ui/streamlit_app.py       # dashboard
pytest                                      # test suite
python samples/make_sample_bundle.py        # (re)generate sample bundles
python -m app.pipeline tests/bundles/bundle_01_clean   # run one bundle from the CLI
```

If you have `make`:

```bash
make install      make demo      make test      make ui      make clean
```

---

## Configurability

All thresholds live in `config/policy_pack.yaml` (with optional `config/regional/` overrides
merged on top). Changing a value re-routes a decision with no code edit — for example, raising
`amount_tolerance_pct` lets an over-tolerance invoice pass. `demo.py` demonstrates this live: it
runs an over-tolerance bundle (ESCALATE), raises the tolerance in config, and re-runs the same
bundle (HONOUR).

---

## Project layout

```
app/
  pipeline.py            LangGraph StateGraph: A→B→C→D→E→H + routing
  state.py               shared pipeline state
  config.py              environment/runtime settings
  schemas/               Pydantic contracts between agents
  agents/                one module per pipeline stage
  parsing/               pdf_parser, ocr_parser, quality_scorer, extraction_router, classifier
  tools/                 calculator, fuzzy match, evidence, policy loader
  rules/                 ucp600, matching_rules, sanctions_lists (pure logic)
  llm/                   optional LangChain touchpoints (gated by USE_LLM)
  audit/                 tracer, audit logger, decision logger
  reports/               Jinja2 templates + report builder
  data/                  sample sanctions lists + synthetic fallback values
  ui/streamlit_app.py    the dashboard
config/                  policy_pack.yaml + regional overrides
samples/                 sample-bundle generator
tests/                   pytest suite + scenario bundles
runs/                    generated per-run artifacts
demo.py                  one-command demo
```

---

## Test scenarios

| Bundle | Scenario | Expected |
|--------|----------|----------|
| `bundle_01_clean` | All documents compliant | HONOUR |
| `bundle_02_bl_expiry` | Bill of lading after L/C expiry | ESCALATE |
| `bundle_03_amount_tolerance` | Invoice over L/C amount beyond tolerance | ESCALATE |
| `bundle_06_sanctions_hit` | Sanctioned party match | REFUSE (freeze route) |
| `bundle_08_low_ocr` | Low-confidence scanned field | MANUAL_REVIEW |
| `lc_only` | Single L/C document (no bundle to cross-check) | ESCALATE |

Run `pytest` to verify all scenarios, the extraction router, the tools, and a
deterministic-rerun assertion.
