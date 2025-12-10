# core/perception.py
from __future__ import annotations
from typing import List, Dict, Any
from playwright.sync_api import Page
from agents.schemas import Observation, ElementMini


def _safe_text(s: str) -> str:
    """ניקוי טקסטים מיותרים, רווחים, תווים נסתרים."""
    s = (s or "").strip()
    return " ".join(s.split())


def _collect_buttons(page: Page) -> List[ElementMini]:
    """אוסף כפתורים ולינקים (כולל כאלה עם role או input[type=submit])"""
    btns = []
    loc = page.locator("button, [role=button], input[type=submit], a")
    count = min(loc.count(), 80)
    for i in range(count):
        el = loc.nth(i)
        try:
            txt = _safe_text(el.inner_text(timeout=300))
        except Exception:
            txt = ""
        try:
            btns.append(ElementMini(
                role="button",
                text=txt or None,
                id=el.get_attribute("id"),
                name=el.get_attribute("name"),
                aria_label=el.get_attribute("aria-label"),
                data_testid=el.get_attribute("data-testid"),
                selector_hint=_build_selector_hint(el)
            ))
        except Exception:
            pass
    return btns


def _collect_inputs(page: Page) -> List[ElementMini]:
    """אוסף כל השדות האפשריים בעמוד"""
    ins = []
    loc = page.locator("input, textarea, [role=textbox], select")
    count = min(loc.count(), 100)
    for i in range(count):
        el = loc.nth(i)
        try:
            txt = el.get_attribute("placeholder") or el.get_attribute("aria-label") or el.get_attribute("name") or el.get_attribute("id") or el.get_attribute("type")
        except Exception:
            txt = None
        try:
            ins.append(ElementMini(
                role="input",
                text=_safe_text(txt) if txt else None,
                id=el.get_attribute("id"),
                name=el.get_attribute("name"),
                aria_label=el.get_attribute("aria-label"),
                data_testid=el.get_attribute("data-testid"),
                selector_hint=_build_selector_hint(el)
            ))
        except Exception:
            pass
    return ins


def _build_selector_hint(el) -> str | None:
    """מייצר selector קצר ל-AI Agent"""
    try:
        if el.get_attribute("id"):
            return f"#{el.get_attribute('id')}"
        if el.get_attribute("name"):
            return f"[name='{el.get_attribute('name')}']"
        if el.get_attribute("data-testid"):
            return f"[data-testid='{el.get_attribute('data-testid')}']"
    except Exception:
        pass
    return None


def perceive(page: Page,
             history: List[Dict[str, Any]] | None = None,
             memory: Dict[str, Any] | None = None) -> Observation:
    """קורא את הדף הנוכחי ומחזיר תיאור תמציתי (Observation)"""
    url = page.url
    try:
        title = page.title()
    except Exception:
        title = None

    # דגלים חכמים לזיהוי מצבים
    flags: Dict[str, Any] = {}

    try:
        flags["modal_open"] = page.locator("[role=dialog]:visible, .modal.show, .modal:visible").count() > 0
    except Exception:
        flags["modal_open"] = False

    try:
        flags["has_password"] = page.locator("input[type='password']").count() > 0
    except Exception:
        flags["has_password"] = False

    try:
        flags["has_form"] = page.locator("form").count() > 0
    except Exception:
        flags["has_form"] = False

    try:
        flags["error_banner"] = None
        error_el = page.locator("text=/error|invalid|failed|wrong|שגיאה|נכשל/i").first
        if error_el and error_el.count() > 0:
            flags["error_banner"] = _safe_text(error_el.inner_text(timeout=200))
    except Exception:
        pass

    try:
        flags["success_banner"] = None
        succ_el = page.locator("text=/success|welcome|הצלחה|בוצע|נשמר|נשלח/i").first
        if succ_el and succ_el.count() > 0:
            flags["success_banner"] = _safe_text(succ_el.inner_text(timeout=200))
    except Exception:
        pass

    # טקסטים בולטים בעמוד (לא כל הדף כדי לא להציף)
    visible_texts = []
    try:
        all_text = page.locator("body").inner_text(timeout=700)
        for t in all_text.splitlines():
            t = _safe_text(t)
            if 3 <= len(t) <= 150:
                visible_texts.append(t)
        visible_texts = visible_texts[:80]
    except Exception:
        pass

    # החזרת אובייקט Observation
    return Observation(
        url=url,
        title=title,
        visible_texts=visible_texts,
        buttons=_collect_buttons(page),
        inputs=_collect_inputs(page),
        flags=flags,
        memory=memory or {},
        history=history or []
    )
