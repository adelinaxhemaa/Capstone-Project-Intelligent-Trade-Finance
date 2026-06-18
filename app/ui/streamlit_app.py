from __future__ import annotations

import io
import sys
import tempfile
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.config import get_settings
from app.pipeline import run_pipeline

st.set_page_config(
    page_title="Intelligent Trade Finance",
    page_icon="\u25c8",
    layout="wide",
    initial_sidebar_state="expanded",
)

INK = "#10243e"
INK_SOFT = "#1c3a5e"
PARCHMENT = "#f4efe4"
PARCHMENT_DEEP = "#e9e1cd"
BRASS = "#b08338"
BRASS_BRIGHT = "#d4a24c"
SEAL = "#8c2f1f"
VERDIGRIS = "#2f6f5e"
SLATE = "#5c6b7a"
LINE = "#d8cdb4"

DECISION = {
    "honour": {"label": "HONOUR", "color": VERDIGRIS, "blurb": "Documents comply. Credit cleared for settlement."},
    "refuse": {"label": "REFUSE", "color": SEAL, "blurb": "Discrepancies bar payment under UCP 600 Art. 16."},
    "escalate": {"label": "ESCALATE", "color": BRASS, "blurb": "Material findings require senior compliance review."},
    "manual_review": {"label": "MANUAL REVIEW", "color": INK_SOFT, "blurb": "Low-confidence extraction routed for human checking."},
}

SEVERITY = {
    "critical": SEAL,
    "major": "#b8542f",
    "minor": BRASS,
    "info": SLATE,
}

SEVERITY_ORDER = ["critical", "major", "minor", "info"]

st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,900&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

    .stApp {{ background:
        radial-gradient(circle at 12% 8%, #f8f4ea 0%, {PARCHMENT} 38%, {PARCHMENT_DEEP} 100%);
        background-attachment: fixed;
    }}
    [data-testid="stAppViewContainer"], [data-testid="stMain"] {{ background: transparent; }}
    [data-testid="stHeader"] {{ background: transparent; }}
    .block-container {{ padding-top: 2.2rem; max-width: 1400px; }}

    h1, h2, h3, h4 {{ font-family: 'Fraunces', Georgia, serif !important; color: {INK}; letter-spacing: -0.01em; }}
    p, span, div, label, .stMarkdown {{ font-family: 'Inter', system-ui, sans-serif; }}

    .tf-mast {{
        border-bottom: 3px double {INK};
        padding-bottom: 0.7rem; margin-bottom: 0.3rem;
        display: flex; align-items: baseline; justify-content: space-between;
    }}
    .tf-mast .title {{ font-family:'Fraunces'; font-weight:900; font-size:2.5rem; color:{INK}; line-height:1; }}
    .tf-mast .sub {{ font-family:'IBM Plex Mono'; font-size:0.72rem; letter-spacing:0.22em;
        text-transform:uppercase; color:{BRASS}; }}
    .tf-eyebrow {{ font-family:'IBM Plex Mono'; font-size:0.68rem; letter-spacing:0.28em;
        text-transform:uppercase; color:{SLATE}; margin: 1.4rem 0 0.4rem 0; }}

    .tf-stamp {{
        border: 3px solid; border-radius: 10px; padding: 1.1rem 1.4rem;
        display:flex; flex-direction:column; gap:0.25rem; position:relative;
        background: rgba(255,255,255,0.35);
    }}
    .tf-stamp .verdict {{ font-family:'Fraunces'; font-weight:900; font-size:2rem; line-height:1; }}
    .tf-stamp .blurb {{ font-family:'Inter'; font-size:0.9rem; color:{INK}; opacity:0.85; }}
    .tf-stamp .route {{ font-family:'IBM Plex Mono'; font-size:0.68rem; letter-spacing:0.12em;
        text-transform:uppercase; color:{SLATE}; }}

    .tf-kpi {{
        border:1px solid {LINE}; border-left:4px solid {BRASS}; border-radius:6px;
        padding:0.85rem 1rem; background:rgba(255,255,255,0.45); height:100%;
    }}
    .tf-kpi .v {{ font-family:'Fraunces'; font-weight:900; font-size:1.9rem; color:{INK}; line-height:1; }}
    .tf-kpi .k {{ font-family:'IBM Plex Mono'; font-size:0.62rem; letter-spacing:0.18em;
        text-transform:uppercase; color:{SLATE}; margin-top:0.35rem; }}

    .tf-card {{ border:1px solid {LINE}; border-radius:8px; background:rgba(255,255,255,0.5);
        padding:1.1rem 1.25rem; }}

    section[data-testid="stSidebar"] {{ background: {INK}; }}
    section[data-testid="stSidebar"] * {{ color:{PARCHMENT} !important; }}
    section[data-testid="stSidebar"] .tf-side-title {{
        font-family:'Fraunces'; font-weight:900; font-size:1.3rem; color:{BRASS_BRIGHT} !important; }}
    section[data-testid="stSidebar"] .tf-side-line {{ font-family:'IBM Plex Mono'; font-size:0.72rem;
        letter-spacing:0.06em; color:{PARCHMENT} !important; opacity:0.85; }}

    .stButton button {{
        background:{INK}; color:{PARCHMENT}; border:none; border-radius:6px;
        font-family:'IBM Plex Mono'; letter-spacing:0.12em; text-transform:uppercase;
        font-size:0.72rem; padding:0.6rem 1.2rem;
    }}
    .stButton button:hover {{ background:{BRASS}; color:{INK}; }}

    .stDownloadButton button {{
        background:transparent; color:{INK}; border:1px solid {LINE}; border-radius:6px;
        font-family:'IBM Plex Mono'; font-size:0.7rem; text-align:left;
    }}
    .stDownloadButton button:hover {{ border-color:{BRASS}; color:{SEAL}; }}

    .stTabs [data-baseweb="tab-list"] {{ gap:0.3rem; border-bottom:1px solid {LINE}; }}
    .stTabs [data-baseweb="tab"] {{ font-family:'IBM Plex Mono'; font-size:0.72rem;
        letter-spacing:0.1em; text-transform:uppercase; color:{SLATE}; }}
    .stTabs [aria-selected="true"] {{ color:{INK}; border-bottom:2px solid {BRASS}; }}

    .tf-pill {{ display:inline-block; font-family:'IBM Plex Mono'; font-size:0.62rem;
        letter-spacing:0.1em; text-transform:uppercase; padding:0.12rem 0.5rem;
        border-radius:20px; color:#fff; }}
    .tf-evidence {{ font-family:'IBM Plex Mono'; font-size:0.74rem; color:{SLATE}; }}
    </style>
    """,
    unsafe_allow_html=True,
)


def _find_bundle_root(extracted: Path) -> Path:
    if (extracted / "manifest.yaml").exists():
        return extracted
    for sub in extracted.iterdir():
        if sub.is_dir() and (sub / "manifest.yaml").exists():
            return sub
    pdfs = list(extracted.rglob("*.pdf"))
    return pdfs[0].parent if pdfs else extracted


def _sample_bundles() -> list[Path]:
    base = ROOT / "tests" / "bundles"
    if not base.exists():
        return []
    out = []
    for p in sorted(base.iterdir()):
        if p.is_dir() and (p / "manifest.yaml").exists():
            out.append(p)
    return out


def _pretty(name: str) -> str:
    return name.replace("bundle_", "").replace("_", " ").title()


def masthead() -> None:
    st.markdown(
        """
        <div class="tf-mast">
          <div>
            <div class="title">Intelligent Trade Finance</div>
          </div>
          <div class="sub">Documentary Credit Examination Desk</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<p style='font-family:Inter;color:{SLATE};margin-top:0.4rem;max-width:60ch;'>"
        "A six-agent pipeline reads a presentation, checks it against UCP 600, reconciles "
        "every document against the others, screens all parties for sanctions, and reaches "
        "a settlement decision \u2014 with each conclusion traced to the page it came from.</p>",
        unsafe_allow_html=True,
    )


def kpi(col, value, label) -> None:
    col.markdown(
        f"<div class='tf-kpi'><div class='v'>{value}</div><div class='k'>{label}</div></div>",
        unsafe_allow_html=True,
    )


def decision_stamp(decision: dict, route: str | None) -> None:
    action = decision.get("action", "unknown")
    meta = DECISION.get(action, {"label": action.upper(), "color": SLATE, "blurb": ""})
    route_line = ""
    if route and route != "continue":
        route_line = f"<div class='route'>Routed via \u00b7 {route}</div>"
    st.markdown(
        f"""
        <div class="tf-stamp" style="border-color:{meta['color']};">
          <div class="verdict" style="color:{meta['color']};">{meta['label']}</div>
          <div class="blurb">{decision.get('rationale', meta['blurb'])}</div>
          {route_line}
        </div>
        """,
        unsafe_allow_html=True,
    )


def severity_bar(findings: list[dict]) -> go.Figure:
    counts = {s: 0 for s in SEVERITY_ORDER}
    for f in findings:
        sev = f.get("severity", "info")
        counts[sev] = counts.get(sev, 0) + 1
    labels = [s.title() for s in SEVERITY_ORDER]
    values = [counts[s] for s in SEVERITY_ORDER]
    colors = [SEVERITY[s] for s in SEVERITY_ORDER]
    fig = go.Figure(go.Bar(x=values, y=labels, orientation="h", marker_color=colors,
                           text=values, textposition="outside"))
    fig.update_layout(
        height=210, margin=dict(l=10, r=20, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter", color=INK, size=12),
        xaxis=dict(showgrid=True, gridcolor=LINE, dtick=1),
        yaxis=dict(autorange="reversed"),
    )
    return fig


def confidence_strip(docs: list[dict]) -> go.Figure:
    rows = []
    for d in docs:
        for fld in d.get("fields", []):
            rows.append({
                "doc": d.get("document_type", "?").replace("_", " "),
                "field": fld.get("name", "?"),
                "confidence": fld.get("confidence", 0.0),
            })
    if not rows:
        return go.Figure()
    df = pd.DataFrame(rows)
    means = df.groupby("doc")["confidence"].mean().sort_values()
    colors = [SEAL if v < 0.75 else (BRASS if v < 0.9 else VERDIGRIS) for v in means.values]
    fig = go.Figure(go.Bar(
        x=means.values, y=[m.title() for m in means.index], orientation="h",
        marker_color=colors, text=[f"{v:.0%}" for v in means.values], textposition="outside",
    ))
    fig.update_layout(
        height=240, margin=dict(l=10, r=30, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter", color=INK, size=12),
        xaxis=dict(range=[0, 1.08], tickformat=".0%", showgrid=True, gridcolor=LINE),
    )
    return fig


def stage_timeline(trace: list[dict]) -> go.Figure:
    names = {
        "agent_a_intake": "A \u00b7 Intake",
        "agent_b_extraction": "B \u00b7 Extraction",
        "agent_c_ucp": "C \u00b7 UCP 600",
        "agent_d_matching": "D \u00b7 Matching",
        "agent_e_sanctions": "E \u00b7 Sanctions",
        "agent_h_orchestrator": "H \u00b7 Decision",
    }
    labels, values, colors = [], [], []
    for step in trace:
        agent = step.get("agent", "")
        f = step.get("findings", step.get("hits", 0)) or 0
        labels.append(names.get(agent, agent))
        values.append(f)
        colors.append(SEAL if f else INK_SOFT)
    fig = go.Figure(go.Bar(x=labels, y=values, marker_color=colors,
                           text=values, textposition="outside"))
    fig.update_layout(
        height=240, margin=dict(l=10, r=10, t=20, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter", color=INK, size=11),
        yaxis=dict(title="findings", showgrid=True, gridcolor=LINE, dtick=1),
    )
    return fig


def portfolio_chart(rows: list[dict]) -> go.Figure:
    order = ["honour", "manual_review", "escalate", "refuse"]
    counts = {k: 0 for k in order}
    for r in rows:
        counts[r["action"]] = counts.get(r["action"], 0) + 1
    fig = go.Figure(go.Bar(
        x=[DECISION[k]["label"] for k in order],
        y=[counts[k] for k in order],
        marker_color=[DECISION[k]["color"] for k in order],
        text=[counts[k] for k in order], textposition="outside",
    ))
    fig.update_layout(
        height=260, margin=dict(l=10, r=10, t=20, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter", color=INK, size=12),
        yaxis=dict(showgrid=True, gridcolor=LINE, dtick=1),
    )
    return fig


def render_findings(findings: list[dict]) -> None:
    if not findings:
        st.markdown(
            f"<div class='tf-card' style='border-left:4px solid {VERDIGRIS};'>"
            f"<b style='color:{VERDIGRIS};'>Clean presentation.</b> No discrepancies were raised "
            "across UCP 600, cross-document matching, or sanctions screening.</div>",
            unsafe_allow_html=True,
        )
        return
    ranked = sorted(findings, key=lambda f: SEVERITY_ORDER.index(f.get("severity", "info"))
                    if f.get("severity") in SEVERITY_ORDER else 99)
    for f in ranked:
        sev = f.get("severity", "info")
        color = SEVERITY.get(sev, SLATE)
        ev_lines = ""
        for e in f.get("evidence", []):
            loc = e.get("source_file", "")
            fld = e.get("field_name")
            page = (e.get("bbox") or {}).get("page")
            bits = [b for b in [loc, fld, (f"p{page}" if page is not None else None)] if b]
            ev_lines += f"<div class='tf-evidence'>\u21b3 {' \u00b7 '.join(str(b) for b in bits)}</div>"
        rec = f.get("recommendation")
        rec_html = f"<div style='margin-top:0.4rem;color:{INK};font-size:0.85rem;'><b>Recommendation:</b> {rec}</div>" if rec else ""
        st.markdown(
            f"""
            <div class="tf-card" style="border-left:4px solid {color}; margin-bottom:0.6rem;">
              <span class="tf-pill" style="background:{color};">{sev}</span>
              <span style="font-family:'Fraunces';font-weight:600;font-size:1.05rem;color:{INK};margin-left:0.5rem;">{f.get('title','')}</span>
              <div style="color:{SLATE};font-size:0.9rem;margin-top:0.35rem;">{f.get('description','')}</div>
              {rec_html}
              {ev_lines}
            </div>
            """,
            unsafe_allow_html=True,
        )


def docs_table(docs: list[dict]) -> None:
    for d in docs:
        synth = " \u00b7 synthetic fallback" if d.get("synthetic") else ""
        with st.expander(f"{d.get('document_type','?').replace('_',' ').title()}  \u2014  {d.get('source_file','')}{synth}"):
            rows = []
            for fld in d.get("fields", []):
                rows.append({
                    "field": fld.get("name"),
                    "value": fld.get("value"),
                    "confidence": f"{fld.get('confidence', 0):.0%}",
                    "page": (fld.get("bbox") or {}).get("page", "\u2014"),
                    "source": "LLM" if fld.get("llm_derived") else "pattern",
                })
            if rows:
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            else:
                st.caption("No fields extracted.")


def ucp_table(ucp: dict) -> None:
    checks = ucp.get("checks", [])
    if not checks:
        st.caption("No UCP checks recorded.")
        return
    rows = [{
        "rule": c.get("rule_id"),
        "article": c.get("article"),
        "check": c.get("description"),
        "result": "pass" if c.get("passed") else "FAIL",
        "detail": c.get("detail") or "",
    } for c in checks]
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
    passed = sum(1 for c in checks if c.get("passed"))
    st.caption(f"{passed}/{len(checks)} checks passed.")


def match_table(match: dict) -> None:
    comps = match.get("comparisons", [])
    if not comps:
        st.caption("No cross-document comparisons recorded.")
        return
    rows = []
    for c in comps:
        vals = c.get("values", {}) or {}
        rows.append({
            "field": c.get("field_name"),
            "type": c.get("match_type"),
            "matched": "yes" if c.get("matched") else "NO",
            "score": c.get("score") if c.get("score") is not None else "\u2014",
            "values": "  vs  ".join(str(v) for v in vals.values()),
            "detail": c.get("detail") or "",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def sanctions_view(screen: dict) -> None:
    hits = screen.get("hits", [])
    screened = screen.get("entities_screened", screen.get("screened", []))
    c1, c2 = st.columns(2)
    c1.markdown(f"<div class='tf-kpi'><div class='v'>{len(screened) if isinstance(screened, list) else screened}</div>"
                "<div class='k'>Entities screened</div></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='tf-kpi' style='border-left-color:{SEAL if hits else VERDIGRIS};'>"
                f"<div class='v' style='color:{SEAL if hits else VERDIGRIS};'>{len(hits)}</div>"
                "<div class='k'>Sanctions hits</div></div>", unsafe_allow_html=True)
    st.write("")
    if hits:
        rows = [{
            "subject": h.get("name", h.get("subject", "")),
            "matched": h.get("matched_name", h.get("list_entry", "")),
            "list": h.get("list", h.get("program", "")),
            "score": h.get("score", ""),
        } for h in hits]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.markdown(f"<div class='tf-card' style='border-left:4px solid {VERDIGRIS};'>"
                    f"<b style='color:{VERDIGRIS};'>Screening clear.</b> No party, vessel, or jurisdiction "
                    "matched a sanctions or PEP entry.</div>", unsafe_allow_html=True)


def artifacts(run_dir: Path) -> None:
    files = sorted(p for p in run_dir.rglob("*") if p.is_file())
    cols = st.columns(3)
    for i, fp in enumerate(files):
        rel = fp.relative_to(run_dir)
        cols[i % 3].download_button(
            label=str(rel), data=fp.read_bytes(), file_name=fp.name, key=f"dl_{rel}"
        )


def run_examination(target: str) -> None:
    state = run_pipeline(target)
    st.session_state["state"] = state
    rows = st.session_state.get("portfolio", {})
    dec = state.get("final_decision", {})
    rows[Path(target).name] = {
        "bundle": _pretty(Path(target).name),
        "action": dec.get("action", "unknown"),
        "findings": len(dec.get("findings", [])),
        "throughput": dec.get("metrics", {}).get("throughput") or 0,
    }
    st.session_state["portfolio"] = rows


def results_panel() -> None:
    state = st.session_state.get("state")
    if not state:
        st.markdown(
            f"<div class='tf-card' style='text-align:center;padding:2.5rem;color:{SLATE};'>"
            "Select a presentation and run the examination to see the decision, findings, "
            "and evidence here.</div>", unsafe_allow_html=True)
        return

    decision = state.get("final_decision", {})
    metrics = decision.get("metrics", {})
    findings = decision.get("findings", state.get("findings", []))

    st.markdown("<div class='tf-eyebrow'>Examination Result</div>", unsafe_allow_html=True)
    left, right = st.columns([1.1, 1])
    with left:
        decision_stamp(decision, state.get("route"))
    with right:
        a, b = st.columns(2)
        kpi(a, metrics.get("documents_processed", 0), "Documents")
        kpi(b, metrics.get("fields_extracted", 0), "Fields extracted")
        c, d = st.columns(2)
        kpi(c, metrics.get("discrepancy_count", 0), "Discrepancies")
        kpi(d, metrics.get("sanctions_hit_count", 0), "Sanctions hits")

    e, f, g = st.columns(3)
    tp = metrics.get("throughput") or metrics.get("throughput_docs_per_sec")
    kpi(e, f"{tp:.1f}" if tp else "\u2014", "Docs / second")
    kpi(f, f"{metrics.get('discrepancy_rate', 0):.2f}" if metrics.get("discrepancy_rate") is not None else "\u2014", "Discrepancy rate")
    kpi(g, metrics.get("low_confidence_count", 0), "Low-confidence fields")

    tabs = st.tabs(["Findings", "Pipeline", "Documents", "UCP 600", "Matching", "Sanctions", "Artifacts"])

    with tabs[0]:
        cc1, cc2 = st.columns([1, 1])
        with cc1:
            st.markdown("<div class='tf-eyebrow'>Severity profile</div>", unsafe_allow_html=True)
            st.plotly_chart(severity_bar(findings), use_container_width=True)
        with cc2:
            st.markdown("<div class='tf-eyebrow'>Extraction confidence by document</div>", unsafe_allow_html=True)
            st.plotly_chart(confidence_strip(state.get("extracted_docs", {}).get("documents", [])),
                            use_container_width=True)
        st.markdown("<div class='tf-eyebrow'>Discrepancies</div>", unsafe_allow_html=True)
        render_findings(findings)

    with tabs[1]:
        st.markdown("<div class='tf-eyebrow'>Findings raised at each stage</div>", unsafe_allow_html=True)
        st.plotly_chart(stage_timeline(state.get("trace", [])), use_container_width=True)
        st.dataframe(pd.DataFrame(state.get("trace", [])), use_container_width=True, hide_index=True)

    with tabs[2]:
        docs_table(state.get("extracted_docs", {}).get("documents", []))

    with tabs[3]:
        ucp_table(state.get("ucp_result", {}))

    with tabs[4]:
        match_table(state.get("match_result", {}))

    with tabs[5]:
        sanctions_view(state.get("sanctions_screen", {}))

    with tabs[6]:
        artifacts(Path(state["run_dir"]))
        report = Path(state["run_dir"]) / "reports" / "run_report.md"
        if report.exists():
            with st.expander("Run report", expanded=False):
                st.markdown(report.read_text(encoding="utf-8"))


def portfolio_panel() -> None:
    rows = list(st.session_state.get("portfolio", {}).values())
    if not rows:
        return
    st.markdown("<div class='tf-eyebrow'>Session Portfolio</div>", unsafe_allow_html=True)
    c1, c2 = st.columns([1, 1.4])
    with c1:
        st.plotly_chart(portfolio_chart(rows), use_container_width=True)
    with c2:
        df = pd.DataFrame(rows)[["bundle", "action", "findings", "throughput"]]
        df["action"] = df["action"].map(lambda a: DECISION.get(a, {}).get("label", a))
        df["throughput"] = df["throughput"].map(lambda v: f"{v:.1f}" if v else "\u2014")
        st.dataframe(df, use_container_width=True, hide_index=True)


def main() -> None:
    settings = get_settings()
    if "portfolio" not in st.session_state:
        st.session_state["portfolio"] = {}

    with st.sidebar:
        st.markdown("<div class='tf-side-title'>Examination Desk</div>", unsafe_allow_html=True)
        st.markdown("<div class='tf-side-line'>Deterministic \u00b7 rule-based core</div>", unsafe_allow_html=True)
        st.write("")
        st.markdown(f"<div class='tf-side-line'>LLM assist &nbsp;&nbsp; <b>{'ON' if settings.use_llm else 'OFF'}</b></div>", unsafe_allow_html=True)
        st.markdown(f"<div class='tf-side-line'>OCR engine &nbsp;&nbsp; <b>{settings.ocr_engine}</b></div>", unsafe_allow_html=True)
        st.write("")
        st.markdown("<div class='tf-side-line' style='opacity:0.7;'>UCP 600 verdicts, sanctions decisions, "
                    "and the settlement call are always rule-based. The LLM only assists extraction "
                    "and narration when enabled.</div>", unsafe_allow_html=True)
        st.markdown("<hr style='border-color:#27496d;'>", unsafe_allow_html=True)

        st.markdown("<div class='tf-side-line' style='letter-spacing:0.2em;'>SELECT PRESENTATION</div>", unsafe_allow_html=True)
        samples = _sample_bundles()
        source = st.radio("Source", ["Sample bundle", "Upload"], label_visibility="collapsed")
        target = None
        if source == "Sample bundle":
            if samples:
                choice = st.selectbox("Bundle", samples, format_func=lambda p: _pretty(p.name))
                target = str(choice)
            else:
                st.warning("No bundles. Run: python samples/make_sample_bundle.py")
        else:
            up = st.file_uploader("Trade bundle (.zip) or single L/C (.pdf)", type=["zip", "pdf"])
            if up is not None:
                tmp = Path(tempfile.mkdtemp())
                if up.name.lower().endswith(".zip"):
                    ex = tmp / "bundle"
                    ex.mkdir()
                    with zipfile.ZipFile(io.BytesIO(up.getvalue())) as zf:
                        zf.extractall(ex)
                    target = str(_find_bundle_root(ex))
                else:
                    fp = tmp / up.name
                    fp.write_bytes(up.getvalue())
                    target = str(fp)
                st.caption(f"Loaded: {Path(target).name}")
        st.write("")
        run_clicked = st.button("Examine documents", disabled=target is None, use_container_width=True)

    masthead()
    if run_clicked and target:
        with st.spinner("Examining presentation\u2026"):
            run_examination(target)
    results_panel()
    portfolio_panel()


main()
