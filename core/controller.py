from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List
import json, time, traceback, inspect

from core.browser import open_browser, close_browser
from core import reporting
from core.runner import run_steps
from agents.planner_llm import build_suite_from_graph_llm

REPORTS_DIR = Path("reports/ai")
GRAPH_PATH  = REPORTS_DIR / "site_graph.json"
SUITE_PATH  = REPORTS_DIR / "test_suite.json"


# ---------- helpers ----------

def _ensure_graph_exists(base_url: str) -> None:
    """
    אם אין site_graph.json — ניצור קובץ דיפולטי מינימלי ונמשיך.
    זה מונע עצירה למשתמש שלא רוצה להתעסק עם 'גרפים'.
    """
    if GRAPH_PATH.exists():
        return
    GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)
    default_graph = {"pages": [{"url": "/"}]}
    GRAPH_PATH.write_text(json.dumps(default_graph, ensure_ascii=False), encoding="utf-8")
    print(f"[INFO] No graph found — created minimal default at {GRAPH_PATH}")


def _fallback_suite(url: str, variables: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    סוויטה מינימלית שלא תלויה ב-LLM, תואמת ל-runner (steps[].type).
    עבור SauceDemo: לוגין + וידוא שהגענו ל-inventory ע"י טקסט 'Products'.
    """
    username = variables.get("USERNAME", "standard_user")
    password = variables.get("PASSWORD", "secret_sauce")

    return [{
        "name": "login-basic",
        "steps": [
            {"type": "goto", "url": url},
            {"type": "wait_for_selector", "selector": "input#user-name", "value": "visible"},
            {"type": "fill", "selector": "input#user-name", "value": username},
            {"type": "fill", "selector": "input#password", "value": password},
            {"type": "click", "selector": "input#login-button"},
            {"type": "wait_for_selector", "selector": "text=Products", "value": "visible"}
        ]
    }]


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------- NORMALIZATION FIX ----------

ALLOWED_TYPES = {
    "goto", "click", "fill", "press", "select_option",
    "wait", "wait_for_selector", "screenshot",
    "assert_text", "assert_url_contains"
}

def _normalize_suite(suite: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """מיישר את הסוויטה לפורמט שה-runner מכיר (steps[].type בלבד)."""
    norm: List[Dict[str, Any]] = []
    for test in suite or []:
        steps: List[Dict[str, Any]] = []
        for st in test.get("steps", []) or []:
            t = (st.get("type") or st.get("action") or "").strip().lower()

            # השלמות חכמות
            if not t and "url" in st:
                t = "goto"
            if not t and "selector" in st and "value" in st:
                t = "fill"
            if t == "assert_url":
                t = "assert_url_contains"

            st["type"] = t

            # ברירות מחדל בסיסיות
            if t in {"click", "fill", "wait_for_selector"}:
                st.setdefault("retry", 1)
                st.setdefault("retry_delay_ms", 400)
            if t == "wait_for_selector":
                st.setdefault("value", "visible")

            steps.append(st)
        norm.append({"name": test.get("name", "test"), "steps": steps})
    return norm


def _call_run_steps_safely(
    steps: List[Dict[str, Any]],
    *,
    url: str,
    options: Dict[str, Any],
    results_obj: Any,
    page=None,
    ctx=None,
) -> None:
    """
    מריץ run_steps כשהוא שולח רק פרמטרים נתמכים.
    כולל סינון צעדים חסרי type.
    """
    sig = inspect.signature(run_steps)
    supported = set(sig.parameters.keys())

    kwargs: Dict[str, Any] = {}
    if "base_url" in supported:
        kwargs["base_url"] = url
    elif "url" in supported:
        kwargs["url"] = url

    if "options" in supported:
        kwargs["options"] = options

    if "results" in supported:
        kwargs["results"] = results_obj
    elif "reporter" in supported:
        kwargs["reporter"] = results_obj

    if "reports_dir" in supported:
        kwargs["reports_dir"] = REPORTS_DIR
    if "variables" in supported:
        kwargs["variables"] = options.get("variables", {})
    if "context" in supported:
        kwargs["context"] = {"page": page, "context": ctx}
    if "page" in supported:
        kwargs["page"] = page
    if "ctx" in supported:
        kwargs["ctx"] = ctx

    # סינון צעדים חסרי type
    clean_steps: List[Dict[str, Any]] = []
    for st in steps or []:
        t = (st.get("type") or "").strip().lower()
        if not t:
            print(f"[WARN] skipping step with no type: {st}")
            continue
        clean_steps.append(st)

    if "steps" in supported:
        run_steps(steps=clean_steps, **kwargs)
    else:
        run_steps(clean_steps, **kwargs)


# ---------- public API ----------

def run_explore(_options: Dict[str, Any]) -> None:
    _ensure_graph_exists(_options.get("url", ""))


def run_suite(options: Dict[str, Any]) -> None:
    """
    AI-only: בונה סוויטה דרך Ollama ומריץ אותה.
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    url          = options.get("url") or ""
    browser_name = options.get("browser", "chromium")
    headful      = bool(options.get("headful"))
    video        = bool(options.get("video"))
    timeout_ms   = int(options.get("timeout_ms") or 20000)
    viewport     = options.get("viewport") or (1366, 900)
    model_name   = options.get("ollama_model", "llama3")

    # variables עם ברירות מחדל
    variables = dict(options.get("variables") or {})
    variables.setdefault("USERNAME", "standard_user")
    variables.setdefault("PASSWORD", "secret_sauce")
    options["variables"] = variables

    _ensure_graph_exists(url)

    # 1) תכנון בעזרת LLM
    print(f"[AI Planner/LLM] Building suite via Ollama (model={model_name})…")
    suite: List[Dict[str, Any]] | None = None
    try:
        suite = build_suite_from_graph_llm(GRAPH_PATH, variables=variables, model=model_name)
    except Exception as e:
        print(f"[WARN] LLM planner failed: {e!r}")

    # 2) פולבק אם אין סוויטה
    if not suite or not isinstance(suite, list):
        print("[WARN] LLM did not produce a valid suite. Using fallback plan.")
        suite = _fallback_suite(url, variables)

    # נרמול כדי למנוע Unknown step type
    suite = _normalize_suite(suite)

    _write_json(SUITE_PATH, suite)
    print(f"[AI Planner] Suite ready: {SUITE_PATH}")

    if suite and suite[0].get("steps"):
        first = suite[0]["steps"][0]
        print(f"[DEBUG] first step → type={first.get('type')} selector={first.get('selector')} url={first.get('url')}")

    # 3) דוח
    results = reporting.start_run(name="AI LLM Suite", base_url=url,
                                  browser=browser_name, headful=headful)
    started_ts = time.time()

    # 4) פתיחת דפדפן
    p, browser, ctx, page = open_browser(
        browser_name=browser_name,
        headful=headful,
        record_video_dir=(REPORTS_DIR / "video") if video else None,
        downloads_dir=(REPORTS_DIR / "downloads"),
        viewport=viewport,
        timeout_ms=timeout_ms,
        slow_mo=int(options.get("slow_mo") or 0),
        proxy=options.get("proxy"),
        extra_context_options=None,
        user_agent=options.get("user_agent"),
    )

    try:
        # 5) הרצה בפועל
        for test in suite:
            steps = test.get("steps", [])
            _call_run_steps_safely(
                steps,
                url=url,
                options=options,
                results_obj=results,
                page=page,
                ctx=ctx,
            )

        reporting.finalize_run(results, status="passed",
                               error=None, started_ts=started_ts, reports_dir=REPORTS_DIR)

    except Exception as e:
        reporting.finalize_run(results, status="failed",
                               error=str(e), started_ts=started_ts, reports_dir=REPORTS_DIR)
        print("[controller] run failed:\n", traceback.format_exc())
        raise
    finally:
        close_browser(p, browser, ctx)


def run_ai(options: Dict[str, Any]) -> None:
    run_suite(options)
