from core.config import resolve_url
import re
from playwright.sync_api import TimeoutError as PWTimeoutError

# ===============================================================
#  ACTIONS: Navigation & Input
# ===============================================================

def action_goto(page, *, selector, base_url=None, timeout_ms=7000, **_):
    url = resolve_url(base_url, selector)
    page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)


def action_press(page, *, selector, value, timeout_ms=7000, **_):
    page.locator(selector).press(str(value), timeout=timeout_ms)


# ===============================================================
#  LOGIN / SIGN-IN HELPERS
# ===============================================================

LOGIN_WORDS = list(dict.fromkeys([
    # English
    "login", "log in", "sign in", "signin", "sign-in", "continue", "submit", "ok", "confirm",
    # Hebrew
    "כניסה", "התחברות", "התחבר", "היכנס", "שלח", "המשך", "אישור"
]))

REGISTER_WORDS = [
    "sign up", "signup", "register", "registration", "join now",
    "הרשמה", "צור חשבון", "הירשם", "הצטרף"
]


def _find_password_field(page):
    sel = (
        "input[type='password'], "
        "input[autocomplete='current-password'], "
        "input[name*='pass' i], "
        "input[id*='pass' i]"
    )
    pw = page.locator(sel).first
    try:
        pw.wait_for(state="visible", timeout=1500)
        return pw
    except PWTimeoutError:
        return None
    except Exception:
        return None


def _find_username_field_near(page, pw):
    if not pw:
        return None

    candidates = [
        "input[name*=user i]", "input[id*=user i]", "input[name*=email i]", "input[id*=email i]",
        "input[type=email]", "input[name*=login i]", "input[id*=login i]", "input[name*=phone i]"
    ]
    form = pw.locator("xpath=ancestor::form[1]")
    for css in candidates:
        try:
            el = (form.locator(css).first if form.count() else pw.page.locator(css).first)
            el.wait_for(state="attached", timeout=500)
            return el
        except Exception:
            continue
    return None


def _click_submit_in_form(form, timeout_ms):
    btn_css = [
        "button[type=submit]", "input[type=submit]", "[role=button]", "button",
        ".btn-primary, .btn, .button"
    ]
    for css in btn_css:
        try:
            btn = form.locator(css).filter(has_not=form.page.locator(":disabled")).first
            btn.wait_for(state="visible", timeout=min(1500, timeout_ms))
            btn.click(timeout=timeout_ms)
            return True
        except Exception:
            pass

    # לפי טקסט / role
    for w in LOGIN_WORDS:
        pattern = re.compile(rf"\b{re.escape(w)}\b", re.I)
        for role in ("button", "link"):
            try:
                btn = form.page.get_by_role(role, name=pattern).first
                if btn.locator("xpath=ancestor::form[1]").count() == 0:
                    continue
                btn.wait_for(state="visible", timeout=min(1500, timeout_ms))
                btn.click(timeout=timeout_ms)
                return True
            except Exception:
                pass
    return False


def _submit_via_enter(pw, timeout_ms):
    try:
        pw.focus()
        pw.press("Enter", timeout=timeout_ms)
        return True
    except Exception:
        try:
            form = pw.locator("xpath=ancestor::form[1]")
            if form.count():
                form.evaluate("el => el.submit()")
                return True
        except Exception:
            pass
    return False


def _global_login_button_click(page, timeout_ms, intent_words=None):
    words = list(dict.fromkeys((intent_words or []) + LOGIN_WORDS))
    for w in words:
        pattern = re.compile(rf"\b{re.escape(w)}\b", re.I)
        for role in ("button", "link"):
            try:
                btn = page.get_by_role(role, name=pattern).first
                btn.wait_for(state="visible", timeout=min(1500, timeout_ms))
                btn.click(timeout=timeout_ms)
                return True
            except Exception:
                pass

    # CSS נפוצים
    for css in ("button[type=submit]", "input[type=submit]", "[role=button]", "button", ".btn-primary, .btn"):
        try:
            candidate = page.locator(css).filter(has_not=page.locator(":disabled")).first
            candidate.wait_for(state="visible", timeout=min(1500, timeout_ms))
            candidate.click(timeout=timeout_ms)
            return True
        except Exception:
            pass
    return False


# ===============================================================
#  CLICK (SMART)
# ===============================================================

def _pick_visible_candidate(page, selector: str, timeout_ms: int):
    """
    מחזיר את האלמנט הראשון שגלוי ולא מושבת — קודם ממודאל, אחר כך מדף רגיל.
    """
    half = max(500, int(timeout_ms * 0.5))
    modal = page.locator("[role=dialog]:visible, .modal.show, .modal:visible").first

    if modal.count():
        cand = modal.locator(f"{selector}:visible").filter(has_not=page.locator(":disabled")).first
        try:
            cand.wait_for(state="visible", timeout=half)
            return cand
        except Exception:
            pass

    cand = page.locator(f"{selector}:visible").filter(has_not=page.locator(":disabled")).first
    try:
        cand.wait_for(state="visible", timeout=half)
        return cand
    except Exception:
        pass

    return None


def action_click(page, *, selector=None, value=None, timeout_ms=7000, **_):
    """
    קליק חכם:
    - אם קיים selector מפורש — ילחץ עליו.
    - אחרת ינסה למצוא כפתור לפי value (כוונה, כמו login / sign in / continue).
    - אם לא נמצא — ינסה fallback כללי.
    """
    if selector:
        cand = _pick_visible_candidate(page, selector, timeout_ms)
        if cand and cand.count():
            cand.click(timeout=timeout_ms)
            return
        else:
            raise RuntimeError(f"Element not found for selector: {selector}")

    # אין selector → fallback לפי intent (login, sign in, register וכו')
    intent = (value or "").strip().lower()
    words = list(dict.fromkeys(
        ([intent] if intent else []) + LOGIN_WORDS + REGISTER_WORDS
    ))

    # נסה במודאל
    modal = page.locator("[role=dialog]:visible, .modal.show, .modal:visible").first
    if modal.count():
        for w in words:
            try:
                modal.get_by_role("button", name=re.compile(rf"\b{re.escape(w)}\b", re.I)).first.click(timeout=timeout_ms)
                return
            except Exception:
                pass

    # גלובלי
    for w in words:
        try:
            page.get_by_role("button", name=re.compile(rf"\b{re.escape(w)}\b", re.I)).first.click(timeout=timeout_ms)
            return
        except Exception:
            pass

    # Fallback: כפתורים סטנדרטיים
    cand = _pick_visible_candidate(page, "button, [role=button], input[type=submit]", timeout_ms)
    if cand and cand.count():
        cand.click(timeout=timeout_ms)
        return

    # לא נמצא כלום
    raise RuntimeError(
        f"⚠️ לא נמצא אלמנט מתאים ללחיצה (value={value!r}). "
        "ודא שהכפתור גלוי או ספק selector מפורש."
    )
