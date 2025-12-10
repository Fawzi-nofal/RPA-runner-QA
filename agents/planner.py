from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional
import json, re

LOGIN_WORDS  = ["login", "log in", "signin", "sign in", "כניסה", "התחבר", "התחברות", "היכנס"]
SIGNUP_WORDS = ["signup", "sign up", "register", "create account", "הרשמה", "הירשם", "צור חשבון"]

# מילים שעדיף לא ללחוץ עליהן אוטומטית (תקלות/פעולות הרסניות)
SAFE_SKIP_WORDS = [
    "logout", "sign out", "delete", "remove", "unsubscribe",
    "cancel", "close account", "pay", "purchase", "buy", "checkout",
    "delete account", "erase", "refund"
]

# ----------------------------- selector helpers -----------------------------

def _pick_selector(node: Dict[str, Any]) -> Optional[str]:
    if not node:
        return None
    cand: List[str] = []
    s = (node.get("selector") or "").strip()
    if s:
        cand.append(s)

    def add(val: Optional[str], fmt):
        if val:
            v = str(val).strip()
            if v:
                cand.append(fmt(v))

    add(node.get("id"),          lambda v: f"#{v}")
    add(node.get("dataTest"),    lambda v: f"[data-test='{v}']")
    add(node.get("name"),        lambda v: f"[name='{v}']")
    add(node.get("placeholder"), lambda v: f"input[placeholder='{v}']")

    txt = (node.get("text") or "").strip()
    if txt:
        cand.append(f"text={txt}")
        cand.append(f"text=/{re.escape(txt)}/i")

    for c in cand:
        if c:
            return c
    return None

def _looks_like_username(inp: Dict[str, Any]) -> bool:
    parts = [inp.get("name"), inp.get("placeholder"), inp.get("label")]
    probe = " ".join(str(p) for p in parts if p).lower()
    return any(w in probe for w in ["user", "username", "email", "login", "mail", "שם משתמש", "מייל"])

def _first_button_with(words: List[str], buttons: List[Dict[str,Any]]) -> Optional[Dict[str,Any]]:
    for b in (buttons or []):
        txt = (b.get("text") or "").lower()
        if any(w in txt for w in words):
            return b
    return None

def _first_input_by_type(model: Dict[str,Any], t: str) -> Optional[Dict[str,Any]]:
    return next((i for i in (model.get("inputs") or []) if (i.get("type") or "").lower() == t), None)

def _first_username_input(model: Dict[str,Any]) -> Optional[Dict[str,Any]]:
    ins = model.get("inputs") or []
    for i in ins:
        if _looks_like_username(i) and (i.get("type", "").lower() != "password"):
            return i
    for i in ins:
        if (i.get("type", "").lower() != "password"):
            return i
    return None

# ----------------------------- probes -----------------------------

def _success_probe(_model_after_login: Dict[str, Any]) -> str:
    # ברירת מחדל טובה ל-SauceDemo; אפשר לשפר דומיין-ספציפי בהמשך
    return "text=Products"

# ----------------------------- clickables for exploration -----------------------------

def _clickable_candidates(page_model: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    מוצא כפתורים/לינקים בטוחים ללחיצה (מסנן ביטויים הרסניים).
    מחזיר [{"selector": str, "label": str}, ...]
    """
    out: List[Dict[str, Any]] = []
    btns = page_model.get("buttons") or []
    links = page_model.get("links") or []

    def push(item: Dict[str, Any]):
        sel = _pick_selector(item)
        if not sel:
            return
        txt = (item.get("text") or "").lower().strip()
        if any(w in txt for w in SAFE_SKIP_WORDS):
            return
        out.append({"selector": sel, "label": item.get("text") or ""})

    for b in btns:
        push(b)
    for a in links:
        push(a)

    # הסרת כפילויות לפי selector
    seen = set()
    uniq: List[Dict[str, Any]] = []
    for it in out:
        if it["selector"] in seen:
            continue
        uniq.append(it)
        seen.add(it["selector"])
    return uniq

# ----------------------------- finders -----------------------------

def _find_login_triplet(model: Dict[str,Any]) -> Optional[Dict[str,str]]:
    pw   = _first_input_by_type(model, "password")
    user = _first_username_input(model)
    if not (pw and user):
        return None
    btns = model.get("buttons") or []
    btn  = _first_button_with(LOGIN_WORDS + ["submit","continue"], btns) or (btns[0] if btns else None)
    if not btn:
        return None
    su = _pick_selector(user); sp = _pick_selector(pw); sb = _pick_selector(btn)
    if not (su and sp and sb):
        return None
    return {"user": su, "pass": sp, "submit": sb}

def _find_login_trigger(model: Dict[str,Any]) -> Optional[str]:
    btn = _first_button_with(LOGIN_WORDS, model.get("buttons") or [])
    return _pick_selector(btn) if btn else None

def _find_signup_trigger(model: Dict[str,Any]) -> Optional[str]:
    btn = _first_button_with(SIGNUP_WORDS, model.get("buttons") or [])
    return _pick_selector(btn) if btn else None

def _find_signup_fields(model: Dict[str,Any]) -> Optional[Dict[str,str]]:
    user = _first_username_input(model)
    pw   = _first_input_by_type(model, "password")
    if not (user and pw):
        return None
    su = _pick_selector(user); sp = _pick_selector(pw)
    if not (su and sp):
        return None
    btn = _first_button_with(SIGNUP_WORDS + ["submit","continue","create"], model.get("buttons") or [])
    sb = _pick_selector(btn) if btn else None
    return {"user": su, "pass": sp, "submit": sb or "button"}

# ----------------------------- suites -----------------------------

def _suite_login(model: Dict[str,Any]) -> Optional[List[Dict[str,Any]]]:
    tri = _find_login_triplet(model)
    if not tri:
        return None
    steps = [
        {"type": "goto", "selector": "/"},
        {"type": "wait_for_selector", "selector": tri["user"], "value": "visible"},
        {"type": "wait_for_selector", "selector": tri["pass"], "value": "visible"},
        {"type": "fill", "selector": tri["user"], "value": "${USERNAME}"},
        {"type": "fill", "selector": tri["pass"], "value": "${PASSWORD}"},
        {"type": "click", "selector": tri["submit"]},
        {"type": "wait_for_selector", "selector": _success_probe(model), "value": "visible"},
        {"type": "screenshot", "value": "after_login.png"},
    ]
    return [{"id": "AI-AUTO-LOGIN", "name": "AI Login (page)", "steps": steps}]

def _suite_signup_then_login(model: Dict[str,Any]) -> Optional[List[Dict[str,Any]]]:
    trig = _find_signup_trigger(model)
    if not trig:
        return None
    fields = _find_signup_fields(model) or {
        "user": "input[type=text], input[type=email], [name*=user i], [name*=email i]",
        "pass": "input[type=password], [name*=pass i]",
        "submit": "text=/sign up|register|create/i"
    }
    login_trig = _find_login_trigger(model)
    login_trip = _find_login_triplet(model)

    steps: List[Dict[str,Any]] = [{"type": "goto", "selector": "/"}]
    # Sign up
    steps += [
        {"type": "wait_for_selector", "selector": trig, "value": "visible"},
        {"type": "click", "selector": trig},
        {"type": "wait_for_selector", "selector": fields["user"], "value": "visible"},
        {"type": "wait_for_selector", "selector": fields["pass"], "value": "visible"},
        {"type": "fill", "selector": fields["user"], "value": "${NEW_USERNAME}"},
        {"type": "fill", "selector": fields["pass"], "value": "${NEW_PASSWORD}"},
        {"type": "click", "selector": fields["submit"], "continue_on_fail": True},
        {"type": "wait", "value": "1200ms", "continue_on_fail": True},
        {"type": "screenshot", "value": "after_signup.png", "continue_on_fail": True},
    ]
    # Login (modal/page)
    if login_trig:
        steps += [
            {"type": "click", "selector": login_trig},
            {"type": "wait_for_selector", "selector": "input[type=text], input[type=email], #loginusername, [name*=user i], [name*=email i]", "value": "visible"},
            {"type": "wait_for_selector", "selector": "input[type=password], #loginpassword, [name*=pass i]", "value": "visible"},
            {"type": "fill", "selector": "input[type=text], input[type=email], #loginusername, [name*=user i], [name*=email i]", "value": "${NEW_USERNAME}"},
            {"type": "fill", "selector": "input[type=password], #loginpassword, [name*=pass i]", "value": "${NEW_PASSWORD}"},
            {"type": "click", "selector": "#logInModal .modal-footer .btn-primary", "continue_on_fail": True},
        ]
    elif login_trip:
        steps += [
            {"type": "wait_for_selector", "selector": login_trip["user"], "value": "visible"},
            {"type": "wait_for_selector", "selector": login_trip["pass"], "value": "visible"},
            {"type": "fill", "selector": login_trip["user"], "value": "${NEW_USERNAME}"},
            {"type": "fill", "selector": login_trip["pass"], "value": "${NEW_PASSWORD}"},
            {"type": "click", "selector": login_trip["submit"]},
        ]
    else:
        steps += [{"type": "screenshot", "value": "no_login_path.png"}]
        return [{"id": "AI-AUTO-SIGNUP", "name": "AI Sign up (no login path found)", "steps": steps}]

    steps += [
        {"type": "wait_for_selector", "selector": _success_probe(model), "value": "visible", "continue_on_fail": True},
        {"type": "screenshot", "value": "after_login.png"}
    ]
    return [{"id": "AI-AUTO-SIGNUP-LOGIN", "name": "AI Sign up → Login", "steps": steps}]

def _suite_smoke(model: Dict[str,Any]) -> List[Dict[str,Any]]:
    btns = model.get("buttons") or []
    cta  = _first_button_with(["start","get started","shop","products","continue","צפה","לרכישה","התחל"], btns) or (btns[0] if btns else None)
    steps = [{"type": "goto", "selector": "/"}]
    if cta:
        sel = _pick_selector(cta)
        if sel:
            steps += [
                {"type": "wait_for_selector", "selector": sel, "value": "visible"},
                {"type": "click", "selector": sel},
                {"type": "screenshot", "value": "after_cta.png"},
            ]
    else:
        steps += [{"type": "screenshot", "value": "home.png"}]
    return [{"id": "AI-AUTO-SMOKE", "name": "AI Smoke (from graph)", "steps": steps}]

def _suite_browse_clickables(graph: Dict[str, Any], limit_per_page: int = 5) -> List[Dict[str, Any]]:
    """
    תרחישי חקר אוטומטיים: עד N קליקים בטוחים בכל דף, עם המתנה וצילום.
    """
    pages = graph.get("pages") or graph.get("nodes") or []
    out: List[Dict[str, Any]] = []

    for idx, page in enumerate(pages):
        model = page.get("model") or page.get("snapshot") or {}
        path = page.get("path") or page.get("urlPath") or "/"
        cands = _clickable_candidates(model)[:limit_per_page]
        if not cands:
            continue

        steps: List[Dict[str, Any]] = [{"type": "goto", "selector": path}]
        for c in cands:
            safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", c['label'] or "element")
            steps += [
                {"type": "wait_for_selector", "selector": c["selector"], "value": "visible", "retry": 1, "retry_delay_ms": 400, "continue_on_fail": True},
                {"type": "click", "selector": c["selector"], "continue_on_fail": True},
                {"type": "wait", "value": "800ms", "continue_on_fail": True},
                {"type": "screenshot", "value": f"clicked_{safe_name}.png", "continue_on_fail": True},
            ]
        out.append({
            "id": f"AI-AUTO-BROWSE-{idx+1}",
            "name": f"AI Browse clickables on page #{idx+1}",
            "steps": steps
        })
    return out

# ----------------------------- public API -----------------------------

def build_suite_from_graph(graph_path: Path) -> List[Dict[str, Any]]:
    graph = json.loads(Path(graph_path).read_text(encoding="utf-8"))
    pages = graph.get("pages") or graph.get("nodes") or []
    if not pages:
        raise RuntimeError("Empty site_graph.json (no pages/nodes)")
    home  = pages[0]
    model = home.get("model") or home.get("snapshot") or {}

    # 1) Login
    suite = _suite_login(model)
    if suite:
        return suite + _suite_browse_clickables(graph, limit_per_page=5)

    # 2) Signup → Login
    suite = _suite_signup_then_login(model)
    if suite:
        return suite + _suite_browse_clickables(graph, limit_per_page=5)

    # 3) Smoke + חקר
    smoke = _suite_smoke(model)
    browse = _suite_browse_clickables(graph, limit_per_page=5)
    return smoke + browse

def plan_to_file(graph_path: Path, suite_path: Path) -> Path:
    suite = build_suite_from_graph(graph_path)
    suite_path.parent.mkdir(parents=True, exist_ok=True)
    suite_path.write_text(json.dumps(suite, ensure_ascii=False, indent=2), encoding="utf-8")
    return suite_path

def generate_suite_from_graph(graph_path: Path, out_suite_path: Path) -> List[Dict[str, Any]]:
    suite = build_suite_from_graph(graph_path)
    out_suite_path.parent.mkdir(parents=True, exist_ok=True)
    out_suite_path.write_text(json.dumps(suite, ensure_ascii=False, indent=2), encoding="utf-8")
    return suite
