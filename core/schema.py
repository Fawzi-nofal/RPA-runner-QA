# core/schema.py
from __future__ import annotations
from typing import Any, Dict, List

def _require(d: Dict[str, Any], key: str, msg: str):
    if key not in d or d[key] in (None, ""):
        raise ValueError(msg)

def _is_ms_string(v: Any) -> bool:
    return isinstance(v, str) and v.strip().lower().endswith("ms") and v.strip()[:-2].strip().isdigit()

def validate_scenario(s: Dict[str, Any]) -> None:
    if not isinstance(s, dict):
        raise ValueError("Scenario must be a dict")
    steps = s.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("Scenario must have a non-empty 'steps' list")

    for i, st in enumerate(steps, start=1):
        if not isinstance(st, dict):
            raise ValueError(f"Step {i} must be a dict")
        if "include" in st:
            continue  # include יכול להיות מחרוזת או רשימה – נבדוק בזמן ריצה
        t = (st.get("type") or "").strip().lower()
        if not t:
            raise ValueError(f"Step {i} missing 'type'")

        if t in {"goto","fill","click","press","select_option","wait_for_selector"}:
            # עבור אלו, selector לרוב נדרש (מלבד click-by-intent שבו נשתמש ב-value)
            if t != "click":
                _require(st, "selector", f"Step {i} '{t}' requires 'selector'")
        if t == "fill":
            _require(st, "value", f"Step {i} 'fill' requires 'value'")
        if t == "press":
            _require(st, "value", f"Step {i} 'press' requires 'value'")

        if t == "wait":
            # מאפשר גם "500ms" וגם מספר (שניות)
            if "value" not in st:
                raise ValueError(f"Step {i} 'wait' requires 'value'")
            v = st["value"]
            if not (isinstance(v, (int, float)) or _is_ms_string(v)):
                raise ValueError(f"Step {i} 'wait' value must be number (seconds) or string like '500ms'")

        if t == "screenshot":
            # value אופציונלי – נקצה שם ברירת מחדל בזמן ריצה
            pass

        if t.startswith("assert_"):
            # assert_url דורש value בלבד; אחרים לרוב דורשים selector + value/טקסט
            if t == "assert_url":
                _require(st, "value", f"Step {i} 'assert_url' requires 'value'")

        # שדות אופציונליים
        if "retry" in st and not isinstance(st["retry"], int):
            raise ValueError(f"Step {i} 'retry' must be int")
        if "retry_delay_ms" in st and not isinstance(st["retry_delay_ms"], int):
            raise ValueError(f"Step {i} 'retry_delay_ms' must be int")
        if "continue_on_fail" in st and not isinstance(st["continue_on_fail"], bool):
            raise ValueError(f"Step {i} 'continue_on_fail' must be bool")
