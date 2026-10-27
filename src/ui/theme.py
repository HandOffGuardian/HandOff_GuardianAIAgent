"""Glassmorphism design system for the Handoff Guardian Streamlit UI.

Presentation only. Injects Apple-inspired liquid glass design tokens (CSS custom properties)
for the selected appearance (Obsidian Dark or Crisp Light) and a single stylesheet for
Streamlit widgets and the ``hg-*`` component classes rendered by ``src/ui/components.py``.
"""

from __future__ import annotations

import streamlit as st

TOKENS: dict[str, dict[str, str]] = {
    "Dark": {
        "bg": "#000000",
        "bg-2": "#060608",
        "ambient-1": "rgba(255, 255, 255, 0.025)",
        "ambient-2": "rgba(10, 132, 255, 0.05)",
        "ambient-3": "rgba(94, 92, 230, 0.04)",
        "grid": "rgba(255, 255, 255, 0.015)",
        "text": "#F5F5F7",
        "text-muted": "#8E8E93",
        "text-faint": "#48484A",
        "glass": "rgba(18, 18, 22, 0.72)",
        "glass-strong": "rgba(12, 12, 15, 0.88)",
        "glass-fallback": "#0A0A0C",
        "surface": "#0E0E12",
        "surface-2": "#141418",
        "border": "rgba(255, 255, 255, 0.10)",
        "border-strong": "rgba(255, 255, 255, 0.18)",
        "highlight": "rgba(255, 255, 255, 0.16)",
        "shadow": "0 20px 48px rgba(0,0,0,0.75)",
        "input-bg": "#121216",
        "accent": "#0A84FF",
        "accent-2": "#5E5CE6",
        "accent-soft": "rgba(10, 132, 255, 0.16)",
        "on-accent": "#FFFFFF",
        "ok": "#30D158",
        "ok-soft": "rgba(48, 209, 88, 0.15)",
        "warn": "#FF9F0A",
        "warn-soft": "rgba(255, 159, 10, 0.15)",
        "bad": "#FF453A",
        "bad-soft": "rgba(255, 69, 58, 0.15)",
        "neutral": "#8E8E93",
        "neutral-soft": "rgba(142, 142, 147, 0.14)",
    },
    "Light": {
        "bg": "#F5F5F7",
        "bg-2": "#EBEBF0",
        "ambient-1": "rgba(10, 132, 255, 0.08)",
        "ambient-2": "rgba(94, 92, 230, 0.06)",
        "ambient-3": "rgba(0, 0, 0, 0.02)",
        "grid": "rgba(0, 0, 0, 0.02)",
        "text": "#1D1D1F",
        "text-muted": "#6E6E73",
        "text-faint": "#86868B",
        "glass": "rgba(255, 255, 255, 0.75)",
        "glass-strong": "rgba(255, 255, 255, 0.90)",
        "glass-fallback": "#FFFFFF",
        "surface": "#FFFFFF",
        "surface-2": "#F5F5F7",
        "border": "rgba(0, 0, 0, 0.09)",
        "border-strong": "rgba(0, 0, 0, 0.16)",
        "highlight": "rgba(255, 255, 255, 0.90)",
        "shadow": "0 18px 40px rgba(0, 0, 0, 0.08)",
        "input-bg": "#FFFFFF",
        "accent": "#0071E3",
        "accent-2": "#5E5CE6",
        "accent-soft": "rgba(0, 113, 227, 0.10)",
        "on-accent": "#FFFFFF",
        "ok": "#34C759",
        "ok-soft": "rgba(52, 199, 89, 0.12)",
        "warn": "#FF9500",
        "warn-soft": "rgba(255, 149, 0, 0.12)",
        "bad": "#FF3B30",
        "bad-soft": "rgba(255, 59, 48, 0.12)",
        "neutral": "#8E8E93",
        "neutral-soft": "rgba(142, 142, 147, 0.12)",
    },
}

_STYLESHEET = r"""
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

/* ---------- Foundation ---------- */
.stApp, .stApp p, .stApp li, .stApp label, .stApp input, .stApp textarea, .stApp button,
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6, .stApp td, .stApp th,
.stApp [data-testid="stMarkdownContainer"] {
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Inter', system-ui, sans-serif;
  -webkit-font-smoothing: antialiased;
}
.stApp code, .hg-mono { font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Consolas, monospace; }

.stApp {
  color: var(--text);
  background:
    radial-gradient(1000px 520px at 10% -10%, var(--ambient-1), transparent 60%),
    radial-gradient(800px 480px at 100% 0%, var(--ambient-2), transparent 55%),
    radial-gradient(800px 580px at 50% 115%, var(--ambient-3), transparent 60%),
    linear-gradient(var(--grid) 1px, transparent 1px) 0 0 / 48px 48px,
    linear-gradient(90deg, var(--grid) 1px, transparent 1px) 0 0 / 48px 48px,
    linear-gradient(180deg, var(--bg) 0%, var(--bg-2) 100%);
  background-attachment: fixed;
}
.stApp p, .stApp li, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
.stApp td, .stApp th, .stApp span { color: var(--text); }
.stApp [data-testid="stCaptionContainer"], .stApp [data-testid="stCaptionContainer"] p { color: var(--text-muted); }
.stApp a { color: var(--accent); }
.stApp ::selection { background: var(--accent-soft); }

/* Remove top gap from Streamlit default header */
[data-testid="stHeader"] {
  height: 0 !important;
  min-height: 0 !important;
  padding: 0 !important;
  background: transparent !important;
  display: none !important;
}
[data-testid="stDecoration"] { display: none !important; }
[data-testid="stToolbar"] { top: 10px !important; right: 16px !important; z-index: 999; }
[data-testid="stAppViewBlockContainer"] {
  padding-top: 1rem !important;
  padding-bottom: 3.5rem !important;
  max-width: 1300px;
}

/* ---------- Apple Glass Sidebar & Symmetrical Header ---------- */
[data-testid="stSidebar"] {
  background: var(--glass-strong) !important;
  -webkit-backdrop-filter: blur(32px) saturate(200%);
  backdrop-filter: blur(32px) saturate(200%);
  border-right: 1px solid var(--border) !important;
  box-shadow: 2px 0 24px rgba(0, 0, 0, 0.4);
}
[data-testid="stSidebar"] > div:first-child {
  background: transparent !important;
  padding-top: 0 !important;
}
[data-testid="stSidebarHeader"] {
  height: 48px !important;
  min-height: 48px !important;
  padding: 8px 14px !important;
  display: flex !important;
  align-items: center !important;
  justify-content: flex-end !important;
  background: transparent !important;
}
[data-testid="stSidebarCollapseButton"] {
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
}
[data-testid="stSidebarCollapseButton"] button {
  background: rgba(255, 255, 255, 0.06) !important;
  border: 1px solid var(--border) !important;
  border-radius: 10px !important;
  color: var(--text-muted) !important;
  width: 32px !important;
  height: 32px !important;
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
}
[data-testid="stSidebarCollapseButton"] button:hover {
  background: rgba(255, 255, 255, 0.12) !important;
  color: var(--text) !important;
  border-color: var(--border-strong) !important;
  transform: scale(1.04);
}
[data-testid="stSidebarCollapseButton"] svg {
  fill: currentColor !important;
  stroke: currentColor !important;
  width: 16px !important;
  height: 16px !important;
}
[data-testid="stSidebarUserContent"] {
  padding-top: 0 !important;
  padding-left: 1rem !important;
  padding-right: 1rem !important;
}
[data-testid="stSidebar"] hr { border-color: var(--border); margin: 0.85rem 0; }
[data-testid="stSidebar"] [role="radiogroup"] { gap: 4px; }
[data-testid="stSidebar"] [role="radiogroup"] label {
  width: 100%; padding: 8px 12px; border-radius: 10px; border: 1px solid transparent;
  transition: background .2s ease, border-color .2s ease;
}
[data-testid="stSidebar"] [role="radiogroup"] label:hover { background: var(--accent-soft); }
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
  background: var(--accent-soft); border-color: var(--border-strong);
}
[data-testid="stSidebar"] [role="radiogroup"] label p { font-weight: 600; }

/* ---------- Widgets & Input Fix (Never Turns White) ---------- */
[data-testid="stWidgetLabel"] p { color: var(--text-muted) !important; font-weight: 600; font-size: .82rem; letter-spacing: .01em; }

.stApp [data-baseweb="input"],
.stApp [data-baseweb="base-input"],
.stApp [data-baseweb="textarea"],
.stApp [data-baseweb="select"] > div {
  background-color: var(--input-bg) !important;
  border: 1px solid var(--border-strong) !important;
  border-radius: 12px !important;
  transition: border-color .2s ease, box-shadow .2s ease, background-color .2s ease;
}

.stApp [data-baseweb="input"] input,
.stApp [data-baseweb="base-input"] input,
.stApp [data-baseweb="textarea"] textarea,
.stApp input[type="text"],
.stApp textarea {
  color: var(--text) !important;
  -webkit-text-fill-color: var(--text) !important;
  background-color: var(--input-bg) !important;
  caret-color: var(--accent) !important;
}

.stApp [data-baseweb="input"]:focus,
.stApp [data-baseweb="input"]:focus-within,
.stApp [data-baseweb="base-input"]:focus,
.stApp [data-baseweb="base-input"]:focus-within,
.stApp [data-baseweb="textarea"]:focus-within,
.stApp [data-baseweb="select"] > div:focus-within {
  background-color: var(--input-bg) !important;
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 3px var(--accent-soft) !important;
}

/* Chrome/Safari Autofill protection: enforce dark background */
.stApp input:-webkit-autofill,
.stApp input:-webkit-autofill:hover, 
.stApp input:-webkit-autofill:focus, 
.stApp input:-webkit-autofill:active,
.stApp textarea:-webkit-autofill,
.stApp textarea:-webkit-autofill:hover,
.stApp textarea:-webkit-autofill:focus {
  -webkit-box-shadow: 0 0 0 1000px var(--input-bg) inset !important;
  box-shadow: 0 0 0 1000px var(--input-bg) inset !important;
  -webkit-text-fill-color: var(--text) !important;
  caret-color: var(--text) !important;
  transition: background-color 5000s ease-in-out 0s;
}

.stApp input::placeholder, .stApp textarea::placeholder { color: var(--text-faint) !important; -webkit-text-fill-color: var(--text-faint) !important; }
.stApp [data-baseweb="select"] div, .stApp [data-baseweb="select"] svg { color: var(--text) !important; fill: var(--text-muted); }
div[data-baseweb="popover"] ul, div[data-baseweb="popover"] li { background: var(--surface) !important; color: var(--text) !important; }
div[data-baseweb="popover"] li:hover { background: var(--accent-soft) !important; }
[data-testid="InputInstructions"] { display: none !important; }

/* Strong Apple Glass Form Container */
[data-testid="stForm"] {
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.02) 100%), var(--glass);
  -webkit-backdrop-filter: blur(30px) saturate(200%);
  backdrop-filter: blur(30px) saturate(200%);
  border: 1px solid var(--border) !important;
  border-radius: 20px;
  padding: 1.5rem 1.6rem 1.3rem;
  box-shadow: var(--shadow), inset 0 1px 0 var(--highlight), inset 0 0 0 1px rgba(255, 255, 255, 0.04);
}

/* Apple System Action Button */
[data-testid="stFormSubmitButton"] button {
  background: linear-gradient(135deg, #0A84FF 0%, #0066CC 100%) !important;
  color: #FFFFFF !important;
  border: 0 !important;
  border-radius: 12px !important;
  min-height: 46px;
  font-weight: 600 !important;
  letter-spacing: .01em;
  box-shadow: 0 8px 24px rgba(10, 132, 255, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.25);
  transition: transform .15s ease, box-shadow .2s ease, filter .2s ease;
}
[data-testid="stFormSubmitButton"] button p { color: #FFFFFF !important; font-weight: 600; font-size: .95rem; }
[data-testid="stFormSubmitButton"] button:hover {
  transform: translateY(-1px);
  filter: brightness(1.08);
  box-shadow: 0 12px 28px rgba(10, 132, 255, 0.45), inset 0 1px 0 rgba(255, 255, 255, 0.35);
}
[data-testid="stFormSubmitButton"] button:active { transform: translateY(0); }

.stApp button:focus-visible, .stApp summary:focus-visible, .stApp [role="tab"]:focus-visible {
  outline: 2px solid var(--accent) !important; outline-offset: 3px;
}
[data-testid="stDownloadButton"] button {
  background: var(--glass) !important; border: 1px solid var(--border-strong) !important;
  border-radius: 10px !important; color: var(--text) !important; transition: border-color .2s, background .2s;
}
[data-testid="stDownloadButton"] button:hover { border-color: var(--accent) !important; background: var(--accent-soft) !important; }

/* Alerts: Opaque readable cards */
[data-testid="stAlert"] > div {
  background: var(--surface) !important; border: 1px solid var(--border-strong) !important;
  border-left-width: 4px !important; border-radius: 14px !important; color: var(--text) !important;
}
[data-testid="stAlert"] p { color: var(--text) !important; font-weight: 500; }
.element-container:has(.hg-mark) { display: none; }
.element-container:has(.hg-mark-bad) + .element-container [data-testid="stAlert"] > div { border-color: var(--bad) !important; background: linear-gradient(90deg, var(--bad-soft), transparent 70%), var(--surface) !important; }
.element-container:has(.hg-mark-ok) + .element-container [data-testid="stAlert"] > div { border-color: var(--ok) !important; background: linear-gradient(90deg, var(--ok-soft), transparent 70%), var(--surface) !important; }
.element-container:has(.hg-mark-warn) + .element-container [data-testid="stAlert"] > div { border-color: var(--warn) !important; background: linear-gradient(90deg, var(--warn-soft), transparent 70%), var(--surface) !important; }

/* Apple-style Glass Tabs */
.stTabs [data-baseweb="tab-list"] {
  gap: 6px; padding: 5px; border-radius: 14px; background: var(--glass);
  border: 1px solid var(--border);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  backdrop-filter: blur(24px) saturate(180%);
  overflow-x: auto;
}
.stTabs [data-baseweb="tab"] {
  height: 36px; padding: 0 14px; border-radius: 10px; background: transparent;
  transition: background .2s ease, color .2s ease;
}
.stTabs [data-baseweb="tab"] p { color: var(--text-muted); font-weight: 600; font-size: .85rem; }
.stTabs [data-baseweb="tab"]:hover p { color: var(--text); }
.stTabs [aria-selected="true"] { background: var(--accent-soft) !important; box-shadow: inset 0 0 0 1px var(--border-strong); }
.stTabs [aria-selected="true"] p { color: var(--text); }
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display: none; }
.stTabs [data-baseweb="tab-panel"] { padding-top: 1rem; }
[data-testid="stJson"] { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 10px; }

/* ---------- Apple Glass Components ---------- */
.hg-glass {
  position: relative;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.02) 100%), var(--glass);
  -webkit-backdrop-filter: blur(30px) saturate(200%);
  backdrop-filter: blur(30px) saturate(200%);
  border: 1px solid var(--border);
  border-radius: 20px;
  box-shadow: var(--shadow), inset 0 1px 0 var(--highlight), inset 0 0 0 1px rgba(255, 255, 255, 0.04);
}
.hg-solid { background: var(--surface); border: 1px solid var(--border); border-radius: 16px; }

/* Compact Apple-style top menu bar */
.hg-topbar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 18px;
  margin-top: 0 !important;
  margin-bottom: 16px !important;
  flex-wrap: wrap;
}
.hg-logo {
  width: 42px; height: 42px; border-radius: 12px; flex: none; display: grid; place-items: center;
  background: linear-gradient(140deg, #0A84FF 0%, #5E5CE6 100%);
  box-shadow: 0 8px 20px rgba(10, 132, 255, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.4);
}
.hg-logo svg { width: 22px; height: 22px; }
.hg-brand { flex: 1 1 240px; min-width: 0; }
.hg-brand h1 { margin: 0 !important; padding: 0 !important; font-size: 1.35rem !important; font-weight: 700 !important; letter-spacing: -.02em; line-height: 1.2 !important; }
.hg-brand h1 .hg-ai { background: linear-gradient(90deg, var(--accent), var(--accent-2)); -webkit-background-clip: text; background-clip: text; color: transparent; }
.hg-brand p { margin: 1px 0 0 !important; color: var(--text-muted) !important; font-size: .84rem; }
.hg-chips { display: flex; gap: 8px; flex-wrap: wrap; }

.hg-chip {
  display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 999px;
  font-size: .74rem; font-weight: 600; line-height: 1.3; white-space: nowrap;
  border: 1px solid var(--border-strong); background: var(--neutral-soft); color: var(--text) !important;
}
.hg-chip .hg-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--neutral); flex: none; }
.hg-chip.ok { background: var(--ok-soft); border-color: color-mix(in srgb, var(--ok) 40%, transparent); }
.hg-chip.ok .hg-dot { background: var(--ok); }
.hg-chip.warn { background: var(--warn-soft); border-color: color-mix(in srgb, var(--warn) 40%, transparent); }
.hg-chip.warn .hg-dot { background: var(--warn); }
.hg-chip.bad { background: var(--bad-soft); border-color: color-mix(in srgb, var(--bad) 40%, transparent); }
.hg-chip.bad .hg-dot { background: var(--bad); }
.hg-chip.accent { background: var(--accent-soft); border-color: color-mix(in srgb, var(--accent) 40%, transparent); }
.hg-chip.accent .hg-dot { background: var(--accent); }
.hg-chip.mono { font-family: 'JetBrains Mono', ui-monospace, monospace; font-weight: 500; }

.hg-eyebrow { font-size: .70rem !important; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; color: var(--accent) !important; margin: 0 0 2px !important; }
.hg-section { margin: 24px 0 10px; }
.hg-section h2 { font-size: 1.15rem !important; font-weight: 700 !important; margin: 0 !important; padding: 0 !important; letter-spacing: -.01em; }
.hg-section p.hg-sub { color: var(--text-muted) !important; margin: 3px 0 0 !important; font-size: .86rem; }

/* Streamlined Intro Card */
.hg-intro { padding: 14px 18px; margin-bottom: 14px; display: flex; gap: 16px; align-items: center; justify-content: space-between; flex-wrap: wrap; }
.hg-intro-text { flex: 1 1 300px; }
.hg-intro-text h2 { font-size: 1.15rem !important; margin: 0 0 2px !important; padding: 0 !important; font-weight: 700 !important; }
.hg-intro-text p { margin: 0 !important; color: var(--text-muted) !important; font-size: .86rem; }
.hg-steps { display: flex; gap: 6px; flex-wrap: wrap; }
.hg-step { display: flex; align-items: center; gap: 6px; font-size: .78rem; font-weight: 500; color: var(--text-muted) !important; }
.hg-step b { width: 20px; height: 20px; border-radius: 50%; display: grid; place-items: center; font-size: .70rem; background: var(--accent-soft); color: var(--accent) !important; border: 1px solid var(--border-strong); }

/* Disposition Hero */
.hg-hero { display: grid; grid-template-columns: minmax(260px, 1.1fr) minmax(300px, 1.6fr); gap: 0; overflow: hidden; }
.hg-hero-main { padding: 22px 24px; position: relative; }
.hg-hero-main::before { content: ""; position: absolute; inset: 0; background: radial-gradient(420px 220px at 0% 0%, var(--tone-soft), transparent 70%); pointer-events: none; }
.hg-hero[data-tone="bad"] { --tone: var(--bad); --tone-soft: var(--bad-soft); }
.hg-hero[data-tone="ok"] { --tone: var(--ok); --tone-soft: var(--ok-soft); }
.hg-hero-label { font-size: .72rem !important; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; color: var(--text-muted) !important; margin: 0 !important; }
.hg-disposition { display: flex; align-items: center; gap: 12px; margin: 4px 0 8px; }
.hg-disposition .hg-glyph { width: 38px; height: 38px; border-radius: 12px; display: grid; place-items: center; background: var(--tone-soft); border: 1px solid color-mix(in srgb, var(--tone) 45%, transparent); }
.hg-disposition .hg-glyph svg { width: 20px; height: 20px; stroke: var(--tone); }
.hg-disposition span.hg-word { font-size: 2.1rem; font-weight: 800; letter-spacing: -.02em; color: var(--tone) !important; line-height: 1; }
.hg-hero-main p.hg-explain { margin: 0 !important; color: var(--text-muted) !important; font-size: .88rem; line-height: 1.45; }
.hg-hero-side { padding: 20px 22px; border-left: 1px solid var(--border); display: grid; grid-template-columns: auto 1fr; gap: 20px; align-items: center; background: color-mix(in srgb, var(--surface) 35%, transparent); }
.hg-ring { --p: 0; width: 96px; height: 96px; border-radius: 50%; display: grid; place-items: center;
  background: conic-gradient(var(--ring) calc(var(--p) * 1%), var(--border) 0); }
.hg-ring.na { background: conic-gradient(var(--border) 100%, var(--border) 0); }
.hg-ring-inner { width: 78px; height: 78px; border-radius: 50%; background: var(--surface); display: grid; place-items: center; text-align: center; }
.hg-ring-inner b { display: block; font-size: 1.4rem; font-weight: 800; line-height: 1; color: var(--text) !important; }
.hg-ring-inner small { display: block; font-size: .62rem; color: var(--text-muted) !important; letter-spacing: .06em; text-transform: uppercase; margin-top: 2px; }
.hg-facts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px 16px; }
.hg-fact span { display: block; font-size: .68rem; letter-spacing: .08em; text-transform: uppercase; color: var(--text-faint) !important; font-weight: 600; }
.hg-fact b { display: block; font-size: .88rem; font-weight: 600; color: var(--text) !important; margin-top: 1px; overflow-wrap: anywhere; }
.hg-why { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 12px; }

/* 4-Stage Apple Glass Workflow */
.hg-pipeline { display: flex; align-items: stretch; gap: 0; }
.hg-stage { flex: 1 1 0; min-width: 0; padding: 14px 14px 12px; display: flex; flex-direction: column; gap: 8px; overflow: hidden;
  transition: transform .2s ease, border-color .2s ease, box-shadow .2s ease; }
.hg-stage::before { content: ""; position: absolute; left: 0; right: 0; top: 0; height: 3px; background: var(--st); opacity: .9; }
.hg-stage:hover { transform: translateY(-2px); border-color: var(--border-strong); }
.hg-stage[data-status="completed"] { --st: var(--ok); --st-soft: var(--ok-soft); }
.hg-stage[data-status="warning"] { --st: var(--warn); --st-soft: var(--warn-soft); }
.hg-stage[data-status="failed"] { --st: var(--bad); --st-soft: var(--bad-soft); }
.hg-stage[data-status="not_run"], .hg-stage[data-status="unknown"], .hg-stage[data-status="idle"] { --st: var(--neutral); --st-soft: var(--neutral-soft); }
.hg-stage[data-status="not_run"] .hg-stage-head, .hg-stage[data-status="not_run"] .hg-role { opacity: .7; }
.hg-stage-head { display: flex; align-items: center; gap: 9px; }
.hg-stage-icon { width: 34px; height: 34px; border-radius: 10px; flex: none; display: grid; place-items: center; background: var(--accent-soft); border: 1px solid var(--border-strong); }
.hg-stage-icon svg { width: 18px; height: 18px; stroke: var(--accent); }
.hg-stage-title { min-width: 0; }
.hg-stage-title span { display: block; font-size: .66rem; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: var(--text-faint) !important; }
.hg-stage-title b { display: block; font-size: .94rem; font-weight: 700; color: var(--text) !important; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.hg-role { font-size: .78rem !important; color: var(--text-muted) !important; line-height: 1.4; margin: 0 !important; min-height: 2.8em; }
.hg-status { display: inline-flex; align-items: center; gap: 6px; align-self: flex-start; padding: 3px 9px; border-radius: 999px;
  font-size: .72rem; font-weight: 700; background: var(--st-soft); border: 1px solid color-mix(in srgb, var(--st) 45%, transparent); color: var(--text) !important; }
.hg-status svg { width: 12px; height: 12px; stroke: var(--st); }
.hg-outputs { list-style: none; margin: 0 !important; padding: 0 !important; display: grid; gap: 4px; }
.hg-outputs li { font-size: .78rem; color: var(--text) !important; padding-left: 14px; position: relative; margin: 0 !important; }
.hg-outputs li::before { content: ""; position: absolute; left: 2px; top: .55em; width: 5px; height: 5px; border-radius: 50%; background: var(--st); }
.hg-stage details { margin-top: auto; border-top: 1px solid var(--border); padding-top: 6px; }
.hg-stage summary { cursor: pointer; font-size: .74rem; font-weight: 600; color: var(--text-muted) !important; list-style: none; }
.hg-stage summary::-webkit-details-marker { display: none; }
.hg-stage summary::before { content: "\25B8"; display: inline-block; margin-right: 5px; transition: transform .2s ease; }
.hg-stage details[open] summary::before { transform: rotate(90deg); }
.hg-diag { margin-top: 6px; padding: 6px 8px; border-radius: 8px; background: var(--surface); border: 1px solid var(--border); font-size: .74rem; }
.hg-diag code { font-size: .70rem; color: var(--st) !important; background: transparent; padding: 0; }
.hg-diag p { margin: 2px 0 0 !important; color: var(--text-muted) !important; font-size: .74rem; }
.hg-link { flex: 0 0 32px; display: flex; align-items: center; justify-content: center; position: relative; }
.hg-link::before { content: ""; position: absolute; left: 4px; right: 4px; top: 50%; height: 2px; background: linear-gradient(90deg, var(--border-strong), var(--accent)); opacity: .7; }
.hg-link::after { content: ""; position: absolute; right: 3px; top: calc(50% - 4px); border-left: 7px solid var(--accent); border-top: 5px solid transparent; border-bottom: 5px solid transparent; opacity: .8; }
.hg-link .hg-check { position: relative; z-index: 1; width: 16px; height: 16px; transform: rotate(45deg); border-radius: 3px; background: var(--surface); border: 1px solid var(--accent); }
.hg-legend { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; font-size: .72rem; color: var(--text-faint) !important; align-items: center; }

/* Dense tables & cards */
.hg-table-wrap { overflow-x: auto; border-radius: 14px; border: 1px solid var(--border); background: var(--surface); }
.hg-table { width: 100%; border-collapse: collapse; font-size: .84rem; }
.hg-table th { text-align: left; font-size: .68rem; letter-spacing: .08em; text-transform: uppercase; color: var(--text-faint) !important; font-weight: 700; padding: 10px 12px; background: var(--surface-2); border-bottom: 1px solid var(--border); white-space: nowrap; }
.hg-table td { padding: 10px 12px; border-bottom: 1px solid var(--border); vertical-align: top; color: var(--text) !important; }
.hg-table tr:last-child td { border-bottom: 0; }
.hg-table tr:hover td { background: var(--accent-soft); }
.hg-table .hg-mono { font-size: .76rem; color: var(--text-muted) !important; }

.hg-ev-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 10px; }
.hg-ev { padding: 12px 14px; display: flex; flex-direction: column; gap: 6px; transition: border-color .2s ease, transform .2s ease; }
.hg-ev:hover { border-color: var(--border-strong); transform: translateY(-1px); }
.hg-ev-head { display: flex; justify-content: space-between; align-items: center; gap: 6px; flex-wrap: wrap; }
.hg-ev-field { font-size: .72rem; color: var(--text-faint) !important; text-transform: uppercase; letter-spacing: .07em; font-weight: 700; margin: 0 !important; }
.hg-ev-value { font-size: .92rem; font-weight: 600; color: var(--text) !important; margin: 0 !important; overflow-wrap: anywhere; }
.hg-ev blockquote { margin: 0 !important; padding: 6px 10px !important; border-left: 3px solid var(--accent) !important; background: var(--surface-2); border-radius: 0 8px 8px 0; font-size: .80rem; color: var(--text-muted) !important; line-height: 1.45; }
.hg-ev-foot { display: flex; justify-content: space-between; gap: 6px; flex-wrap: wrap; font-size: .72rem; color: var(--text-faint) !important; }

.hg-finding { padding: 12px 14px; border-left: 4px solid var(--neutral) !important; display: grid; gap: 4px; margin-bottom: 8px; }
.hg-finding.blocking { border-left-color: var(--bad) !important; }
.hg-finding-head { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.hg-finding-head b { font-size: .88rem; color: var(--text) !important; margin-right: 4px; }
.hg-finding p { margin: 0 !important; font-size: .84rem; color: var(--text-muted) !important; line-height: 1.45; }

.hg-list { margin: 0 !important; padding: 10px 14px 10px 28px !important; }
.hg-list li { font-size: .84rem; margin: 3px 0 !important; color: var(--text) !important; }

.hg-empty { padding: 22px; text-align: center; }
.hg-empty b { display: block; font-size: .95rem; color: var(--text) !important; margin-bottom: 2px; }
.hg-empty p { margin: 0 auto !important; color: var(--text-muted) !important; font-size: .84rem; max-width: 55ch; }

.hg-side-card { padding: 10px 12px; margin-top: 4px; display: grid; gap: 6px; }
.hg-side-row { display: flex; justify-content: space-between; align-items: center; gap: 6px; font-size: .76rem; }
.hg-side-row span { color: var(--text-muted) !important; }
.hg-sbrand { display: flex; align-items: center; gap: 10px; margin: 0 0 4px; }
.hg-sbrand .hg-logo { width: 34px; height: 34px; border-radius: 10px; }
.hg-sbrand .hg-logo svg { width: 18px; height: 18px; }
.hg-sbrand b { display: block; font-size: .98rem; font-weight: 700; color: var(--text) !important; letter-spacing: -.01em; }
.hg-sbrand span { display: block; font-size: .72rem; color: var(--text-muted) !important; }

/* Perfectly Symmetrical 2x2 About Agents Grid */
.hg-about-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}
.hg-about-card {
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 120px;
  justify-content: flex-start;
  transition: transform .2s ease, border-color .2s ease;
}
.hg-about-card:hover {
  transform: translateY(-2px);
  border-color: var(--border-strong);
}
.hg-about-card p {
  margin: 0 !important;
  font-size: .85rem;
  color: var(--text-muted) !important;
  line-height: 1.5;
}
@media (max-width: 680px) {
  .hg-about-grid {
    grid-template-columns: 1fr;
  }
}

/* Subtle Apple Motion */
@keyframes hg-rise { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }
.hg-anim { animation: hg-rise .35s cubic-bezier(.16,1,.3,1) both; }
.hg-anim.d1 { animation-delay: .03s; } .hg-anim.d2 { animation-delay: .06s; } .hg-anim.d3 { animation-delay: .09s; } .hg-anim.d4 { animation-delay: .12s; }

@media (prefers-reduced-motion: reduce) {
  .stApp *, .stApp *::before, .stApp *::after { animation: none !important; transition: none !important; }
}

@media (max-width: 980px) {
  .hg-pipeline { flex-direction: column; }
  .hg-link { flex-basis: 24px; }
  .hg-link::before { left: 50%; right: auto; top: 3px; bottom: 3px; width: 2px; height: auto; background: linear-gradient(180deg, var(--border-strong), var(--accent)); }
  .hg-link::after { right: auto; left: calc(50% - 5px); top: auto; bottom: 1px; border-top: 7px solid var(--accent); border-left: 5px solid transparent; border-right: 5px solid transparent; border-bottom: 0; }
  .hg-hero { grid-template-columns: 1fr; }
  .hg-hero-side { border-left: 0; border-top: 1px solid var(--border); }
  .hg-role { min-height: 0; }
}
@media (max-width: 560px) {
  .hg-hero-side { grid-template-columns: 1fr; justify-items: start; }
  .hg-facts { grid-template-columns: 1fr; }
}
"""


def inject_theme(mode: str) -> None:
    """Inject tokens for ``mode`` ("Dark" or "Light") and the shared stylesheet."""
    tokens = TOKENS.get(mode, TOKENS["Dark"])
    variables = ";".join(f"--{name}:{value}" for name, value in tokens.items())
    ring = tokens["accent"]
    st.markdown(
        f"<style>:root{{{variables};--ring:{ring};color-scheme:{'dark' if mode != 'Light' else 'light'}}}"
        f"{_STYLESHEET}</style>",
        unsafe_allow_html=True,
    )
