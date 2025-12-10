# core/reporting.py
from __future__ import annotations
import time, html
from pathlib import Path
from typing import Dict, Any, List, Optional

def start_run(name: str, base_url: Optional[str], browser: str, headful: bool) -> Dict[str, Any]:
    return {
        "name": name,
        "base_url": base_url,
        "browser": browser,
        "headful": headful,
        "started": time.time(),
        "steps": [],
        "artifacts": [],
        "status": "running",
        "error": None,
    }

def record_step(results: Dict[str, Any], idx: int, t: str, selector: Optional[str], value: Any) -> Dict[str, Any]:
    rec = {
        "index": idx,
        "type": t,
        "selector": selector,
        "value": value,
        "started": time.time(),
        "ended": None,
        "status": "running",
        "error": None,
        "continue_on_fail": False,
    }
    results["steps"].append(rec)
    return rec

def finish_step(rec: Dict[str, Any], status: str = "passed", error: Optional[str] = None) -> None:
    rec["ended"] = time.time()
    rec["status"] = status
    if error:
        rec["error"] = error

def attach_artifact(results: Dict[str, Any], kind: str, path: Path) -> None:
    results["artifacts"].append({"type": kind, "path": str(path)})

def _status_badge(s: str) -> str:
    color = {"passed":"#16a34a","failed":"#dc2626","failed-continued":"#f59e0b","running":"#2563eb"}.get(s, "#6b7280")
    return f'<span style="background:{color};color:#fff;border-radius:8px;padding:2px 8px;font-size:12px">{html.escape(s)}</span>'

def finalize_run(results: Dict[str, Any], status: str, error: Optional[str], started_ts: float, reports_dir: Path) -> None:
    results["status"] = status
    results["error"]  = error
    total_sec = time.time() - started_ts

    # TXT
    txt_lines = [
        f"Run: {results['name']}",
        f"Base URL: {results.get('base_url')}",
        f"Browser: {results['browser']} | Headful: {results['headful']}",
        f"Status: {results['status']}",
        f"Error: {results['error'] or '-'}",
        f"Duration: {total_sec:.2f}s",
        "",
        "Steps:"
    ]
    for s in results["steps"]:
        dur = (s["ended"] or time.time()) - s["started"]
        txt_lines.append(f"  [{s['index']}] {s['type']}  ({dur:.2f}s)  -> {s['status']}  sel={s.get('selector')!r} val={s.get('value')!r}")
        if s.get("error"):
            txt_lines.append(f"       error: {s['error']}")
    txt_path = reports_dir / "report_summary.txt"
    txt_path.write_text("\n".join(txt_lines), encoding="utf-8")

    # HTML
    html_path = reports_dir / "report_summary.html"
    html_rows = []
    for s in results["steps"]:
        dur = (s["ended"] or time.time()) - s["started"]
        html_rows.append(
            "<tr>"
            f"<td>{s['index']}</td>"
            f"<td><code>{html.escape(str(s['type']))}</code></td>"
            f"<td><code>{html.escape(str(s.get('selector') or ''))}</code></td>"
            f"<td><code>{html.escape(str(s.get('value') or ''))}</code></td>"
            f"<td>{dur:.2f}s</td>"
            f"<td>{_status_badge(s['status'])}</td>"
            f"<td>{html.escape(s.get('error') or '')}</td>"
            "</tr>"
        )

    art_rows = []
    for a in results["artifacts"]:
        p = html.escape(a["path"])
        t = html.escape(a["type"])
        link = f'<a href="{p}" target="_blank">{p}</a>'
        thumb = ""
        if p.lower().endswith((".png",".jpg",".jpeg",".gif")):
            thumb = f'<div><img src="{p}" style="max-width:320px;border:1px solid #ddd;margin-top:4px"/></div>'
        art_rows.append(f"<tr><td>{t}</td><td>{link}{thumb}</td></tr>")

    html_doc = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"/>
<title>RPA Report – {html.escape(results['name'])}</title>
<style>
 body{{font-family:Arial,Helvetica,sans-serif;margin:24px}}
 table{{border-collapse:collapse;width:100%}}
 th,td{{border:1px solid #e5e7eb;padding:8px;text-align:left}}
 th{{background:#f3f4f6}}
 code{{background:#f3f4f6;padding:1px 4px;border-radius:4px}}
 .meta div{{margin-bottom:4px}}
</style>
</head><body>
<h2>RPA Report – {html.escape(results['name'])}</h2>
<div class="meta">
  <div><b>Base URL:</b> {html.escape(str(results.get('base_url') or ''))}</div>
  <div><b>Browser:</b> {html.escape(results['browser'])} | <b>Headful:</b> {results['headful']}</div>
  <div><b>Status:</b> {_status_badge(results['status'])}</div>
  <div><b>Error:</b> {html.escape(results['error'] or '-')}</div>
  <div><b>Duration:</b> {total_sec:.2f}s</div>
</div>

<h3>Steps</h3>
<table>
  <thead><tr><th>#</th><th>Type</th><th>Selector</th><th>Value</th><th>Time</th><th>Status</th><th>Error</th></tr></thead>
  <tbody>
    {''.join(html_rows)}
  </tbody>
</table>

<h3>Artifacts</h3>
<table>
  <thead><tr><th>Type</th><th>Path</th></tr></thead>
  <tbody>
    {''.join(art_rows) if art_rows else '<tr><td colspan="2">No artifacts</td></tr>'}
  </tbody>
</table>
</body></html>"""
    html_path.write_text(html_doc, encoding="utf-8")
