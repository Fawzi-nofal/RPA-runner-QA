
from __future__ import annotations
import os, random, string
from typing import Optional, Any, Dict, Sequence

def _parse_viewport(v) -> Optional[Sequence[int]]:
    if not v: return None
    if isinstance(v, (list, tuple)) and len(v) == 2: return [int(v[0]), int(v[1])]
    if isinstance(v, str):
        parts = [p.strip() for p in v.lower().replace("×", "x").split("x")]
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            return [int(parts[0]), int(parts[1])]
    return None

def _rand_token(n: int = 6) -> str:
    return "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(n))

def load_options(scenario: dict, env=os.environ) -> Dict[str, Any]:
    opts = scenario.get("options", {}) or {}
    headful_env = env.get("HEADFUL") == "1"

    viewport = _parse_viewport(opts.get("viewport") or env.get("VIEWPORT", "1366x900"))
    browsers = opts.get("browsers") or None
    if isinstance(browsers, str):
        browsers = [b.strip().lower() for b in browsers.split(",") if b.strip()]

    variables = dict(scenario.get("variables", {}) or {})
    if isinstance(opts.get("variables"), dict):
        variables.update(opts["variables"])
    # הזרקת ${RAND} כברירת מחדל – שימושי לחשבונות/שמות ייחודיים
    variables.setdefault("RAND", _rand_token())

    proxy = None
    if env.get("PROXY_SERVER"):
        proxy = {"server": env["PROXY_SERVER"]}
        if env.get("PROXY_USERNAME"): proxy["username"] = env["PROXY_USERNAME"]
        if env.get("PROXY_PASSWORD"): proxy["password"] = env["PROXY_PASSWORD"]

    return {
        "headful": bool(opts.get("headful", headful_env)),
        "browser": str(opts.get("browser", env.get("BROWSER", "chromium"))).lower(),
        "timeout_ms": int(opts.get("timeout_ms", env.get("TIMEOUT_MS", 7000))),
        "speed_s": float(opts.get("speed_s", env.get("SPEED_S", 0.0))),
        "tracing": bool(opts.get("tracing", env.get("TRACING", "1") == "1")),
        "video": bool(opts.get("video", env.get("VIDEO", "0") == "1")),
        "viewport": viewport,
        "user_agent": opts.get("user_agent") or env.get("USER_AGENT"),
        "browsers": browsers,
        "variables": variables,
        "slow_mo": int(opts.get("slow_mo", env.get("SLOW_MO", 0))),
        "proxy": proxy,
    }

def resolve_url(base_url: Optional[str], sel: str) -> str:
    if not sel: return ""
    if sel.startswith("http://") or sel.startswith("https://"):
        return sel
    if base_url:
        if sel.startswith("/"): return base_url.rstrip("/") + sel
        return base_url.rstrip("/") + "/" + sel.lstrip("/")
    return sel

def substitute_vars(value: Any, variables: dict):
    if not isinstance(value, str): return value
    out = value
    for k, v in (variables or {}).items():
        out = out.replace(f"${{{k}}}", str(v))
    return out
