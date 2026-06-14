"""Gradio UI for the Multimodal AI Design Analysis Suite.

OWNER: Person E
SPRINT CONCEPTS: Sprint 4 — Gradio app surface for the multi-agent pipeline.
CONSUMES: ``agents.graph.run_graph``, ``agents.base.build_default_deps``,
          ``schemas.outputs.DesignReport``.
PROVIDES: a Gradio Blocks app on ``http://127.0.0.1:7860`` with three tabs:
          (1) full DesignReport JSON, (2) per-agent collapsibles, (3)
          retrieved reference matches.

WHY THIS FILE LIVES OUTSIDE ``src/``
------------------------------------
``src/`` is library code — imported by tests, the MCP server, and CI.
``ui/`` is user-facing entrypoint code. Keeping them separate avoids
"why did importing FakeLLM start a Gradio server?" surprises.

LAUNCH
------
    python ui/app.py            # offline (fakes), no API key
    USE_REAL=1 python ui/app.py # real OpenRouter, ≈ $0.03 / run
"""

from __future__ import annotations

import html
import os
import sys
from collections.abc import Generator, Mapping
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import src.config as app_config  # noqa: E402
from src.agents.base import AgentDeps, build_default_deps  # noqa: E402
from src.agents.graph import run_graph  # noqa: E402
from src.config import (  # noqa: E402, F401  # `settings` is reassigned via `global` in _fresh_settings
    Settings,
    settings,
)
from src.schemas.outputs import DesignReport  # noqa: E402
from src.utils.logger import get_logger  # noqa: E402

log = get_logger(__name__)

APP_CSS = """
:root {
  color-scheme: light;
  /* Surfaces */
  --surface: #f7f7f3;
  --panel: #ffffff;
  --line: #e2e6dd;
  --line-strong: #c8d0c4;
  /* Ink */
  --ink: #14202a;
  --muted: #415054;
  --soft-text: #38474c;
  /* Brand */
  --teal: #0f766e;
  --teal-dark: #0b5f58;
  --blue: #2563eb;
  --blue-dark: #1d4ed8;
  --coral: #d45d4c;
  --coral-dark: #a9473a;
  --gold: #b88718;
  --navy: #1f3142;
  /* Tints */
  --green-soft: #e7f4ef;
  --coral-soft: #faece8;
  --gold-soft: #f7efd8;
  --blue-soft: #e8f0f7;
  /* Depth */
  --shadow-sm: 0 1px 2px rgba(20, 32, 42, 0.05);
  --shadow-md: 0 6px 18px rgba(20, 32, 42, 0.06), 0 2px 4px rgba(20, 32, 42, 0.04);
  --shadow-lg: 0 18px 42px rgba(20, 32, 42, 0.08), 0 4px 12px rgba(20, 32, 42, 0.05);
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 16px;
  --ease: cubic-bezier(0.4, 0, 0.2, 1);
}

/* Modern type stack — Inter loaded via head, with safe fallbacks */
.gradio-container,
.gradio-container body {
  font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI",
               "Helvetica Neue", Arial, sans-serif !important;
  font-feature-settings: "cv11" 1, "ss01" 1;
}

html,
body {
  color-scheme: light;
}

.gradio-container {
  background:
    linear-gradient(180deg, #f7f6ef 0%, #fbfaf6 36%, #ffffff 100%) !important;
  color: var(--ink) !important;
}

.gradio-container label,
.gradio-container textarea,
.gradio-container input,
.gradio-container th,
.gradio-container td,
.gradio-container .prose,
.gradio-container .markdown,
.gradio-container .label-wrap,
.gradio-container .form,
.gradio-container .wrap {
  color: var(--ink) !important;
}

.gradio-container ::placeholder {
  color: #607174 !important;
  opacity: 1 !important;
}

.app-shell {
  max-width: 1180px;
  margin: 0 auto;
  padding: 0 6px;
}

.hero-band {
  position: relative;
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background:
    radial-gradient(circle at 0% 0%, rgba(15, 118, 110, 0.14) 0%, transparent 38%),
    radial-gradient(circle at 100% 0%, rgba(212, 93, 76, 0.12) 0%, transparent 42%),
    linear-gradient(180deg, #ffffff 0%, #fbfaf4 100%);
  padding: 36px 36px 32px;
  margin: 22px 0;
  box-shadow: var(--shadow-md);
  overflow: hidden;
}

.hero-band::after {
  content: "";
  position: absolute;
  inset: auto -40px -40px auto;
  width: 220px;
  height: 220px;
  background: radial-gradient(circle, rgba(15, 118, 110, 0.10) 0%, transparent 70%);
  pointer-events: none;
}

.hero-band .eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--teal-dark);
  background: rgba(15, 118, 110, 0.10);
  padding: 5px 10px;
  border-radius: 999px;
  margin-bottom: 14px;
}

.hero-band .eyebrow::before {
  content: "";
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--teal);
  box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.18);
}

.hero-band h1 {
  margin: 0 0 12px;
  font-size: 40px;
  line-height: 1.05;
  letter-spacing: -0.02em;
  font-weight: 800;
  color: var(--ink);
}

.hero-band p {
  max-width: 760px;
  margin: 0;
  color: var(--soft-text);
  font-size: 16.5px;
  line-height: 1.6;
}

.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 22px;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid rgba(15, 118, 110, 0.24);
  background: #ffffff;
  border-radius: 999px;
  color: var(--teal-dark);
  font-size: 12.5px;
  font-weight: 700;
  letter-spacing: 0.01em;
  padding: 7px 13px;
  box-shadow: var(--shadow-sm);
  transition: transform 200ms var(--ease), box-shadow 200ms var(--ease);
}

.chip:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}

.chip::before {
  content: "";
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--teal);
}

.guide-card,
.result-card,
.status-card,
.settings-card,
.reference-card {
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  background: var(--panel);
  padding: 22px;
  box-shadow: var(--shadow-sm);
  transition: box-shadow 200ms var(--ease), transform 200ms var(--ease);
}

.guide-card:hover {
  box-shadow: var(--shadow-md);
}

.guide-card h3,
.result-card h3,
.status-card h3,
.settings-card h3,
.reference-card h3 {
  margin: 0 0 12px;
  font-size: 16px;
  font-weight: 700;
  letter-spacing: -0.005em;
  color: var(--ink) !important;
}

.guide-card p,
.guide-card li,
.result-card p,
.result-card li,
.status-card p,
.settings-card p,
.settings-card li,
.reference-card p,
.reference-card li {
  color: var(--soft-text);
  font-size: 14.5px;
  line-height: 1.6;
}

.guide-card ul,
.result-card ul,
.reference-card ul {
  margin: 0;
  padding-left: 18px;
}

.guide-card li {
  margin-bottom: 6px;
}

.settings-card b,
.reference-card b {
  color: var(--ink) !important;
}

.reference-card a,
.settings-card a {
  color: #0b5f99 !important;
  font-weight: 700;
}

.steps {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin: 14px 0 22px;
}

.step {
  position: relative;
  border-radius: var(--radius-md);
  border: 1px solid var(--line);
  background: #ffffff;
  padding: 18px 18px 18px 56px;
  box-shadow: var(--shadow-sm);
  transition: transform 200ms var(--ease), box-shadow 200ms var(--ease),
              border-color 200ms var(--ease);
}

.step:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.step::before {
  content: attr(data-step);
  position: absolute;
  top: 18px;
  left: 16px;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 800;
  color: #ffffff;
  background: var(--teal);
  box-shadow: 0 0 0 4px rgba(15, 118, 110, 0.14);
}

.step.accent-coral::before { background: var(--coral); box-shadow: 0 0 0 4px rgba(212, 93, 76, 0.14); }
.step.accent-gold::before  { background: var(--gold);  box-shadow: 0 0 0 4px rgba(184, 135, 24, 0.16); }

.step b {
  display: block;
  color: var(--ink);
  font-size: 14.5px;
  font-weight: 700;
  margin-bottom: 4px;
}

.step span {
  color: var(--soft-text);
  font-size: 13px;
  line-height: 1.5;
}

.accent-teal { border-left: 4px solid var(--teal); }
.accent-coral { border-left: 4px solid var(--coral); }
.accent-gold { border-left: 4px solid var(--gold); }

.upload-panel {
  border: 1px solid #c9d4cd;
  border-radius: 8px;
  background: #fffefb;
  padding: 18px;
  box-shadow: 0 8px 24px rgba(29, 37, 40, 0.06);
}

.upload-panel h3,
.upload-panel p,
.upload-panel span,
.upload-panel label,
.upload-panel table,
.upload-panel th,
.upload-panel td {
  color: var(--ink) !important;
}

.upload-panel p {
  color: var(--soft-text) !important;
  font-size: 15px;
  line-height: 1.55;
}

.upload-panel textarea,
.upload-panel input {
  background: #ffffff !important;
  border-color: #bfcac3 !important;
  color: var(--ink) !important;
}

.upload-panel button,
.upload-panel [role="button"] {
  color: var(--ink) !important;
}

.upload-panel .table-wrap,
.upload-panel table {
  background: #ffffff !important;
}

.upload-panel th {
  background: #eef5f1 !important;
  color: #203235 !important;
  font-weight: 700 !important;
}

.upload-panel td {
  background: #ffffff !important;
  color: #243236 !important;
}

.upload-panel .wrap {
  gap: 14px;
}

.status-card {
  min-height: 124px;
  background: #f4fbf8;
  border-color: #bed8cc;
}

.status-card h3 {
  color: #0b5f58;
}

.reference-card {
  background: #f8fbff;
  border-color: #c9d9e8;
}

.settings-card {
  background: #ffffff;
  border-color: #c9d9e8;
  color: var(--ink) !important;
}

.settings-card,
.settings-card *,
.reference-card,
.reference-card * {
  color: var(--ink) !important;
  -webkit-text-fill-color: currentColor !important;
}

.settings-card p,
.settings-card li,
.reference-card p,
.reference-card li,
.reference-card span {
  color: var(--soft-text) !important;
}

.reference-panel,
.reference-panel .form,
.reference-panel .block,
.reference-panel .wrap,
.reference-panel .input-container,
.reference-panel .checkbox-container,
.reference-panel textarea,
.reference-panel input,
.reference-gallery,
.reference-gallery .wrap,
.reference-gallery .block,
.reference-gallery .empty,
.reference-gallery [data-testid="gallery"] {
  background: #ffffff !important;
  background-color: #ffffff !important;
  border-color: #b9c8c0 !important;
  color: var(--ink) !important;
  -webkit-text-fill-color: var(--ink) !important;
}

.reference-panel label.float,
.reference-panel .float,
.reference-panel [data-testid="block-info"],
.reference-panel .label-wrap,
.reference-panel .label-wrap *,
.reference-panel .block-label,
.reference-panel .block-title,
.reference-gallery label.float,
.reference-gallery .float,
.reference-gallery [data-testid="block-info"],
.reference-gallery .label-wrap,
.reference-gallery .label-wrap *,
.reference-gallery .block-label,
.reference-gallery .block-title {
  background: #eef5f1 !important;
  background-color: #eef5f1 !important;
  border: 1px solid #bed8cc !important;
  border-radius: 7px !important;
  color: #16282b !important;
  -webkit-text-fill-color: #16282b !important;
  font-weight: 750 !important;
}

.reference-panel input[type="checkbox"] {
  accent-color: var(--blue) !important;
}

.reference-panel button.primary,
.reference-panel button.primary *,
.reference-panel .primary,
.reference-panel .primary * {
  background: var(--blue) !important;
  background-color: var(--blue) !important;
  border-color: var(--blue-dark) !important;
  color: #ffffff !important;
  -webkit-text-fill-color: #ffffff !important;
}

.report-wrap,
.report-wrap * {
  color: var(--ink) !important;
  -webkit-text-fill-color: var(--ink) !important;
}

.report-wrap {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  padding: 32px;
  box-shadow: var(--shadow-md);
}

.report-wrap h2 {
  margin: 0 0 6px;
  font-size: 26px;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.report-wrap .report-subtitle {
  margin: 0 0 22px;
  color: var(--soft-text) !important;
  font-size: 14px;
}

.report-wrap h3 {
  margin: 28px 0 10px;
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--muted) !important;
}

.report-wrap h3::after {
  content: "";
  display: block;
  width: 28px;
  height: 2px;
  background: var(--teal);
  margin-top: 6px;
  border-radius: 2px;
}

.report-wrap ul {
  margin: 0;
  padding-left: 0;
  list-style: none;
}

.report-wrap ul li {
  color: var(--soft-text) !important;
  -webkit-text-fill-color: var(--soft-text) !important;
  line-height: 1.6;
  margin-bottom: 10px;
  padding-left: 22px;
  position: relative;
}

.report-wrap ul li::before {
  content: "";
  position: absolute;
  left: 0;
  top: 9px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--teal);
  opacity: 0.45;
}

/* Recommendation cards (nested ul .rec-list) */
.report-wrap .rec-list {
  display: grid;
  gap: 12px;
}

.report-wrap .rec-list li {
  background: #fbfaf6;
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  padding: 16px 18px 16px 18px;
  margin-bottom: 0;
  list-style: none;
}

.report-wrap .rec-list li::before {
  display: none;
}

.report-wrap .rec-list b {
  display: block;
  color: var(--ink) !important;
  font-size: 15px;
  font-weight: 700;
  margin-bottom: 8px;
}

.report-score {
  display: inline-flex;
  align-items: baseline;
  gap: 8px;
  padding: 18px 24px;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, #ecfaf3 0%, #d6f0e2 100%);
  border: 1px solid #bedccd;
  font-weight: 800;
  box-shadow: var(--shadow-sm);
  margin-bottom: 12px;
}

.report-score,
.report-score * {
  color: var(--teal-dark) !important;
  -webkit-text-fill-color: var(--teal-dark) !important;
}

.report-score span.report-score-value {
  font-size: 44px;
  line-height: 1;
  letter-spacing: -0.03em;
  font-weight: 800;
}

.report-score span.report-score-suffix {
  font-size: 16px;
  font-weight: 600;
  opacity: 0.7;
}

.report-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  padding: 3px 10px;
  border-radius: 999px;
  background: #eef2f7;
  border: 1px solid #cdd6e0;
  margin-right: 6px;
  color: var(--navy) !important;
}

.report-tag.tag-effort {
  background: var(--gold-soft);
  border-color: rgba(184, 135, 24, 0.36);
  color: #6a4e0a !important;
}

.report-tag.tag-impact {
  background: var(--green-soft);
  border-color: rgba(15, 118, 110, 0.36);
  color: var(--teal-dark) !important;
}

.report-tag.tag-lift {
  background: #eaf6ff;
  border-color: rgba(37, 99, 235, 0.32);
  color: #1d4ed8 !important;
}

.report-tag.tag-priority {
  background: #fff;
  border-color: rgba(15, 118, 110, 0.4);
  color: var(--teal-dark) !important;
  font-weight: 800 !important;
  width: 28px;
  height: 28px;
  padding: 0 !important;
  justify-content: center;
  font-size: 12px !important;
  border-radius: 50% !important;
  box-shadow: var(--shadow-sm);
}

/* --- premium report hero ------------------------------------------- */
.report-hero {
  display: grid;
  grid-template-columns: minmax(220px, 280px) 1fr;
  gap: 28px;
  align-items: center;
  background: linear-gradient(135deg, #fbfaf6 0%, #f4f8f5 100%);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  padding: 28px 28px 26px;
  margin-bottom: 28px;
  box-shadow: var(--shadow-sm);
}

.report-hero .score-block {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 22px 18px;
  background: #ffffff;
  border: 1px solid #cfe1d6;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}

.report-hero .score-block .label {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--teal-dark) !important;
  -webkit-text-fill-color: var(--teal-dark) !important;
  margin-bottom: 4px;
}

.report-hero .score-block .value {
  font-size: 64px;
  line-height: 1;
  font-weight: 900;
  letter-spacing: -0.04em;
  color: var(--ink) !important;
  -webkit-text-fill-color: var(--ink) !important;
}

.report-hero .score-block .anchor {
  font-size: 12.5px;
  font-weight: 700;
  color: var(--teal-dark) !important;
  -webkit-text-fill-color: var(--teal-dark) !important;
  margin-top: 8px;
  padding: 4px 10px;
  background: var(--green-soft);
  border-radius: 999px;
}

.report-hero .score-meta {
  font-size: 11.5px;
  color: var(--muted) !important;
  -webkit-text-fill-color: var(--muted) !important;
  margin-top: 14px;
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
}

.report-hero .rationale {
  font-size: 15px;
  line-height: 1.65;
  color: var(--ink) !important;
  -webkit-text-fill-color: var(--ink) !important;
  margin: 0;
}

.report-hero .rationale-label {
  font-size: 10.5px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--muted) !important;
  -webkit-text-fill-color: var(--muted) !important;
  margin-bottom: 8px;
}

/* --- breakdown bars ------------------------------------------------ */
.breakdown {
  display: grid;
  gap: 10px;
  margin-bottom: 28px;
}

.breakdown-row {
  display: grid;
  grid-template-columns: 130px 1fr 50px;
  align-items: center;
  gap: 14px;
}

.breakdown-row .axis {
  font-size: 13px;
  font-weight: 700;
  color: var(--ink) !important;
  -webkit-text-fill-color: var(--ink) !important;
  text-transform: capitalize;
}

.breakdown-row .bar {
  position: relative;
  height: 10px;
  background: #eef1eb;
  border-radius: 999px;
  overflow: hidden;
  border: 1px solid var(--line);
}

.breakdown-row .bar-fill {
  position: absolute;
  inset: 0 auto 0 0;
  background: linear-gradient(90deg, var(--teal) 0%, #14a085 100%);
  border-radius: 999px;
}

.breakdown-row.warn .bar-fill {
  background: linear-gradient(90deg, #c89523 0%, #e0a93a 100%);
}

.breakdown-row.fail .bar-fill {
  background: linear-gradient(90deg, var(--coral) 0%, #e07565 100%);
}

.breakdown-row .num {
  font-size: 13px;
  font-weight: 700;
  text-align: right;
  font-variant-numeric: tabular-nums;
  color: var(--ink) !important;
  -webkit-text-fill-color: var(--ink) !important;
}

/* --- quick wins callout ------------------------------------------- */
.quick-wins {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  background: linear-gradient(135deg, #eafaf3 0%, #def4e7 100%);
  border: 1px solid #b9dec8;
  border-radius: var(--radius-md);
  padding: 16px 20px;
  margin-bottom: 22px;
  box-shadow: var(--shadow-sm);
}

.quick-wins-icon {
  font-size: 22px;
  font-weight: 900;
  color: var(--teal-dark) !important;
  -webkit-text-fill-color: var(--teal-dark) !important;
  background: #ffffff;
  border-radius: 8px;
  padding: 4px 10px;
  border: 1px solid #b9dec8;
}

.quick-wins-body {
  flex: 1;
}

.quick-wins-title {
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--teal-dark) !important;
  -webkit-text-fill-color: var(--teal-dark) !important;
  margin-bottom: 4px;
}

.quick-wins-body p {
  margin: 0;
  font-size: 14px;
  line-height: 1.55;
  color: var(--ink) !important;
  -webkit-text-fill-color: var(--ink) !important;
}

/* --- ranked recommendation cards ---------------------------------- */
.report-wrap .rec-list .priority-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}

.report-wrap .rec-list .meta-row {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.report-wrap .rec-list .proof {
  display: inline-block;
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
  font-size: 11.5px;
  color: var(--muted) !important;
  -webkit-text-fill-color: var(--muted) !important;
  background: #f3f5ef;
  border: 1px solid var(--line);
  padding: 2px 8px;
  border-radius: 6px;
  margin-top: 6px;
}

.report-wrap .rec-list .rationale-text {
  color: var(--soft-text) !important;
  -webkit-text-fill-color: var(--soft-text) !important;
  font-size: 14px;
  line-height: 1.55;
  margin: 4px 0 0;
}

/* --- analyst status grid ------------------------------------------ */
.status-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 22px;
}

.status-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 12px 8px;
  background: #ffffff;
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
}

.status-cell .dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  margin-bottom: 6px;
}

.status-cell.ok      .dot { background: #16a34a; }
.status-cell.partial .dot { background: #d4a017; }
.status-cell.failed  .dot { background: #c4493a; }
.status-cell.skipped .dot { background: #94a3b8; }

.status-cell .name {
  font-size: 12px;
  font-weight: 700;
  text-transform: capitalize;
  color: var(--ink) !important;
  -webkit-text-fill-color: var(--ink) !important;
}

.status-cell .state {
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  margin-top: 2px;
}

.status-cell.ok      .state { color: #166534 !important; -webkit-text-fill-color: #166534 !important; }
.status-cell.partial .state { color: #854d0e !important; -webkit-text-fill-color: #854d0e !important; }
.status-cell.failed  .state { color: #842c1f !important; -webkit-text-fill-color: #842c1f !important; }
.status-cell.skipped .state { color: #475569 !important; -webkit-text-fill-color: #475569 !important; }

/* --- detail collapse for specialist sections ---------------------- */
.report-wrap details.specialist {
  margin-top: 14px;
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  background: #fdfcf8;
  padding: 0;
  box-shadow: var(--shadow-sm);
}

.report-wrap details.specialist summary {
  list-style: none;
  cursor: pointer;
  padding: 12px 18px;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--ink) !important;
  -webkit-text-fill-color: var(--ink) !important;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.report-wrap details.specialist summary::-webkit-details-marker { display: none; }

.report-wrap details.specialist summary::after {
  content: "+";
  font-size: 18px;
  font-weight: 700;
  color: var(--muted) !important;
  -webkit-text-fill-color: var(--muted) !important;
}

.report-wrap details[open].specialist summary::after { content: "-"; }

.report-wrap details.specialist .body {
  padding: 4px 18px 16px;
}

.json-holder {
  border-radius: 8px;
  overflow: hidden;
}

button.primary,
.gradio-button.primary {
  background: #0f766e !important;
  border-color: #0f766e !important;
}

/* Contrast safety overrides for Gradio-generated controls. */
.gradio-container h1,
.gradio-container h2,
.gradio-container h3,
.gradio-container h4,
.gradio-container h5,
.gradio-container h6,
.gradio-container p,
.gradio-container li,
.gradio-container label,
.gradio-container legend,
.gradio-container .prose,
.gradio-container .markdown,
.gradio-container .caption,
.gradio-container .label-wrap,
.gradio-container .block-title,
.gradio-container .block-label {
  color: var(--ink) !important;
}

.gradio-container p,
.gradio-container li,
.gradio-container .prose,
.gradio-container .markdown {
  color: var(--soft-text) !important;
}

.gradio-container button,
.gradio-container button span,
.gradio-container [role="button"],
.gradio-container [role="button"] span {
  color: var(--ink) !important;
}

.gradio-container button:not([role="tab"]):not(.primary),
.gradio-container button:not([role="tab"]):not(.primary) span {
  background: #ffffff !important;
  border-color: #9db2bf !important;
  color: #173247 !important;
  font-weight: 700 !important;
}

.gradio-container button:not([role="tab"]):not(.primary):hover {
  background: #e8f1ff !important;
  border-color: var(--blue) !important;
}

.gradio-container button.primary,
.gradio-container button.primary span,
.gradio-container .gradio-button.primary,
.gradio-container .gradio-button.primary span {
  background: var(--blue) !important;
  border-color: var(--blue-dark) !important;
  color: #ffffff !important;
  font-weight: 750 !important;
}

.gradio-container button.primary:hover,
.gradio-container .gradio-button.primary:hover {
  background: var(--blue-dark) !important;
  border-color: #1e40af !important;
}

.gradio-container button[role="tab"],
.gradio-container button[role="tab"] span,
.gradio-container .tab-nav button,
.gradio-container .tab-nav button span {
  background: #ffffff !important;
  border-color: #cbd7cf !important;
  color: #1d2528 !important;
  font-weight: 700 !important;
}

.gradio-container button[role="tab"][aria-selected="true"],
.gradio-container button[role="tab"][aria-selected="true"] span,
.gradio-container .tab-nav button.selected,
.gradio-container .tab-nav button.selected span {
  background: #0f766e !important;
  border-color: #0f766e !important;
  color: #ffffff !important;
}

.gradio-container textarea,
.gradio-container input,
.gradio-container table,
.gradio-container th,
.gradio-container td {
  color: #1d2528 !important;
}

.gradio-container th {
  background: #eaf3ef !important;
  color: #16282b !important;
}

.gradio-container td {
  background: #ffffff !important;
}

.gradio-container [data-testid="file"],
.gradio-container [data-testid="file"] *,
.gradio-container .file-preview,
.gradio-container .file-preview *,
.gradio-container .upload-container,
.gradio-container .upload-container *,
.gradio-container .filepond--drop-label,
.gradio-container .filepond--drop-label * {
  color: #1d2528 !important;
}

.gradio-container [data-testid="file"],
.gradio-container .upload-container,
.gradio-container .filepond--root {
  background: #ffffff !important;
  border-color: #b9c8c0 !important;
}

.gradio-container .upload-panel .form,
.gradio-container .upload-panel .block,
.gradio-container .upload-panel .wrap,
.gradio-container .upload-panel .input-container,
.gradio-container .upload-panel .checkbox-container,
.gradio-container .upload-panel [data-testid="file"],
.gradio-container .upload-panel .file-preview,
.gradio-container .upload-panel .upload-container,
.gradio-container .upload-panel .filepond--root,
.gradio-container .upload-panel .filepond--panel,
.gradio-container .upload-panel .filepond--drop-label {
  background: #ffffff !important;
  background-color: #ffffff !important;
  border-color: #b9c8c0 !important;
  color: #1d2528 !important;
  -webkit-text-fill-color: #1d2528 !important;
}

.gradio-container .upload-panel .form *,
.gradio-container .upload-panel .block *,
.gradio-container .upload-panel [data-testid="file"] *,
.gradio-container .upload-panel .file-preview *,
.gradio-container .upload-panel .upload-container *,
.gradio-container .upload-panel .filepond--drop-label *,
.gradio-container .upload-panel .checkbox-container *,
.gradio-container .upload-panel textarea,
.gradio-container .upload-panel textarea *,
.gradio-container .upload-panel input,
.gradio-container .upload-panel input * {
  color: #1d2528 !important;
  -webkit-text-fill-color: #1d2528 !important;
}

.gradio-container .upload-panel label.float,
.gradio-container .upload-panel .float,
.gradio-container .upload-panel [data-testid="block-info"],
.gradio-container .upload-panel .label-wrap,
.gradio-container .upload-panel .label-wrap *,
.gradio-container .upload-panel .block-label,
.gradio-container .upload-panel .block-title {
  background: #eef5f1 !important;
  background-color: #eef5f1 !important;
  color: #16282b !important;
  -webkit-text-fill-color: #16282b !important;
  border: 1px solid #bed8cc !important;
  border-radius: 7px !important;
  font-weight: 750 !important;
}

.gradio-container .upload-panel textarea,
.gradio-container .upload-panel input[type="text"] {
  background: #ffffff !important;
  background-color: #ffffff !important;
  border: 1px solid #b9c8c0 !important;
  color: #1d2528 !important;
  -webkit-text-fill-color: #1d2528 !important;
}

.gradio-container .upload-panel input[type="checkbox"] {
  accent-color: #0f766e !important;
}

.gradio-container .gr-accordion,
.gradio-container .gr-accordion *,
.gradio-container details,
.gradio-container details * {
  background-color: #fffefb !important;
  color: #1d2528 !important;
  -webkit-text-fill-color: #1d2528 !important;
}

@media (max-width: 760px) {
  .hero-band {
    padding: 22px 18px;
  }

  .hero-band h1 {
    font-size: 28px;
  }

  .steps {
    grid-template-columns: 1fr;
  }
}

.gradio-container .upload-panel button.primary,
.gradio-container .upload-panel button.primary.svelte-xzq5jh,
.gradio-container button.primary,
.gradio-container button.primary *,
.gradio-container .primary,
.gradio-container .primary * {
  background-color: var(--blue) !important;
  border-color: var(--blue-dark) !important;
  color: #ffffff !important;
  -webkit-text-fill-color: #ffffff !important;
}
"""

FORCE_LIGHT_THEME_JS = """
() => {
  const root = document.documentElement;
  root.classList.remove("dark");
  root.classList.add("light");
  root.dataset.theme = "light";
  localStorage.setItem("theme", "light");
  localStorage.setItem("__theme", "light");
  localStorage.setItem("gradio-theme", "light");

  const params = new URLSearchParams(window.location.search);
  if (params.get("__theme") !== "light") {
    params.set("__theme", "light");
    const nextUrl = `${window.location.pathname}?${params.toString()}${window.location.hash}`;
    window.history.replaceState({}, "", nextUrl);
  }

  return [];
}
"""

FORCE_LIGHT_THEME_HEAD = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<script>
  document.documentElement.classList.remove("dark");
  document.documentElement.classList.add("light");
  document.documentElement.dataset.theme = "light";
  localStorage.setItem("theme", "light");
  localStorage.setItem("__theme", "light");
  localStorage.setItem("gradio-theme", "light");
</script>
"""


def _status_message(title: str, body: str) -> str:
    return f"""
<div class="status-card">
  <h3>{html.escape(title)}</h3>
  <p>{html.escape(body)}</p>
</div>
"""


def _fresh_settings() -> Settings:
    """Re-read .env and point UI-adjacent modules at the fresh Settings."""
    global settings

    app_config.get_settings.cache_clear()
    settings = app_config.get_settings()
    app_config.settings = settings

    modules = (
        "src.agents.base",
        "src.tools.web_search",
        "src.llm.openrouter_client",
        "src.llm.multimodal",
        "src.rag.retriever",
        "src.rag.embedder",
    )
    for module_name in modules:
        module = sys.modules.get(module_name)
        if module is not None:
            module.settings = settings
    return settings


def _has_openrouter_key() -> bool:
    cfg = _fresh_settings()
    return bool(cfg.openrouter_api_key and "REPLACE_ME" not in cfg.openrouter_api_key)


def _default_real_mode() -> bool:
    cfg = _fresh_settings()
    return cfg.use_real or _has_openrouter_key()


def _resolve_reference_path(image_path: str) -> str:
    """Convert portable retriever paths into browser-readable local paths."""
    cfg = _fresh_settings()
    candidates = [
        Path(image_path),
        PROJECT_ROOT / image_path,
        cfg.reference_dir.parent / image_path,
        cfg.reference_dir / image_path,
    ]
    for p in candidates:
        if p.exists():
            return str(p.resolve())
    return image_path


def _vector_row_count() -> int:
    try:
        from src.rag.vector_store import get_or_create_table, open_db

        table = get_or_create_table(open_db(), dim=512)
        return int(table.count_rows())
    except Exception as e:
        log.warning("references: could not count vector rows: %s", e)
        return 0


def _local_reference_file_count() -> int:
    cfg = _fresh_settings()
    exts = {".png", ".jpg", ".jpeg", ".webp"}
    if not cfg.reference_dir.exists():
        return 0
    return sum(1 for p in cfg.reference_dir.rglob("*") if p.suffix.lower() in exts)


def _format_web_references(query: str, use_real: bool) -> str:
    if not use_real:
        return """
<div class="reference-card">
  <h3>Web references</h3>
  <p>Turn on real references for live web results.</p>
</div>
"""
    try:
        cfg = _fresh_settings()
        from src.tools.web_search import get_default_search

        provider = "Tavily" if cfg.tavily_api_key else "DuckDuckGo"
        hits = get_default_search().search(f"{query} UI design examples", k=5)
    except Exception as e:
        return f"""
<div class="reference-card">
  <h3>Web references</h3>
  <p>Search failed: {html.escape(str(e))}</p>
</div>
"""

    if not hits:
        return """
<div class="reference-card">
  <h3>Web references</h3>
  <p>No live results. Check TAVILY_API_KEY or network access.</p>
</div>
"""

    rows = "\n".join(
        "<li>"
        f'<a href="{html.escape(hit.url)}" target="_blank">'
        f"{html.escape(hit.title)}</a>"
        f"<br><span>{html.escape(hit.snippet[:180])}</span>"
        "</li>"
        for hit in hits
    )
    return f"""
<div class="reference-card">
  <h3>Web references from {provider}</h3>
  <ul>{rows}</ul>
</div>
"""


def on_run(
    image: Any,
    instructions: str,
) -> Generator[tuple[str, dict[str, Any], dict[str, Any] | None], None, None]:
    """Streaming run handler for Tab 1.

    The runtime mode (real APIs vs offline fakes) is read from ``.env`` —
    specifically ``USE_REAL`` and the presence of ``OPENROUTER_API_KEY``.
    There is no UI override; the Settings tab shows what's loaded.
    """
    if image is None:
        yield (
            _status_message(
                "Upload needed",
                "Add a PNG or JPG screenshot first.",
            ),
            {},
            None,
        )
        return

    image_path = Path(image.name if hasattr(image, "name") else image)
    _fresh_settings()
    use_real = _default_real_mode()

    if use_real and not _has_openrouter_key():
        yield (
            _status_message(
                "Missing API key",
                "USE_REAL is on but OPENROUTER_API_KEY is not set in .env. "
                "Either add the key or set USE_REAL=false in .env.",
            ),
            {},
            None,
        )
        return

    deps: AgentDeps = build_default_deps(use_real=use_real)
    mode_label = "real APIs (.env)" if use_real else "offline fakes"

    yield (
        _status_message(
            "Analysis running",
            f"Reviewing {image_path.name} with {mode_label}.",
        ),
        {},
        None,
    )
    report: DesignReport = run_graph(image_path, instructions=instructions or None, deps=deps)
    report_dict = report.model_dump()
    yield (
        _status_message(
            "Report ready",
            f"Score: {report.overall_score:.1f}/100. Open Report.",
        ),
        report_dict,
        report_dict,
    )


def _ul(items: list[str]) -> str:
    """Render an escaped HTML list (items may contain pre-escaped markup)."""
    rows = "".join(f"<li>{item}</li>" for item in items)
    return f"<ul>{rows}</ul>"


def _score_anchor(score: float) -> str:
    """Map an overall score to its rubric anchor label."""
    if score >= 95:
        return "World-class"
    if score >= 80:
        return "Production-ready"
    if score >= 65:
        return "Needs polish"
    if score >= 50:
        return "Significant rework"
    return "Foundational issues"


def _bar_class(value: float) -> str:
    """Color a breakdown bar by health: ok / warn / fail."""
    if value >= 75:
        return ""
    if value >= 55:
        return "warn"
    return "fail"


def _status_grid(status: Mapping[str, str]) -> str:
    """Five-cell grid showing per-agent run status."""
    if not status:
        return ""
    order = ["visual", "ux", "accessibility", "brand", "market"]
    cells: list[str] = []
    for axis in order:
        state = status.get(axis, "skipped")
        cls = state if state in {"ok", "partial", "failed", "skipped"} else "skipped"
        cells.append(
            f'<div class="status-cell {cls}">'
            f'<span class="dot"></span>'
            f'<span class="name">{html.escape(axis)}</span>'
            f'<span class="state">{html.escape(cls)}</span>'
            "</div>"
        )
    return f'<div class="status-grid">{"".join(cells)}</div>'


def _breakdown_bars(breakdown: dict[str, float], default: float = 50.0) -> str:
    """Five horizontal bars, one per axis."""
    order = ["visual", "ux", "accessibility", "brand", "market"]
    rows: list[str] = []
    for axis in order:
        value = float(breakdown.get(axis, default))
        cls = _bar_class(value)
        width = max(0.0, min(100.0, value))
        rows.append(
            f'<div class="breakdown-row {cls}">'
            f'<span class="axis">{html.escape(axis)}</span>'
            f'<span class="bar"><span class="bar-fill" style="width: {width:.1f}%"></span></span>'
            f'<span class="num">{value:.0f}</span>'
            "</div>"
        )
    return f'<div class="breakdown">{"".join(rows)}</div>'


def _quick_wins_block(report: DesignReport) -> str:
    """Highlight high-impact, low-effort recommendations (the wins to ship first)."""
    wins = [r for r in report.top_recommendations if r.impact == "L" and r.effort == "S"]
    if not wins:
        return ""
    lines = []
    for r in wins[:2]:
        lift = f" — {html.escape(r.metric_lift)}" if r.metric_lift else ""
        lines.append(f"<b>#{r.priority}.</b> {html.escape(r.title)}{lift}")
    body = "<br>".join(lines)
    return (
        '<div class="quick-wins">'
        '<span class="quick-wins-icon">!</span>'
        '<div class="quick-wins-body">'
        '<div class="quick-wins-title">Quick wins — ship first</div>'
        f"<p>{body}</p>"
        "</div></div>"
    )


def _recommendation_card(r: Any) -> str:
    """Render one premium recommendation card with priority chip + meta row."""
    e = html.escape
    parts = [
        '<div class="priority-row">',
        f'<span class="report-tag tag-priority">{r.priority}</span>',
        f"<b>{e(r.title)}</b>",
        "</div>",
        f'<p class="rationale-text">{e(r.rationale)}</p>',
        '<div class="meta-row">',
        f'<span class="report-tag tag-effort">Effort {e(str(r.effort))}</span>',
        f'<span class="report-tag tag-impact">Impact {e(str(r.impact))}</span>',
    ]
    if r.metric_lift:
        parts.append(f'<span class="report-tag tag-lift">{e(r.metric_lift)}</span>')
    parts.append("</div>")
    if r.proof:
        parts.append(f'<span class="proof">Source · {e(r.proof)}</span>')
    return "".join(parts)


def render_report(report: DesignReport | dict[str, Any] | None) -> str:
    """Format the latest report as a self-contained, premium HTML block.

    Layout (top to bottom):
      1. Hero: large score number + 1-paragraph score_rationale (the WHY).
      2. Breakdown: five horizontal bars (visual, ux, accessibility, brand, market).
      3. Per-agent run status grid (ok / partial / failed / skipped).
      4. Quick wins callout (high-impact + low-effort only).
      5. Top strengths (3 distinguishing items).
      6. Ranked recommendations (priority chip, effort/impact pills,
         metric_lift, source citation).
      7. Collapsible specialist sections for the curious.
    """
    if report is None:
        return """
<div class="result-card">
  <h3>No report yet</h3>
  <p>Run an analysis from the Analyze tab. The score, justification,
  per-axis breakdown, and prioritized recommendations will appear here.</p>
</div>
"""
    rep: DesignReport = DesignReport.model_validate(report) if isinstance(report, dict) else report
    report = rep

    e = html.escape
    score = report.overall_score or 0.0
    anchor = _score_anchor(score)

    # --- runtime metadata --------------------------------------------- #
    meta_parts: list[str] = []
    if report.run_id:
        meta_parts.append(f"run · {e(report.run_id)}")
    if report.analyzed_at:
        meta_parts.append(e(report.analyzed_at))
    meta_line = " &nbsp;·&nbsp; ".join(meta_parts) if meta_parts else ""

    rationale = e(
        report.score_rationale
        or (
            "No rationale was returned. The synthesizer must explain the "
            "score; re-run if this persists."
        )
    )
    hero = (
        '<div class="report-hero">'
        '<div class="score-block">'
        '<span class="label">Overall</span>'
        f'<span class="value">{score:.1f}</span>'
        f'<span class="anchor">{e(anchor)}</span>'
        "</div>"
        "<div>"
        '<div class="rationale-label">Why this score</div>'
        f'<p class="rationale">{rationale}</p>'
        f'<div class="score-meta">{meta_line}</div>'
        "</div></div>"
    )

    parts: list[str] = [
        '<div class="report-wrap">',
        "<h2>Design report</h2>",
        '<p class="report-subtitle">'
        "Synthesized from five specialist agents — visual, UX, accessibility, "
        "brand, market. Recommendations are ranked by impact-over-effort and "
        "cite the agent finding that produced them."
        "</p>",
        hero,
    ]

    # --- per-axis breakdown bars ------------------------------------- #
    if report.score_breakdown or any(
        getattr(report, k) is not None for k in ("visual", "ux", "accessibility", "brand", "market")
    ):
        parts.append("<h3>Per-axis breakdown</h3>")
        parts.append(_breakdown_bars(report.score_breakdown))

    # --- agent run status -------------------------------------------- #
    if report.analysis_status:
        parts.append("<h3>Specialist status</h3>")
        parts.append(_status_grid(report.analysis_status))

    # --- quick wins -------------------------------------------------- #
    parts.append(_quick_wins_block(report))

    # --- strengths --------------------------------------------------- #
    parts.append("<h3>Top strengths</h3>")
    parts.append(_ul([e(s) for s in report.top_strengths] or ["No strengths returned yet."]))

    # --- prioritized recommendations -------------------------------- #
    parts.append("<h3>Prioritized recommendations</h3>")
    if report.top_recommendations:
        items = "".join(f"<li>{_recommendation_card(r)}</li>" for r in report.top_recommendations)
        parts.append(f'<ul class="rec-list">{items}</ul>')
    else:
        parts.append(_ul(["No recommendations returned yet."]))

    # --- collapsible specialist details ------------------------------ #
    if report.visual:
        body = _ul(
            [
                f"Layout: {e(report.visual.layout or 'Not returned')}",
                f"Hierarchy: {e(report.visual.hierarchy or 'Not returned')}",
                f"Density score: {report.visual.density_score:.1f}/100",
            ]
        )
        parts.append(
            f'<details class="specialist"><summary>Visual analysis</summary>'
            f'<div class="body">{body}</div></details>'
        )
    if report.ux:
        ux_items = [
            f"Cognitive load score: {report.ux.cognitive_load_score:.1f}/100",
            f"Heuristic violations: {len(report.ux.heuristic_violations)}",
            f"Friction points: {len(report.ux.friction_points)}",
        ]
        parts.append(
            '<details class="specialist"><summary>UX critique</summary>'
            f'<div class="body">{_ul(ux_items)}</div></details>'
        )
    if report.accessibility:
        ac = report.accessibility
        pass_text = (
            "pass"
            if ac.contrast_pass is True
            else "needs review" if ac.contrast_pass is False else "not measured"
        )
        ac_items = [
            f"Contrast: {pass_text}",
            f"WCAG findings: {len(ac.wcag_findings)}",
            (
                f"Estimated min touch target: {ac.est_min_touch_target_px}px"
                if ac.est_min_touch_target_px is not None
                else "Touch target: not measured"
            ),
        ]
        parts.append(
            '<details class="specialist"><summary>Accessibility</summary>'
            f'<div class="body">{_ul(ac_items)}</div></details>'
        )
    if report.brand:
        br = report.brand
        br_items = [
            f"Consistency score: {br.consistency_score:.1f}/100",
            f"Color drift: {e(br.color_drift or 'not measured')}",
            f"Type drift: {e(br.type_drift or 'not measured')}",
            f"Component drift: {e(br.component_drift or 'not measured')}",
        ]
        parts.append(
            '<details class="specialist"><summary>Brand consistency</summary>'
            f'<div class="body">{_ul(br_items)}</div></details>'
        )
    if report.market:
        mk = report.market
        mk_items = [f"Trend: {e(t)}" for t in (mk.trends or [])] or ["No trends returned."]
        if mk.competitors:
            mk_items.append("Competitors cited: " + ", ".join(e(c.name) for c in mk.competitors))
        parts.append(
            '<details class="specialist"><summary>Market signals</summary>'
            f'<div class="body">{_ul(mk_items)}</div></details>'
        )

    parts.append("</div>")
    return "\n".join(parts)


def _gallery_query(deps: AgentDeps, query: str, k: int = 12) -> list[tuple[str, str]]:
    """Return Gradio gallery tuples from the configured retriever."""
    refs = deps.retriever.retrieve_by_text(query, k=k)
    return [(_resolve_reference_path(r.image_path), f"{r.id} - {r.score:.2f}") for r in refs]


def _references_for_report(
    report: DesignReport | dict[str, Any] | None,
) -> tuple[list[tuple[str, str]], str]:
    """Build the References-tab payload from the LATEST analysis.

    Replaces the old "search-only" References tab with a contextual one:
    when the user runs an analysis, this surfaces exactly the references
    the agents looked at — local image RAG hits the brand agent retrieved
    plus the URLs the market agent cited. Search is still available below
    as a supplementary tool.
    """
    if report is None:
        return (
            [],
            """
<div class="reference-card">
  <h3>References used in this run</h3>
  <p>Run an analysis from the <b>Analyze</b> tab. The references the
  brand and market agents consulted will appear here automatically.</p>
</div>
""",
        )

    rep: DesignReport = DesignReport.model_validate(report) if isinstance(report, dict) else report
    report = rep

    gallery_items: list[tuple[str, str]] = []
    if report.brand and report.brand.comparable_refs:
        for ref in report.brand.comparable_refs:
            try:
                resolved = _resolve_reference_path(ref.image_path)
            except Exception:
                resolved = ref.image_path
            label = f"{ref.id} · {ref.score:.2f}"
            gallery_items.append((resolved, label))

    market_lines: list[str] = []
    if report.market and report.market.competitors:
        for c in report.market.competitors:
            market_lines.append(
                f"<li><b>{html.escape(c.name)}</b> "
                f'— <a href="{html.escape(c.url)}" target="_blank" rel="noopener">{html.escape(c.url)}</a> '
                f'<br><span class="muted">{html.escape(c.why_relevant)}</span></li>'
            )
    if report.market and report.market.citations:
        for url in report.market.citations[:5]:
            market_lines.append(
                f'<li><a href="{html.escape(url)}" target="_blank" rel="noopener">{html.escape(url)}</a></li>'
            )

    market_block = ""
    if market_lines:
        market_block = (
            '<div class="reference-card" style="margin-top:14px">'
            "<h3>Market references cited in this run</h3>"
            f'<ul>{"".join(market_lines)}</ul>'
            "</div>"
        )

    gallery_msg = (
        f"{len(gallery_items)} brand reference(s) retrieved by the brand agent."
        if gallery_items
        else "Brand agent retrieved no comparable references for this screen "
        "(empty index or off-domain). Search below to add context."
    )
    summary_html = (
        '<div class="reference-card">'
        "<h3>References used in this run</h3>"
        f"<p>{html.escape(gallery_msg)}</p>"
        "</div>"
        f"{market_block}"
    )
    return gallery_items, summary_html


def _reference_query_from_ui(query: str) -> tuple[list[tuple[str, str]], str]:
    """Search local image refs (LanceDB) and live web refs (Tavily/DuckDuckGo)."""
    _fresh_settings()
    if not query.strip():
        return (
            [],
            """
<div class="reference-card">
  <h3>Similar references</h3>
  <p>Type a pattern or product category.</p>
</div>
""",
        )

    gallery_items: list[tuple[str, str]] = []
    local_files = _local_reference_file_count()
    vector_rows = _vector_row_count()

    if vector_rows > 0:
        try:
            deps = build_default_deps(use_real=True)
            gallery_items = _gallery_query(deps, query, k=12)
        except Exception as e:
            log.warning("references: retriever failed: %s", e)

    status = (
        f"{vector_rows} indexed references from {local_files} local files."
        if gallery_items
        else "No indexed matches yet. Add images to the reference dir and run make ingest."
    )

    web_refs = _format_web_references(query, use_real=True)
    return (
        gallery_items,
        f"""
<div class="reference-card">
  <h3>Similar references</h3>
  <p>{html.escape(status)}</p>
</div>
{web_refs}
""",
    )


def main() -> None:
    """Build and launch the Gradio Blocks app."""
    cfg = _fresh_settings()
    try:
        import gradio as gr  # type: ignore[import-not-found]
    except ImportError as e:
        raise SystemExit(
            "gradio is not installed. Run: pip install -r requirements/person-e-ui.txt"
        ) from e

    with gr.Blocks(title="Design Analysis Suite") as demo, gr.Column(elem_classes=["app-shell"]):
        gr.HTML(
            """
<section class="hero-band">
  <span class="eyebrow">Multimodal review</span>
  <h1>Design Analysis Suite</h1>
  <p>
    Upload a screen for a fast visual, UX, accessibility, brand, and market review.
    Five specialist agents critique in parallel and ship a single prioritized report.
  </p>
  <div class="chip-row">
    <span class="chip">Visual</span>
    <span class="chip">UX</span>
    <span class="chip">Accessibility</span>
    <span class="chip">Brand</span>
    <span class="chip">Market</span>
  </div>
</section>
"""
        )

        gr.HTML(
            """
<div class="steps">
  <div class="step accent-teal"  data-step="1"><b>Upload</b><span>A clear PNG or JPG of the screen you want reviewed.</span></div>
  <div class="step accent-coral" data-step="2"><b>Add context</b><span>Audience, brand voice, market &mdash; helps every agent.</span></div>
  <div class="step accent-gold"  data-step="3"><b>Review</b><span>Score, prioritized fixes, and per-specialist evidence.</span></div>
</div>
"""
        )

        report_state = gr.State(value=None)

        with gr.Tabs():
            with gr.Tab("Analyze"):
                with gr.Row():
                    with gr.Column(scale=3, elem_classes=["upload-panel"]):
                        gr.Markdown(
                            """
### Analyze a screen
Upload a screenshot. Add context if useful.
"""
                        )
                        image_in = gr.File(label="Design screenshot", file_types=["image"])
                        instructions_in = gr.Textbox(
                            label="Context",
                            placeholder="Audience, brand, market, or goal",
                            lines=3,
                        )
                        run_btn = gr.Button("Run analysis", variant="primary")
                        gr.Markdown(
                            "_Mode is read from `.env` — "
                            f"currently **{'real APIs' if _default_real_mode() else 'offline fakes'}**. "
                            "Toggle `USE_REAL` in `.env` to switch._"
                        )
                        gr.Examples(
                            examples=[
                                [
                                    "src/fakes/fixtures/sample.png",
                                    "audience: Indian retail banking users; brand: trustworthy, modern, accessible",
                                ]
                            ],
                            inputs=[image_in, instructions_in],
                            label="Try the bundled sample",
                        )

                    with gr.Column(scale=2):
                        gr.HTML(
                            """
<div class="guide-card accent-teal">
  <h3>Good inputs</h3>
  <ul>
    <li>Readable UI screenshots</li>
    <li>Dashboards, onboarding, checkout</li>
    <li>Full screens work best</li>
  </ul>
</div>
<br>
<div class="guide-card accent-coral">
  <h3>Output</h3>
  <ul>
    <li>Score and key strengths</li>
    <li>Prioritized fixes</li>
    <li>Evidence and references</li>
  </ul>
</div>
"""
                        )

                log_out = gr.HTML(
                    _status_message(
                        "Ready",
                        "Upload a screenshot. The mode (real APIs vs fakes) is read from .env.",
                    )
                )
                with gr.Accordion("Raw structured report", open=False):
                    json_out = gr.JSON(label="DesignReport JSON", elem_classes=["json-holder"])

                run_btn.click(
                    fn=on_run,
                    inputs=[image_in, instructions_in],
                    outputs=[log_out, json_out, report_state],
                )

            with gr.Tab("Report"):
                report_view = gr.HTML(render_report(None))
                report_state.change(fn=render_report, inputs=[report_state], outputs=[report_view])

            with gr.Tab("References"):
                gr.HTML(
                    """
<div class="guide-card accent-teal">
  <h3>References</h3>
  <p>The top section shows references the agents <b>actually used</b> in
  the latest analysis (brand RAG + market citations). Use search below to
  add supplementary references from the local index and the live web.</p>
</div>
"""
                )

                run_refs_gallery = gr.Gallery(
                    columns=4,
                    height=320,
                    label="Brand references retrieved by THIS run",
                    elem_classes=["reference-gallery"],
                )
                run_refs_notes = gr.HTML(
                    """
<div class="reference-card">
  <h3>References used in this run</h3>
  <p>Run an analysis from the <b>Analyze</b> tab. The references the
  brand and market agents consulted will appear here automatically.</p>
</div>
"""
                )

                gr.HTML(
                    """
<div class="guide-card accent-coral" style="margin-top:18px">
  <h3>Search for more references</h3>
  <p>Optional supplementary search across the local index and live web.</p>
</div>
"""
                )
                with gr.Row(elem_classes=["reference-panel"]):
                    q = gr.Textbox(
                        label="Search",
                        placeholder="fintech dashboard, onboarding, checkout",
                        scale=4,
                    )
                    ref_btn = gr.Button("Search", variant="primary", scale=1)
                gallery = gr.Gallery(
                    columns=4,
                    height=380,
                    label="Search results",
                    elem_classes=["reference-gallery"],
                )
                reference_notes = gr.HTML(
                    """
<div class="reference-card">
  <h3>Search results</h3>
  <p>Type a pattern or product category and press Search.</p>
</div>
"""
                )
                q.submit(
                    fn=_reference_query_from_ui,
                    inputs=[q],
                    outputs=[gallery, reference_notes],
                )
                ref_btn.click(
                    fn=_reference_query_from_ui,
                    inputs=[q],
                    outputs=[gallery, reference_notes],
                )

                # Auto-populate the run-references section whenever a new
                # report lands in `report_state`. This is the contextual
                # link that ties the References tab to the current run.
                report_state.change(
                    fn=_references_for_report,
                    inputs=[report_state],
                    outputs=[run_refs_gallery, run_refs_notes],
                )

            with gr.Tab("Settings"):
                gr.HTML(
                    f"""
<div class="settings-card">
  <h3>Runtime settings</h3>
  <p><b>Real API key loaded</b>: {_has_openrouter_key()}</p>
  <p><b>USE_REAL in .env</b>: {cfg.use_real}</p>
  <p><b>Tavily key loaded</b>: {bool(cfg.tavily_api_key)}</p>
  <p><b>Local reference images</b>: {_local_reference_file_count()}</p>
  <p><b>Indexed reference rows</b>: {_vector_row_count()}</p>
  <p><b>Reports</b>: {cfg.report_dir}</p>
</div>
"""
                )

    demo.queue().launch(
        server_name="127.0.0.1",
        server_port=int(os.environ.get("GRADIO_SERVER_PORT", "7860")),
        theme=gr.themes.Soft(),
        css=APP_CSS,
        js=FORCE_LIGHT_THEME_JS,
        head=FORCE_LIGHT_THEME_HEAD,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
