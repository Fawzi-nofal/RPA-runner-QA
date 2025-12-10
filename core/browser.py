from __future__ import annotations
from pathlib import Path
from typing import Optional, Sequence, Dict, Any, Tuple
from playwright.sync_api import sync_playwright, Playwright, Browser, BrowserContext, Page

def _normalize_viewport(viewport: Optional[Sequence[int]]) -> Optional[Dict[str, int]]:
    if not viewport:
        return None
    try:
        w, h = int(viewport[0]), int(viewport[1])
        if w > 0 and h > 0:
            return {"width": w, "height": h}
    except Exception:
        pass
    return None

def _browser_ctor(p: Playwright, name: str):
    name = (name or "chromium").strip().lower()
    if name in ("chromium", "chrome"): return p.chromium
    if name in ("firefox", "ff"):       return p.firefox
    if name in ("webkit", "safari"):    return p.webkit
    return p.chromium

def open_browser(
    browser_name: str,
    headful: bool,
    *,
    record_video_dir: Optional[Path] = None,
    downloads_dir: Optional[Path] = None,
    viewport: Optional[Sequence[int]] = None, #גודל החלון
    user_agent: Optional[str] = None, #טקסט שמגדיר את סוג הדפדפן/מכשיר מול האתר
    timeout_ms: Optional[int] = None, #כמה זמן לחכות לטעינה לפני שיזרק שגיאה
    slow_mo: int = 0,
    proxy: Optional[Dict[str, str]] = None,   # {"server": "http://host:port", "username": "...", "password": "..."}
    extra_context_options: Optional[Dict[str, Any]] = None,
) -> Tuple[Playwright, Browser, BrowserContext, Page]:
    if record_video_dir: Path(record_video_dir).mkdir(parents=True, exist_ok=True)
    if downloads_dir:    Path(downloads_dir).mkdir(parents=True, exist_ok=True)

    p = sync_playwright().start()
    browser_type = _browser_ctor(p, browser_name)

    launch_kwargs: Dict[str, Any] = {"headless": not bool(headful)}
    if slow_mo and int(slow_mo) > 0:
        launch_kwargs["slow_mo"] = int(slow_mo)
    if proxy:
        launch_kwargs["proxy"] = proxy

    browser: Browser = browser_type.launch(**launch_kwargs)

    vp = _normalize_viewport(viewport)
    context_kwargs: Dict[str, Any] = {"accept_downloads": True}
    if vp:
        context_kwargs["viewport"] = vp
    if user_agent:
        context_kwargs["user_agent"] = str(user_agent)
    if record_video_dir:
        context_kwargs["record_video_dir"] = str(record_video_dir)
        if vp:
            context_kwargs["record_video_size"] = {"width": vp["width"], "height": vp["height"]}
    if extra_context_options:
        context_kwargs.update(dict(extra_context_options))

    ctx: BrowserContext = browser.new_context(**context_kwargs)
    page: Page = ctx.new_page()

    if timeout_ms and int(timeout_ms) > 0:
        ms = int(timeout_ms)
        page.set_default_timeout(ms)
        page.set_default_navigation_timeout(ms)

    return p, browser, ctx, page

def close_browser(p: Playwright, browser: Browser, ctx: BrowserContext) -> None:
    try:
        ctx.close()
    finally:
        try:
            browser.close()
        finally:
            try:
                p.stop()
            except Exception:
                pass
