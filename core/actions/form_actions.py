from playwright.sync_api import TimeoutError as PWTimeoutError
import time
# ===== עוזרים פנימיים =====
def _pick_visible_candidate(page, selector: str, timeout_ms: int):
    """
    בוחר את האלמנט הראשון שהוא גם נראה (visible) וגם לא-disabled.
    אם יש מודאל/דיאלוג פתוח – נותן לו עדיפות.
    """
    half = max(500, int(timeout_ms * 0.5))

    # 1) בתוך מודאל/דיאלוג (אם קיים) — עדיפות
    modal = page.locator("[role=dialog]:visible, .modal.show, .modal:visible").first
    if modal.count():
        cand = modal.locator(f"{selector}:visible").filter(has_not=page.locator(":disabled")).first
        try:
            cand.wait_for(state="visible", timeout=half)
            return cand
        except Exception:
            pass

    # 2) גלובלי: נראה ולא disabled
    cand = page.locator(f"{selector}:visible").filter(has_not=page.locator(":disabled")).first
    try:
        cand.wait_for(state="visible", timeout=half)
        return cand
    except Exception:
        pass

    # 3) מוצא ראשון — כרשת ביטחון
    return page.locator(selector).first


def action_fill(page, *, selector, value, timeout_ms=7000, **_):
    """
    ממלא ערך בשדה. בוחר את האלמנט הנכון לפי 'נראה' ו'לא disabled',
    עם עדיפות לשדות בתוך מודאל/דיאלוג.
    """
    target = _pick_visible_candidate(page, selector, timeout_ms)
    # ודא שהאלמנט באמת ניתן לעריכה (יש מצבים של contenteditable וכו')
    try:
        target.fill(str(value), timeout=timeout_ms)
        return
    except PWTimeoutError as e:
        # נסה fallback של type() (לפעמים fill נכשל על רכיבים מותאמים)
        target.click(timeout=min(1000, timeout_ms))
        page.keyboard.type(str(value), delay=10)
    except Exception:
        # ניסיון אחרון: evaluate ל-set value (לשדות input בלבד)
        try:
            target.evaluate("(el, v) => { el.value = v; el.dispatchEvent(new Event('input', {bubbles:true})); }", str(value))
            return
        except Exception as e:
            raise


def action_wait_for_selector(page, *, selector, value="visible", timeout_ms=7000, **_):
    """
    value: one of 'visible' | 'attached' | 'hidden' | 'detached'
    """
    state = str(value).strip().lower()
    if state not in ("visible", "attached", "hidden", "detached"):
        state = "visible"
    page.locator(selector).first.wait_for(state=state, timeout=timeout_ms)


def action_screenshot(page, *, value, **_):
    page.screenshot(path=str(value))
def action_select_option(page, *, selector, value, timeout_ms=7000, **_):
    """
    בוחר ערך מתוך אלמנט <select>.
    מאפשר בחירה לפי value או לפי label (טקסט מוצג).
    """
    try:
        dropdown = page.locator(selector)
        dropdown.wait_for(state="visible", timeout=timeout_ms)

        # ננסה קודם לפי value
        try:
            dropdown.select_option(value=value)
        except Exception:
            # אם לא הצליח לפי value, ננסה לפי label
            dropdown.select_option(label=value)
    except PWTimeoutError:
        raise AssertionError(f"Timeout waiting for select element: {selector}")
    except Exception as e:
        raise AssertionError(f"Failed to select option {value!r} for {selector}: {e}")
    

def action_wait(page, *, value=None, **_):
    """
    השהיה יזומה לצורך דיבוג או המתנה בין פעולות.
    value יכול להיות:
      - מספר (שניות)
      - מחרוזת עם 'ms' (מילישניות)
    """
    if value is None:
        delay_s = 1.0
    elif isinstance(value, (int, float)):
        delay_s = float(value)
    elif isinstance(value, str):
        v = value.strip().lower()
        if v.endswith("ms"):
            delay_s = float(v.replace("ms", "")) / 1000.0
        else:
            delay_s = float(v)
    else:
        raise ValueError(f"Invalid value for wait: {value!r}")

    print(f"[wait] ⏳ Waiting {delay_s:.2f} seconds...")
    time.sleep(delay_s)
