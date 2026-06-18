# Intelligent Trade Finance

Multi-agent documentary-credit examination and settlement-routing pipeline.

A deterministic, rule-based core (UCP 600 checks, cross-document matching, sanctions
screening) orchestrated with LangGraph, with an optional, gated LLM layer for
low-confidence field recovery. Streamlit dashboard for the demo.

## Status

Day 1 — repository scaffolding. Source modules land over the following days per the
team delivery plan.

## Setup (once dependencies land)

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

See `.env.example` for configuration. The default run is rules-only, offline, and
deterministic; set `USE_LLM=true` with a key to enable the optional LLM layer.
