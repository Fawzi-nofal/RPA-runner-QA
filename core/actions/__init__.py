from .browser_actions import action_goto, action_click, action_press
from .form_actions import (
    action_fill, action_select_option, action_wait, action_screenshot,
    action_wait_for_selector,   # ← חדש
)
from .assert_actions import (
    action_assert_visible, action_assert_text, action_assert_contains, action_assert_url
)

# -----------------------------------------------------
# מיפוי שם פעולה ← פונקציה
# -----------------------------------------------------
ACTION_REGISTRY = {
    # פעולות ניווט/דפדפן
    "goto": action_goto,
    "click": action_click,
    "press": action_press,

    # פעולות טפסים/דף
    "fill": action_fill,
    "select_option": action_select_option,
    "wait": action_wait,
    "screenshot": action_screenshot,
    "wait_for_selector": action_wait_for_selector,  # ← חדש

    # אימותים (assertions)
    "assert_visible": action_assert_visible,
    "assert_text": action_assert_text,
    "assert_contains": action_assert_contains,
    "assert_url": action_assert_url,
}