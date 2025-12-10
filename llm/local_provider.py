# llm/local_provider.py
from __future__ import annotations
from typing import Dict, Any, List


# -------- Helpers -------------------------------------------------------------

def _norm(text: str | None) -> str:
    return (text or "").strip().lower()


def _contains_any(s: str, words: List[str]) -> bool:
    s = _norm(s)
    return any(w in s for w in words)


# -------- Public API ----------------------------------------------------------

def summarize_observation(obs: Dict[str, Any]) -> str:
    """
    מחזיר סיכום קצר של מצב הדף מתוך Observation (dict / model_dump()).
    ללא מודל חיצוני – מבוסס היוריסטיקות.
    """
    url = obs.get("url", "")
    title = obs.get("title") or ""
    flags = obs.get("flags", {}) or {}
    has_pw = bool(flags.get("has_password"))
    modal = bool(flags.get("modal_open"))
    has_form = bool(flags.get("has_form"))
    err = (flags.get("error_banner") or "")[:120]
    suc = (flags.get("success_banner") or "")[:120]

    parts = [f"URL: {url}"]
    if title:
        parts.append(f"Title: {title}")
    parts.append(f"Form: {has_form}, Password: {has_pw}, Modal: {modal}")
    if err:
        parts.append(f"Error: {err}")
    if suc:
        parts.append(f"Success: {suc}")

    # כמה טקסטים בולטים
    vt = obs.get("visible_texts") or []
    if vt:
        sample = "; ".join(vt[:3])
        parts.append(f"Texts: {sample[:160]}")

    return " | ".join(parts)


def suggest_next_actions(obs: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    מחזיר רשימת צעדים מוצעים (steps בסגנון המערכת) בהתאם ל-Observation.
    זהו 'LLM' מקומי פשוט שמבוסס כללים – מספיק להתחלה, ואפשר להחליף בהמשך ל-OpenAI.
    """
    steps: List[Dict[str, Any]] = []
    flags = obs.get("flags", {}) or {}
    has_pw = bool(flags.get("has_password"))
    modal = bool(flags.get("modal_open"))
    buttons = obs.get("buttons") or []
    inputs = obs.get("inputs") or []
    texts = " ".join(obs.get("visible_texts") or [])

    # 1) אם יש מודאל פתוח – ננסה לאתר שדות לוגין ולשלוח.
    if modal and has_pw:
        steps += [
            {"type": "wait_for_selector", "selector": "input[type='password']", "value": "visible", "continue_on_fail": True},
            {"type": "wait_for_selector", "selector": "input[type='text'], input[type='email'], [name*='user' i]", "value": "visible", "continue_on_fail": True},
            {"type": "fill", "selector": "input[type='text'], input[type='email'], [name*='user' i]", "value": "${USERNAME}", "continue_on_fail": True},
            {"type": "fill", "selector": "input[type='password']", "value": "${PASSWORD}", "continue_on_fail": True},
            {"type": "click", "value": "log in", "continue_on_fail": True},
        ]
        return steps

    # 2) אם יש שדה סיסמה אך אין מודאל – כנראה דף לוגין / הרשמה.
    if has_pw:
        steps += [
            {"type": "wait_for_selector", "selector": "input[type='password']", "value": "visible", "continue_on_fail": True},
            {"type": "wait_for_selector", "selector": "input[type='text'], input[type='email'], [name*='user' i]", "value": "visible", "continue_on_fail": True},
            {"type": "fill", "selector": "input[type='text'], input[type='email'], [name*='user' i]", "value": "${USERNAME}", "continue_on_fail": True},
            {"type": "fill", "selector": "input[type='password']", "value": "${PASSWORD}", "continue_on_fail": True},
            {"type": "click", "value": "login", "continue_on_fail": True},
        ]
        return steps

    # 3) אם אין סיסמה – נחפש CTA עיקרי (start / continue / sign up / add to cart ...)
    cta_texts = ["start", "get started", "continue", "submit", "sign up", "register",
                 "buy", "add to cart", "checkout", "התחל", "המשך", "שלח", "הרשמה", "קנה", "הוסף לעגלה"]
    for b in buttons:
        t = b.get("text") or ""
        if _contains_any(t, cta_texts):
            sel = b.get("selector_hint") or (f"text=/{t}/i" if t else None)
            if sel:
                steps += [
                    {"type": "wait_for_selector", "selector": sel, "value": "visible", "continue_on_fail": True},
                    {"type": "click", "selector": sel, "continue_on_fail": True},
                ]
                break

    # 4) אם זוהתה שגיאה – נציע צילום מסך
    if flags.get("error_banner"):
        steps.append({"type": "screenshot", "value": "error_banner.png"})

    # ברירת מחדל – צילום מסך קצר
    if not steps:
        steps.append({"type": "screenshot", "value": "page.png"})

    return steps


def generate_suite_from_graph_local(graph: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    מחזיר רשימת TestCases בסיסית מגרף האתר (fallback ל-planner).
    """
    nodes = graph.get("nodes") or []
    suite: List[Dict[str, Any]] = []

    if not nodes:
        return suite

    # TC1: Smoke – כניסה לעמוד הבית + צילום
    suite.append({
        "id": "LOCAL-SMOKE",
        "name": "Smoke: open home",
        "steps": [
            {"type": "goto", "selector": "/"},
            {"type": "screenshot", "value": "home.png"},
        ],
    })

    # TC2: אם בעמוד הבית יש רמזים ללוגין/סיינאפ – ניצור תרחיש כללי
    home_snap = (nodes[0].get("snapshot") if isinstance(nodes[0], dict) else None) or {}
    vt = " ".join((home_snap.get("visible_texts") or []))
    if _contains_any(vt, ["login", "log in", "signin", "sign in"]) or home_snap.get("flags", {}).get("has_password"):
        suite.append({
            "id": "LOCAL-LOGIN",
            "name": "Login (generic)",
            "steps": [
                {"type": "goto", "selector": "/"},
                {"type": "click", "value": "login", "continue_on_fail": True},
                {"type": "wait_for_selector", "selector": "input[type='text'], input[type='email'], [name*='user' i]", "value": "visible", "continue_on_fail": True},
                {"type": "wait_for_selector", "selector": "input[type='password']", "value": "visible", "continue_on_fail": True},
                {"type": "fill", "selector": "input[type='text'], input[type='email'], [name*='user' i]", "value": "${USERNAME}", "continue_on_fail": True},
                {"type": "fill", "selector": "input[type='password']", "value": "${PASSWORD}", "continue_on_fail": True},
                {"type": "click", "value": "login", "continue_on_fail": True},
                {"type": "screenshot", "value": "after_login.png"},
            ],
        })
    elif _contains_any(vt, ["signup", "sign up", "register", "create account"]):
        suite.append({
            "id": "LOCAL-SIGNUP",
            "name": "Sign up (generic)",
            "steps": [
                {"type": "goto", "selector": "/"},
                {"type": "click", "value": "sign up", "continue_on_fail": True},
                {"type": "wait_for_selector", "selector": "input[type='text'], input[type='email'], [name*='user' i]", "value": "visible", "continue_on_fail": True},
                {"type": "wait_for_selector", "selector": "input[type='password']", "value": "visible", "continue_on_fail": True},
                {"type": "fill", "selector": "input[type='text'], input[type='email'], [name*='user' i]", "value": "demo_${RAND}", "continue_on_fail": True},
                {"type": "fill", "selector": "input[type='password']", "value": "demo_${RAND}", "continue_on_fail": True},
                {"type": "click", "value": "sign up", "continue_on_fail": True},
                {"type": "screenshot", "value": "after_signup.png"},
            ],
        })

    return suite
