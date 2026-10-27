"""Presentation components for the Handoff Guardian Streamlit UI.

Each helper renders escaped HTML using the Apple-inspired ``hg-*`` classes defined in
``src/ui/theme.py``. Every value from the backend or user is passed through :func:`esc`
before inclusion in markup.
"""

from __future__ import annotations

import html
from collections.abc import Mapping, Sequence
from typing import Any

import streamlit as st

from src.ui.view_model import describe_diagnostic

# ---------- primitives ----------

_ICON_PATHS: dict[str, str] = {
    "shield": '<path d="M12 3l7 3v5c0 4.5-3 8.3-7 10-4-1.7-7-5.5-7-10V6l7-3z"/><path d="M9 12l2 2 4-4"/>',
    "extract": '<path d="M4 6h16M4 12h10M4 18h7"/><circle cx="18" cy="16" r="3"/><path d="M20.2 18.2L22 20"/>',
    "evidence": '<ellipse cx="12" cy="5.5" rx="7" ry="2.5"/><path d="M5 5.5v6c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5v-6"/><path d="M5 11.5v6c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5v-6"/>',
    "evaluate": '<path d="M12 3v18"/><path d="M5 7h14"/><path d="M5 7l-3 6a3 3 0 006 0L5 7z"/><path d="M19 7l-3 6a3 3 0 006 0l-3-6z"/>',
    "report": '<path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5"/><path d="M10 13h6M10 17h6"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "alert": '<path d="M12 4l9 16H3z"/><path d="M12 10v4M12 17.5v.01"/>',
    "x": '<path d="M6 6l12 12M18 6L6 18"/>',
    "minus": '<path d="M6 12h12"/>',
    "clock": '<circle cx="12" cy="12" r="8"/><path d="M12 8v4l3 2"/>',
    "help": '<circle cx="12" cy="12" r="8"/><path d="M9.8 9.5a2.3 2.3 0 114 1.6c-.8.6-1.8 1.1-1.8 2.4M12 16.5v.01"/>',
}

_STATUS_ICON = {
    "completed": "check",
    "warning": "alert",
    "failed": "x",
    "not_run": "minus",
    "unknown": "help",
    "idle": "clock",
}


def esc(value: Any) -> str:
    """Escape any value for safe inclusion in HTML."""
    if value is None:
        return ""
    return html.escape(str(value), quote=True).replace("$", "&#36;")


def icon(name: str, stroke: str = "currentColor") -> str:
    path = _ICON_PATHS.get(name, _ICON_PATHS["help"])
    return (
        f'<svg viewBox="0 0 24 24" fill="none" stroke="{stroke}" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{path}</svg>'
    )


def chip(text: Any, tone: str = "", *, dot: bool = True, mono: bool = False, title: str | None = None) -> str:
    classes = " ".join(c for c in ("hg-chip", tone, "mono" if mono else "") if c)
    title_attr = f' title="{esc(title)}"' if title else ""
    dot_html = '<span class="hg-dot" aria-hidden="true"></span>' if dot else ""
    return f'<span class="{classes}"{title_attr}>{dot_html}{esc(text)}</span>'


def html_block(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def alert_marker(tone: str) -> None:
    """Hidden marker that lets CSS tint the immediately following ``st.alert``."""
    html_block(f'<div class="hg-mark hg-mark-{esc(tone)}"></div>')


def section(eyebrow: str, title: str, sub: str | None = None) -> None:
    sub_html = f'<p class="hg-sub">{esc(sub)}</p>' if sub else ""
    html_block(
        f'<div class="hg-section"><p class="hg-eyebrow">{esc(eyebrow)}</p>'
        f"<h2>{esc(title)}</h2>{sub_html}</div>"
    )


def empty_state(title: str, text: str) -> None:
    html_block(f'<div class="hg-solid hg-empty"><b>{esc(title)}</b><p>{esc(text)}</p></div>')


# ---------- shell ----------

def topbar(page_subtitle: str) -> None:
    chips = "".join(
        [
            chip("Evidence-Backed", "accent"),
            chip("Fail-Closed", "accent"),
        ]
    )
    html_block(
        '<header class="hg-glass hg-topbar hg-anim">'
        f'<div class="hg-logo">{icon("shield", "#ffffff")}</div>'
        '<div class="hg-brand"><h1>Handoff Guardian <span class="hg-ai">AI</span></h1>'
        f"<p>{esc(page_subtitle)}</p></div>"
        f'<div class="hg-chips">{chips}</div></header>'
    )


def sidebar_brand() -> None:
    html_block(
        '<div class="hg-sbrand">'
        f'<div class="hg-logo">{icon("shield", "#ffffff")}</div>'
        "<div><b>Handoff Guardian</b><span>Sales-to-Support Risk Auditor</span></div></div>"
    )


def sidebar_status(rows: Sequence[tuple[str, str, str]]) -> None:
    """Render runtime status rows."""
    body = "".join(
        f'<div class="hg-side-row"><span>{esc(label)}</span>{chip(value, tone)}</div>'
        for label, value, tone in rows
    )
    html_block(
        f'<div class="hg-glass hg-side-card"><p class="hg-eyebrow">Status</p>{body}</div>'
    )


def intro_card() -> None:
    steps = "".join(
        f'<span class="hg-step"><b>{i}</b>{esc(name)}</span>'
        for i, name in enumerate(("Extract", "Collect", "Evaluate", "Report"), start=1)
    )
    html_block(
        '<div class="hg-glass hg-intro hg-anim d1">'
        '<div class="hg-intro-text"><h2>Investigate Handoff</h2>'
        "<p>Audit sales-to-support commitments against verified account records.</p></div>"
        f'<div class="hg-steps">{steps}</div></div>'
    )


# ---------- results ----------

def _fmt(value: Any, fallback: str = "—") -> str:
    return esc(value) if value not in (None, "") else f'<span style="color:var(--text-faint)">{esc(fallback)}</span>'


def hero(facts: Mapping[str, Any]) -> None:
    disposition = str(facts.get("disposition"))
    is_clear = disposition == "CLEAR"
    tone = "ok" if is_clear else "bad"
    explain = (
        "Verified: All requirements satisfied with conflict-free evidence."
        if is_clear
        else "Manual review required: Discrepancies or missing mandatory evidence detected."
    )

    why: list[str] = []
    if not facts.get("has_evaluation"):
        why.append(chip("Evaluation Incomplete", "bad"))
    if facts.get("blocking_count"):
        n = facts["blocking_count"]
        why.append(chip(f"{n} Blocking Finding{'s' if n != 1 else ''}", "bad"))
    if facts.get("missing_mandatory"):
        n = len(facts["missing_mandatory"])
        why.append(chip(f"{n} Missing Mandatory", "warn"))
    if facts.get("conflicts"):
        n = len(facts["conflicts"])
        why.append(chip(f"{n} Conflict{'s' if n != 1 else ''}", "warn"))
    for name in facts.get("failed_stages") or []:
        why.append(chip(f"{name} Failed", "bad"))
    why_html = f'<div class="hg-why">{"".join(why)}</div>' if why and not is_clear else ""

    score = facts.get("risk_score")
    if score is None:
        ring = '<div class="hg-ring na"><div class="hg-ring-inner"><b>—</b><small>Risk</small></div></div>'
    else:
        pct = max(0, min(100, float(score)))
        ring = (
            f'<div class="hg-ring" style="--p:{pct:.0f}" role="img" aria-label="Risk score {esc(score)} of 100">'
            f'<div class="hg-ring-inner"><b>{esc(score)}</b><small>/ 100</small></div></div>'
        )

    cv = facts.get("citations_verified")
    citations = chip("Verified", "ok") if cv is True else chip("Unverified", "warn") if cv is False else _fmt(None)

    fact_items = [
        ("Account", _fmt(facts.get("account_id"))),
        ("Handoff", _fmt(facts.get("handoff_id"))),
        ("Risk Level", _fmt(facts.get("risk_level"))),
        ("Citations", citations),
        ("Policy", _fmt(facts.get("policy_version"))),
        ("Timestamp", _fmt(facts.get("evaluated_at"))),
    ]
    facts_html = "".join(f'<div class="hg-fact"><span>{esc(k)}</span><b>{v}</b></div>' for k, v in fact_items)

    html_block(
        f'<section class="hg-glass hg-hero hg-anim" data-tone="{tone}" aria-label="Investigation disposition">'
        '<div class="hg-hero-main"><p class="hg-hero-label">Outcome</p>'
        f'<div class="hg-disposition"><span class="hg-glyph">{icon("check" if is_clear else "alert")}</span>'
        f'<span class="hg-word">{esc(disposition)}</span></div>'
        f'<p class="hg-explain">{esc(explain)}</p>{why_html}</div>'
        f'<div class="hg-hero-side">{ring}<div class="hg-facts">{facts_html}</div></div></section>'
    )


def pipeline(states: Sequence[Mapping[str, Any]]) -> None:
    parts: list[str] = []
    for i, s in enumerate(states):
        if i:
            check = '<span class="hg-check" title="Claim validation checkpoint"></span>' if i == 2 else ""
            parts.append(f'<div class="hg-link" aria-hidden="true">{check}</div>')

        attempts = s.get("attempts")
        attempt_txt = f" · {attempts} run{'s' if attempts != 1 else ''}" if isinstance(attempts, int) else ""
        outputs = "".join(f"<li>{esc(o)}</li>" for o in s.get("outputs") or [])
        outputs_html = f'<ul class="hg-outputs">{outputs}</ul>' if outputs else ""

        diags = s.get("diagnostics") or []
        details = ""
        if diags:
            items = "".join(
                f'<div class="hg-diag"><code>{esc(d.get("error"))}</code>'
                + (f' <code>{esc(d.get("exception_type"))}</code>' if d.get("exception_type") else "")
                + f"<p>{esc(describe_diagnostic(d))}</p></div>"
                for d in diags
            )
            details = f"<details><summary>{len(diags)} diagnostic{'s' if len(diags) != 1 else ''}</summary>{items}</details>"

        parts.append(
            f'<article class="hg-glass hg-stage hg-anim d{min(i + 1, 4)}" data-status="{esc(s.get("status"))}" '
            f'aria-label="{esc(s.get("name"))}: {esc(s.get("label"))}">'
            f'<div class="hg-stage-head"><div class="hg-stage-icon">{icon(str(s.get("icon")))}</div>'
            f'<div class="hg-stage-title"><span>Stage {esc(s.get("index"))}</span><b>{esc(s.get("name"))}</b></div></div>'
            f'<p class="hg-role">{esc(s.get("role"))}</p>'
            f'<span class="hg-status">{icon(_STATUS_ICON.get(str(s.get("status")), "help"))}{esc(s.get("label"))}{esc(attempt_txt)}</span>'
            f"{outputs_html}{details}</article>"
        )

    legend = "".join(
        [
            chip("Completed", "ok"),
            chip("Warning", "warn"),
            chip("Failed", "bad"),
            chip("Pending", ""),
        ]
    )
    html_block(
        f'<div class="hg-pipeline" role="list">{"".join(parts)}</div>'
        f'<div class="hg-legend">{legend}</div>'
    )


def claims_table(claims: Sequence[Any]) -> None:
    rows: list[str] = []
    for c in claims:
        if not isinstance(c, Mapping):
            continue
        status = c.get("validation_status")
        tone = "ok" if status == "validated" else "warn" if status == "unvalidated" else ""
        status_html = chip(str(status).capitalize() if status else "Unknown", tone)
        eids = c.get("evidence_ids") or []
        eid_html = " ".join(chip(e, "accent", dot=False, mono=True) for e in eids) or '<span class="hg-mono">—</span>'
        rows.append(
            f'<tr><td class="hg-mono">{esc(c.get("claim_id"))}</td><td>{esc(c.get("category"))}</td>'
            f'<td class="hg-mono">{esc(c.get("key"))}</td><td>{esc(c.get("value"))}</td>'
            f"<td>{status_html}</td><td>{eid_html}</td></tr>"
        )
    html_block(
        '<div class="hg-table-wrap"><table class="hg-table"><thead><tr>'
        "<th>ID</th><th>Category</th><th>Key</th><th>Claimed Value</th><th>Status</th><th>Linked Evidence</th>"
        f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
    )


def evidence_grid(evidence: Sequence[Any], citations: Mapping[str, Sequence[str]]) -> None:
    cards: list[str] = []
    for e in evidence:
        if not isinstance(e, Mapping):
            continue
        eid = str(e.get("evidence_id", ""))
        cited_by = citations.get(eid) or []
        cited = chip("Cited", "ok", title=", ".join(cited_by)) if cited_by else ""
        excerpt = f"<blockquote>{esc(e.get('excerpt'))}</blockquote>" if e.get("excerpt") else ""
        cards.append(
            '<div class="hg-solid hg-ev">'
            f'<div class="hg-ev-head">{chip(e.get("source") or "Source", "accent")}'
            f'<span>{cited} {chip(eid, "", dot=False, mono=True)}</span></div>'
            f'<p class="hg-ev-field">{esc(e.get("field"))}</p>'
            f'<p class="hg-ev-value">{_fmt(e.get("value"), "No value")}</p>{excerpt}'
            f'<div class="hg-ev-foot"><span>Account {esc(e.get("account_id"))}</span>'
            f'<span>{_fmt(e.get("updated_at"), "unknown")}</span></div></div>'
        )
    html_block(f'<div class="hg-ev-grid">{"".join(cards)}</div>')


def findings_list(findings: Sequence[Any]) -> None:
    ordered = sorted(
        (f for f in findings if isinstance(f, Mapping)),
        key=lambda f: (not f.get("blocking", False), str(f.get("rule_id", ""))),
    )
    items: list[str] = []
    for f in ordered:
        blocking = bool(f.get("blocking"))
        head = [
            f"<b>{esc(f.get('reason_code') or 'UNSPECIFIED')}</b>",
            chip("Blocking", "bad") if blocking else chip("Advisory", ""),
        ]
        if f.get("severity"):
            head.append(chip(f"{f.get('severity')}", "warn" if blocking else ""))
        if f.get("rule_id"):
            head.append(chip(f.get("rule_id"), "", dot=False, mono=True))
        eids = " ".join(chip(e, "accent", dot=False, mono=True) for e in (f.get("evidence_ids") or []))
        eid_html = f'<div class="hg-finding-head">{eids}</div>' if eids else ""
        items.append(
            f'<div class="hg-solid hg-finding{" blocking" if blocking else ""}">'
            f'<div class="hg-finding-head">{"".join(head)}</div>'
            f"<p>{esc(f.get('description'))}</p>{eid_html}</div>"
        )
    html_block("".join(items))


def text_list(title: str, values: Sequence[Any]) -> None:
    lis = "".join(f"<li>{esc(v)}</li>" for v in values)
    html_block(
        f'<div class="hg-solid" style="margin-top:10px"><div style="padding:10px 14px 0">'
        f'<p class="hg-eyebrow">{esc(title)}</p></div><ul class="hg-list">{lis}</ul></div>'
    )


def diagnostics_table(diagnostics: Sequence[Any]) -> None:
    rows = "".join(
        f'<tr><td class="hg-mono">{esc(d.get("component"))}</td><td class="hg-mono">{esc(d.get("error"))}</td>'
        f'<td class="hg-mono">{esc(d.get("exception_type") or "—")}</td><td>{esc(describe_diagnostic(d))}</td></tr>'
        for d in diagnostics
        if isinstance(d, Mapping)
    )
    html_block(
        '<div class="hg-table-wrap"><table class="hg-table"><thead><tr>'
        "<th>Component</th><th>Code</th><th>Type</th><th>Description</th>"
        f"</tr></thead><tbody>{rows}</tbody></table></div>"
    )


# ---------- about ----------

def about_stages(stages: Sequence[Mapping[str, Any]]) -> None:
    cards = "".join(
        f'<div class="hg-glass hg-about-card hg-anim d{min(i, 4)}">'
        f'<div class="hg-stage-head"><div class="hg-stage-icon">{icon(str(s["icon"]))}</div>'
        f'<div class="hg-stage-title"><span>Stage {i}</span><b>{esc(s["name"])}</b></div></div>'
        f'<p>{esc(s["role"])}</p></div>'
        for i, s in enumerate(stages, start=1)
    )
    html_block(f'<div class="hg-about-grid">{cards}</div>')


def integration_table(rows: Sequence[tuple[str, str, str, str]]) -> None:
    """Render integration overview rows."""
    body = "".join(
        f"<tr><td><b>{esc(name)}</b></td><td>{chip(status, tone)}</td><td>{esc(detail)}</td></tr>"
        for name, status, tone, detail in rows
    )
    html_block(
        '<div class="hg-table-wrap"><table class="hg-table"><thead><tr>'
        "<th>Service</th><th>Status</th><th>Notes</th>"
        f"</tr></thead><tbody>{body}</tbody></table></div>"
    )
