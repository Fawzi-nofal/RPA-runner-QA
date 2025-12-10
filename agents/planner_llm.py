from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional
import json, re

from .ollama_client import chat_simple  # משתמשים ב-/api/generate

SYSTEM_PROMPT = (
    "You are a senior QA planner. Given a website model (buttons, inputs, links), "
    "output ONLY a STRICT JSON array of tests. Each test has: "
    "{id, name, steps:[{type, selector?, value?, continue_on_fail?, retry?, retry_delay_ms?}]}. "
    "Use Playwright-like selectors (text=..., [data-test='...'], input[placeholder='...']). "
    "Prefer non-destructive flows and add basic assertions with wait_for_selector. "
    "NO prose, NO markdown fences, ONLY JSON array."
)

USER_PROMPT_TEMPLATE = """
SITE_MODEL_JSON:
{graph}

VARS (use if relevant):
{vars}

Guidelines:
- Start with goto '/' if path is unclear.
- Insert 'wait_for_selector' before 'click'/'fill'.
- Use variables like ${{USERNAME}}, ${{PASSWORD}} if a login flow is detected.
- Keep each test 5-12 steps.
- Return ONLY a JSON array (no markdown fences).
"""

# ---------- helpers ----------

def _read_graph_lenient(graph_path: Path) -> Dict[str, Any]:
    """
    קורא את הגרף בסלחנות:
    - אם הקובץ לא קיים/ריק → מחזיר גרף מינימלי.
    - אם נכתב עם BOM → מנסה utf-8-sig.
    - אם יש שגיאת JSON → נופל חזרה לגרף מינימלי.
    """
    try:
        txt = graph_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {"pages": [{"url": "/"}]}
    except UnicodeDecodeError:
        # ייתכן שנכתב עם BOM ע״י PowerShell
        try:
            txt = graph_path.read_text(encoding="utf-8-sig")
        except Exception:
            return {"pages": [{"url": "/"}]}
    try:
        obj = json.loads(txt) if txt.strip() else {"pages": [{"url": "/"}]}
        if not isinstance(obj, dict):
            return {"pages": [{"url": "/"}]}
        return obj
    except Exception:
        return {"pages": [{"url": "/"}]}

def _coerce_suite(raw: str) -> Optional[List[Dict[str, Any]]]:
    """
    מנקה קודמות מרובדות/גדרות מרקר, מוציא את המערך, ומיישר שדות
    כדי שה-runner יקבל: steps[].type/selector/value וכו'.
    """
    try:
        s = raw.strip()
        # ניקוי fences אם המודל בכל זאת החזיר
        if s.startswith("```"):
            s = re.sub(r"^```[a-zA-Z0-9]*", "", s).strip()
            if s.endswith("```"):
                s = s[:-3].strip()

        # נחלץ את המערך הראשון התקין בטקסט
        m = re.search(r"\[.*\]", s, re.S)
        if not m:
            return None
        arr = json.loads(m.group(0))
        if not isinstance(arr, list):
            return None

        # הקשחות לצעדים + המרות קלות
        for t in arr:
            if not isinstance(t, dict) or "steps" not in t or not isinstance(t["steps"], list):
                return None
            for step in t["steps"]:
                # חלק מהמודלים מחזירים action במקום type
                if "type" not in step and "action" in step:
                    step["type"] = step.pop("action")

                tt = step.get("type")
                if tt in {"click", "fill"}:
                    step.setdefault("continue_on_fail", True)
                if tt == "wait_for_selector":
                    step.setdefault("value", "visible")
                if tt in {"click", "wait_for_selector"}:
                    step.setdefault("retry", 1)
                    step.setdefault("retry_delay_ms", 400)
        return arr
    except Exception:
        return None

def _prune_graph_for_prompt(graph: Dict[str, Any], max_pages: int = 8) -> Dict[str, Any]:
    """
    מצמצם את הגרף כדי לא להפיל את השרת: לוקח עד max_pages ומשאיר רק שדות חשובים.
    """
    pages = graph.get("pages") or graph.get("nodes") or []
    pages = pages[:max_pages] if isinstance(pages, list) else []
    if not pages:
        return {"pages": [{"url": "/"}]}
    slim_pages = []
    for p in pages:
        model = (p or {}).get("model") or (p or {}).get("snapshot") or {}
        slim = {
            "url": p.get("url") or p.get("path") or "/",
            "buttons": model.get("buttons") or [],
            "inputs": model.get("inputs") or [],
            "links": model.get("links") or [],
            "texts": model.get("texts") or [],
        }
        slim_pages.append(slim)
    return {"pages": slim_pages or [{"url": "/"}]}

# ---------- public ----------

def build_suite_from_graph_llm(
    graph_path: Path,
    variables: Optional[Dict[str, Any]] = None,
    model: str = "llama3",
    temperature: float = 0.2
) -> Optional[List[Dict[str, Any]]]:

    graph = _read_graph_lenient(graph_path)
    variables = variables or {}

    pruned = _prune_graph_for_prompt(graph)  # צמצום
    graph_min = json.dumps(pruned, ensure_ascii=False, separators=(",", ":"))  # מיניפיקציה
    vars_min = json.dumps(variables, ensure_ascii=False, separators=(",", ":"))

    user_prompt = USER_PROMPT_TEMPLATE.format(graph=graph_min, vars=vars_min)
    full_prompt = SYSTEM_PROMPT + "\n\n" + user_prompt

    content = chat_simple(full_prompt, model=model, temperature=temperature)
    if not content:
        return None

    return _coerce_suite(content)
