# core/runner.py
from __future__ import annotations
import time
from pathlib import Path
from typing import Any, Dict
from core.config import load_options, substitute_vars
from core.browser import open_browser, close_browser
from core.reporting import start_run, record_step, attach_artifact, finalize_run, finish_step
from core.schema import validate_scenario
from core.exceptions import ActionExecutionError
from utils.yaml_io import read_yaml  # אם תבטל YAML – אפשר להסיר
from core.actions import ACTION_REGISTRY  # וודא שקיים: goto/fill/click/press/select_option/wait/wait_for_selector/screenshot/assert_*

def _parse_wait_value(v: Any) -> float:
    if isinstance(v, (int, float)): return float(v)
    if isinstance(v, str) and v.strip().lower().endswith("ms"):
        n = v.strip()[:-2].strip()
        return float(n)/1000.0 if n.isdigit() else 0.5
    try:
        return float(v)
    except Exception:
        return 0.5

def execute_step(page, step, *, base_url, options, results, variables, reports_dir: Path):
    # include (string or list)
    if "include" in step:
        include = step["include"]
        include_files = include if isinstance(include, list) else [include]
        for inc in include_files:
            inc_path = Path(inc)
            sub = read_yaml(inc_path)
            validate_scenario(sub)
            sub_base = sub.get("base_url", base_url)
            run_steps(page, sub["steps"], base_url=sub_base, options=options, results=results,
                      variables=variables, reports_dir=reports_dir)
        return

    t = (step.get("type") or "").strip().lower()
    selector = step.get("selector")
    value = substitute_vars(step.get("value"), variables)
    cont = bool(step.get("continue_on_fail", False))
    rec = record_step(results, len(results["steps"]) + 1, t, selector, value)
    rec["continue_on_fail"] = cont
    started_ts = time.time()

    # retry loop
    max_retry = int(step.get("retry", 0))
    delay_ms = int(step.get("retry_delay_ms", 500))
    attempt = 0
    last_err = None

    while attempt <= max_retry:
        try:
            if t == "wait":
                time.sleep(_parse_wait_value(value))
            else:
                action = ACTION_REGISTRY.get(t)
                if not action:
                    raise ActionExecutionError(f"Unknown step type: {t}")
                action(
                    page,
                    selector=selector,
                    value=value,
                    base_url=base_url,
                    timeout_ms=options["timeout_ms"],
                    reports_dir=reports_dir,
                )
            finish_step(rec, "passed", None)
            last_err = None
            break
        except Exception as e:
            last_err = e
            attempt += 1
            if attempt > max_retry:
                # נכשל סופית
                if cont:
                    finish_step(rec, "failed-continued", str(e))
                    # ניסיון להוסיף צילום לכישלון חלקי
                    try:
                        shot = reports_dir / f"fail_{int(time.time())}.png"
                        page.screenshot(path=str(shot))
                        attach_artifact(results, "screenshot", shot)
                    except Exception:
                        pass
                    return  # ממשיכים לריצה
                # לא להמשיך – זרוק חריגה
                finish_step(rec, "failed", str(e))
                raise
            # המתנה בין ניסיונות
            time.sleep(max(0, delay_ms) / 1000.0)

    # האטה בין צעדים אם הוגדר
    if options.get("speed_s", 0) > 0:
        time.sleep(options["speed_s"])

def run_steps(page, steps, *, base_url, options, results, variables, reports_dir: Path):
    for step in steps:
        execute_step(page, step, base_url=base_url, options=options,
                     results=results, variables=variables, reports_dir=reports_dir)

def run_scenario(path: Path) -> int:
    scenario = read_yaml(path)
    validate_scenario(scenario)

    name = scenario.get("name", path.stem)
    base_url = scenario.get("base_url") or scenario.get("url")
    base_options = load_options(scenario)

    # משתנים זמינים – כולל RAND שהוזרק ב-load_options
    variables = dict(base_options.get("variables") or {})

    browsers = base_options.get("browsers")
    if isinstance(browsers, (list, tuple)) and browsers:
        rc = 0
        for bname in browsers:
            print(f"\n=== Running on browser: {bname} ===\n")
            opts = dict(base_options); opts["browser"] = str(bname).lower()
            reports_dir = Path("reports") / opts["browser"]
            rc = max(rc, _run_single(name, base_url, scenario["steps"], opts, reports_dir, variables))
        return rc
    else:
        reports_dir = Path("reports")
        return _run_single(name, base_url, scenario["steps"], base_options, reports_dir, variables)

def _run_single(name: str, base_url: str, steps, options, reports_dir: Path, variables: Dict[str, Any]) -> int:
    started = time.time()
    reports_dir.mkdir(parents=True, exist_ok=True)
    dl_dir = reports_dir / "downloads"; dl_dir.mkdir(parents=True, exist_ok=True)
    vid_dir = reports_dir / "video";     vid_dir.mkdir(parents=True, exist_ok=True)

    p, browser, ctx, page = open_browser(
        options["browser"],
        options["headful"],
        record_video_dir=(vid_dir if options.get("video") else None),
        downloads_dir=dl_dir,
        viewport=options.get("viewport"),
        user_agent=options.get("user_agent"),
        timeout_ms=options.get("timeout_ms"),
        slow_mo=options.get("slow_mo", 0),
        proxy=options.get("proxy"),
    )

    results = start_run(name, base_url, options["browser"], options["headful"])

    if options.get("tracing"):
        try:
            ctx.tracing.start(screenshots=True, snapshots=True, sources=True)
        except Exception:
            pass

    try:
        run_steps(page, steps, base_url=base_url, options=options, results=results,
                  variables=variables, reports_dir=reports_dir)
        status, error = "passed", None
        print("\n✅ Scenario completed successfully!\n")
        return_code = 0
    except Exception as e:
        status, error = "failed", str(e)
        shot = reports_dir / f"fail_{int(time.time())}.png"
        try:
            page.screenshot(path=str(shot))
            attach_artifact(results, "screenshot", shot)
            print(f"❌ Failure. Screenshot: {shot}")
        except Exception:
            pass
        return_code = 1
    finally:
        if options.get("tracing"):
            try:
                trace_path = reports_dir / "trace.zip"
                ctx.tracing.stop(path=str(trace_path))
                attach_artifact(results, "trace", trace_path)
            except Exception:
                pass
        close_browser(p, browser, ctx)
        finalize_run(results, status, error, started, reports_dir)

    return return_code
