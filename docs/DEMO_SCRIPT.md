# Demo script — 90 seconds, every second budgeted

Open with `make demo` (ingest → run-a → ui). The judges should see the report
before you start talking.

| Time | What you do | What you say |
|---|---|---|
| 0:00 – 0:15 | Slide 1: "Designers ship faster when they get a structured second opinion." | Frame the problem: a multi-agent reviewer that produces typed JSON, not advice paragraphs. |
| 0:15 – 0:30 | Drag `dashboard.png` into the Gradio "Analyze" tab; click **Run**. | "Five specialists run in parallel: visual, UX, accessibility, brand, market. They share one image RAG corpus." |
| 0:30 – 1:00 | Pivot to the LangSmith trace tab while agents run. | "Five spans starting at the same x-coordinate — that's the parallel fan-out. Latency is `max`, not `sum`." |
| 1:00 – 1:20 | Switch to Gradio "Report" tab. Read the top three recommendations. | "Top 3 strengths, top 5 prioritized recommendations with effort vs impact, every Finding has Evidence and a Fix." |
| 1:20 – 1:30 | Switch to Claude Code (or any MCP-compatible coding agent). Run `analyze_design` over MCP from the chat panel. | "Same graph, called from a coding agent over MCP. Sprint 4 in action." |

## Pre-show checklist (T-30 minutes)

- [ ] `make test` is green from a fresh `.venv`.
- [ ] `make ingest` against 10-20 hand-picked references.
- [ ] `make run-a` against your demo screenshot — verify it produces a sane
      report (cache will warm so the live demo is sub-second).
- [ ] LangSmith trace project named "design-analysis-suite-demo".
- [ ] `mcp.json` snippet pasted into your MCP client's config (e.g. Claude Code's `~/.config/claude-code/mcp.json`); restart the client.
- [ ] Backup laptop with the same `.env` and the same cache.

## Backup if WiFi dies

Toggle the "Use real APIs" checkbox OFF in Settings tab → graph runs against
fakes. Demo still works, talking points unchanged.
