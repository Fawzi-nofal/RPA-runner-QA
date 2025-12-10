from playwright.sync_api import expect
import re

def action_assert_visible(page, *, selector, timeout_ms=7000, **_):
    loc = page.locator(selector)
    try:
        expect(loc).to_be_visible(timeout=timeout_ms)
    except Exception as e:
        raise AssertionError(f"Expected VISIBLE: {selector}. Error: {e}")

def action_assert_text(page, *, selector, value, timeout_ms=7000, **_):
    """
    התאמה מלאה של הטקסט (אחרי נרמול קל של רווחים).
    אם תרצה התאמה חלקית, השתמש ב-assert_contains.
    """
    loc = page.locator(selector)
    try:
        # Playwright כבר מנרמל רווחים בתוכו; אם צריך קפדנות גבוהה אפשר להוריד strip()
        expect(loc).to_have_text(str(value), timeout=timeout_ms)
    except Exception as e:
        try:
            actual = loc.inner_text(timeout=1000)
        except Exception:
            actual = "<unavailable>"
        raise AssertionError(
            f"Expected EXACT text.\n  selector: {selector}\n  expected: {value!r}\n  actual  : {actual!r}\n  error   : {e}"
        )

def action_assert_contains(page, *, selector, value, timeout_ms=7000, **_):
    """
    התאמה חלקית (substring) של הטקסט. אפשר גם להעביר regex ב-value.
    """
    loc = page.locator(selector)
    try:
        # אם value הוא str נקי – זה בודק 'contains'; אם תרצה case-insensitive:
        # expect(loc).to_contain_text(re.compile(re.escape(str(value)), re.I), timeout=timeout_ms)
        expect(loc).to_contain_text(str(value), timeout=timeout_ms)
    except Exception as e:
        try:
            actual = loc.inner_text(timeout=1000)
        except Exception:
            actual = "<unavailable>"
        raise AssertionError(
            f"Expected text to CONTAIN substring.\n  selector: {selector}\n  contains: {value!r}\n  actual  : {actual!r}\n  error   : {e}"
        )

def action_assert_url(page, *, value, timeout_ms=7000, **_):
    """
    מאשר שה-URL הנוכחי מכיל את value (באמצעות regex).
    """
    try:
        # שימוש ב-expect מחכה לשינוי URL עד ה-timeout
        pattern = re.compile(re.escape(str(value)))
        expect(page).to_have_url(pattern, timeout=timeout_ms)
    except Exception as e:
        current = page.url
        raise AssertionError(
            f"URL assertion failed (expected to CONTAIN {value!r}).\n  current: {current!r}\n  error  : {e}"
        )

# --- אופציונלי, שימושי מאוד ---

def action_assert_exists(page, *, selector, timeout_ms=7000, **_):
    """
    האלמנט קיים ב-DOM (לא בהכרח נראה).
    """
    loc = page.locator(selector)
    try:
        expect(loc).to_have_count(lambda c: c >= 1, timeout=timeout_ms)  # טריק, אבל ברור יותר:
        # לחלופין:
        # if loc.count() == 0: raise AssertionError(...)
    except Exception:
        if loc.count() == 0:
            raise AssertionError(f"Expected element to exist: {selector}")
        # אם נסיבות אחרות:
        raise

def action_assert_not_visible(page, *, selector, timeout_ms=7000, **_):
    """
    האלמנט לא נראה (hidden / detached).
    """
    loc = page.locator(selector)
    try:
        expect(loc).not_to_be_visible(timeout=timeout_ms)
    except Exception as e:
        raise AssertionError(f"Expected NOT VISIBLE: {selector}. Error: {e}")
