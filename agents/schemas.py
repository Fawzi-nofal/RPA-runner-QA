# agents/schemas.py
from __future__ import annotations
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ElementMini(BaseModel):
    """
    תיאור מינימלי של אלמנט חשוב בדף (כפתור/קלט), עם רמז סלקטור יציב.
    """
    role: Optional[str] = None
    text: Optional[str] = None
    id: Optional[str] = None
    name: Optional[str] = None
    aria_label: Optional[str] = None
    data_testid: Optional[str] = None
    selector_hint: Optional[str] = None


class Observation(BaseModel):
    """
    תמונת מצב של הדף הנוכחי: טקסטים, כפתורים, שדות, ודגלים (modal/password/שגיאות...).
    """
    url: str
    title: Optional[str] = None
    visible_texts: List[str] = Field(default_factory=list)
    buttons: List[ElementMini] = Field(default_factory=list)
    inputs: List[ElementMini] = Field(default_factory=list)
    flags: Dict[str, Any] = Field(default_factory=dict)     # למשל: {"has_password": True, "modal_open": False}
    memory: Dict[str, Any] = Field(default_factory=dict)    # זיכרון פר-דומיין (אופציונלי)
    history: List[Dict[str, Any]] = Field(default_factory=list)  # צעדים ותוצאות קודמים (אופציונלי)


class ActionSpec(BaseModel):
    """
    הוראת פעולה בודדת (עם נפילות חלופיות):
    למשל: {"goal":"login","action":{"type":"fill","selector":"#user","value":"${USERNAME}"},"fallbacks":[...]}
    """
    goal: str = "login"
    action: Dict[str, Any] = Field(default_factory=dict)
    fallbacks: List[Dict[str, Any]] = Field(default_factory=list)
