"""Render a one page Customer Value Review as standalone HTML (print to PDF from a browser)."""

from __future__ import annotations

from datetime import date
from html import escape

from .metrics import HealthResult, ItemStats

COLORS = {"Healthy": "#1E7F4F", "Watch": "#B7791F", "At Risk": "#B42318"}


def _fmt(value, suffix: str = "") -> str:
    return "n/a" if value is None else f"{value}{suffix}"


def _stat_rows(s: ItemStats) -> str:
    rows = [
        ("Total logged", s.total), ("Open", s.open), ("Overdue", s.overdue),
        ("Open without a due date", s.missing_due),
        ("Average days to close", _fmt(s.avg_days_to_close)),
        ("Oldest open item (days)", _fmt(s.oldest_open_days)),
    ]
    return "".join(f"<tr><td>{escape(k)}</td><td class='n'>{escape(str(v))}</td></tr>" for k, v in rows)


def render(customer: str, project: str, rfis: ItemStats, subs: ItemStats, health: HealthResult,
           recs: list[str], plan: list[tuple[str, str]], data_note: str, today: date) -> str:
    color = COLORS[health.grade]
    deductions = "".join(f"<li>{escape(r)}: minus {p}</li>" for r, p in health.deductions) \
        or "<li>No deductions</li>"
    rec_items = "".join(f"<li>{escape(r)}</li>" for r in recs)
    plan_rows = "".join(f"<tr><td class='p'>{escape(a)}</td><td>{escape(b)}</td></tr>" for a, b in plan)
    owners = sorted({**rfis.open_by_owner}.items(), key=lambda kv: -kv[1])[:3]
    owner_line = ", ".join(f"{escape(n)} ({c})" for n, c in owners) or "n/a"

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Customer Value Review: {escape(customer)}</title>
<style>
  @page {{ size: letter; margin: 0.5in; }}
  body {{ font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; color: #1d2433;
         max-width: 7.5in; margin: 24px auto; font-size: 13px; line-height: 1.45; }}
  h1 {{ font-size: 20px; margin: 0; }} h2 {{ font-size: 14px; margin: 18px 0 6px; color: #1F3A5F;
         border-bottom: 1px solid #d8dde6; padding-bottom: 3px; }}
  .sub {{ color: #5b6475; }}
  .top {{ display: flex; justify-content: space-between; align-items: center; gap: 16px; }}
  .score {{ text-align: center; border: 2px solid {color}; border-radius: 10px; padding: 8px 16px; }}
  .score b {{ display: block; font-size: 30px; color: {color}; line-height: 1.1; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
  table {{ width: 100%; border-collapse: collapse; }} td {{ padding: 3px 4px; border-bottom: 1px solid #eef0f4; }}
  td.n {{ text-align: right; font-variant-numeric: tabular-nums; }} td.p {{ width: 110px; font-weight: 600; }}
  ol, ul {{ margin: 4px 0 0 18px; padding: 0; }} li {{ margin-bottom: 4px; }}
  .foot {{ margin-top: 18px; font-size: 11px; color: #5b6475; border-top: 1px solid #d8dde6; padding-top: 6px; }}
</style></head><body>
<div class="top">
  <div><h1>Customer Value Review</h1>
  <div class="sub">{escape(customer)} | {escape(project)} | {today:%B %d, %Y}</div></div>
  <div class="score"><b>{health.score}</b>{escape(health.grade)}</div>
</div>

<h2>Why the score is {health.score}</h2>
<ul>{deductions}</ul>

<div class="grid">
  <div><h2>RFIs</h2><table>{_stat_rows(rfis)}</table>
  <div class="sub" style="margin-top:4px">Ball in court on open RFIs: {owner_line}</div></div>
  <div><h2>Submittals</h2><table>{_stat_rows(subs)}</table></div>
</div>

<h2>Top recommendations</h2>
<ol>{rec_items}</ol>

<h2>30 / 60 / 90 day adoption plan</h2>
<table>{plan_rows}</table>

<div class="foot">{escape(data_note)}</div>
</body></html>"""
