import argparse
from core.controller import run_suite  # AI-only

def _parse_viewport(s: str):
    s = str(s).lower().replace(" ", "")
    if "x" in s:
        w, h = s.split("x", 1)
        return int(w), int(h)
    raise argparse.ArgumentTypeError("viewport must be like 1366x900")

def _parse_vars(items):
    out = {}
    if not items: return out
    for it in items:
        if "=" not in it:
            raise argparse.ArgumentTypeError(f"--var expects KEY=VALUE, got '{it}'")
        k, v = it.split("=", 1)
        out[k.strip()] = v
    return out

def build_argparser():
    ap = argparse.ArgumentParser(description="AI-Only Runner (Ollama)")
    ap.add_argument("--url", required=True)
    ap.add_argument("--browser", default="chromium", choices=("chromium","firefox","webkit"))
    ap.add_argument("--headful", action="store_true")
    ap.add_argument("--video", action="store_true")
    ap.add_argument("--timeout-ms", type=int, default=20000)
    ap.add_argument("--viewport", type=_parse_viewport, default=_parse_viewport("1366x900"))
    ap.add_argument("--slow-mo", type=int, default=0)
    ap.add_argument("--proxy", default=None)
    ap.add_argument("--user-agent", dest="user_agent", default=None)
    ap.add_argument("--var", action="append")
    ap.add_argument("--ollama-model", default="llama3")
    ap.add_argument("--no-llm", action="store_true", help="Run without LLM (use fallback plan)")
    return ap

def main():
    args = build_argparser().parse_args()
    options = {
        "url": args.url,
        "browser": args.browser,
        "headful": bool(args.headful),
        "video": bool(args.video),
        "timeout_ms": int(args.timeout_ms),
        "viewport": args.viewport,
        "slow_mo": int(args.slow_mo),
        "proxy": args.proxy,
        "user_agent": args.user_agent,
        "variables": {"USERNAME": "standard_user", "PASSWORD": "secret_sauce"},
        "ollama_model": args.ollama_model,
        "force_plan": True, # מבחינתנו לא רלוונטי, אבל לא מזיק
        "no_llm": bool(args.no_llm)
    }
    options["variables"].update(_parse_vars(args.var))
    run_suite(options)

if __name__ == "__main__":
    main()
