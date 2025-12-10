# core/graph/builder.py
from __future__ import annotations
from typing import List, Tuple, Set, Dict, Any
from urllib.parse import urlparse, urljoin
from pathlib import Path
from collections import deque

from playwright.sync_api import Page
from core.graph.graph import PageGraph, Node, Edge, save_graph
from core.perception import perceive


# --------- עוזרים לכתובות ---------
def _strip_hash(url: str) -> str:
    return url.split("#", 1)[0]

def _same_origin(a: str, b: str) -> bool:
    pa, pb = urlparse(a), urlparse(b)
    return (pa.scheme, pa.netloc) == (pb.scheme, pb.netloc)

def _normalize(base_url: str, href: str) -> str | None:
    if not href:
        return None
    href = href.strip()
    if href.startswith("javascript:"):
        return None
    try:
        absu = urljoin(base_url, href)
        return _strip_hash(absu)
    except Exception:
        return None

def _node_id_from_url(url: str) -> str:
    """מזהה צומת מה-path + query בסיסי. שומר על יציבות."""
    p = urlparse(url)
    # דף בית => "/"
    path = p.path or "/"
    # אפשר לצרף query קצר, כדי להבדיל דפים שונים מאותו path
    q = ("?" + p.query) if p.query else ""
    return (path + q).strip()


# --------- חילוץ קישורים מהדף ---------
def _extract_links(page: Page, base_url: str, limit: int = 50) -> List[Tuple[str, str]]:
    """
    מחזיר [(href_norm, label), ...] עד limit.
    כולל אלמנטים: <a href>, כפתורים וקישורים עם role.
    """
    links: List[Tuple[str, str]] = []

    # <a href=...>
    anchors = page.locator("a[href]")
    count = min(anchors.count(), limit)
    for i in range(count):
        el = anchors.nth(i)
        try:
            href = el.get_attribute("href") or ""
            label = (el.inner_text(timeout=200) or "").strip()
            absu = _normalize(base_url, href)
            if not absu:
                continue
            links.append((absu, label))
        except Exception:
            continue

    # נסה גם אלמנטים שנראים כמו לינקים/כפתורים שמבצעים ניווט
    # (הוספת עוד Heuristics אפשרית בעתיד)
    # כאן נשאיר בסיסי: buttons with formaction / type=submit שאין להם form, לא נוסיף עכשיו.

    # ניקוי כפילויות
    seen: Set[Tuple[str, str]] = set()
    deduped = []
    for href, label in links:
        key = (href, label)
        if key in seen:
            continue
        seen.add(key)
        deduped.append((href, label))

    return deduped


# --------- בניית גרף (BFS) ---------
def build_graph(page: Page, start_url: str, *, max_pages: int = 10, max_depth: int = 2) -> PageGraph:
    """
    סורק את האתר ב-BFS מוגבל:
    - מתחיל מ-start_url (חייב להיות באותו origin עם ה-base_url שנגזר ממנו).
    - לא יוצא מה-origin.
    - עומק ורוחב מוגבלים כדי לא להסתבך באתרי ענק/אינסוף.
    - עבור כל דף: יוצר Node עם snapshot מ-perceive, ומוסיף קשתות לכל קישור שנמצא.
    """
    base_origin = f"{urlparse(start_url).scheme}://{urlparse(start_url).netloc}"
    graph = PageGraph(base_origin)

    # תור BFS: (url, depth)
    q = deque([(start_url, 0)])
    visited: Set[str] = set()

    while q and len(graph.nodes) < max_pages:
        url, depth = q.popleft()
        url = _strip_hash(url)
        if url in visited:
            continue
        visited.add(url)

        # לא יוצאים מהדומיין
        if not _same_origin(base_origin, url):
            continue

        # נווט לדף
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
        except Exception:
            # אם לא הצליח לנווט, דלג
            continue

        # תיאור דף (Observation)
        obs = perceive(page)
        node_id = _node_id_from_url(url)
        node = Node(id=node_id, url=url, title=obs.title, snapshot=obs.model_dump())
        graph.add_node(node)

        # חילוץ קישורים מהדף
        if depth < max_depth:
            links = _extract_links(page, base_origin, limit=80)
            for href, label in links:
                if not _same_origin(base_origin, href):
                    continue
                dst_id = _node_id_from_url(href)
                graph.add_edge(Edge(src=node_id, dst=dst_id, kind="link", label=(label or None)))
                if href not in visited and len(graph.nodes) + len(q) < max_pages:
                    q.append((href, depth + 1))

    return graph


# --------- פונקציית עזר לשימוש חיצוני ---------
def explore_and_save(page: Page, start_url: str, *, reports_dir: Path = Path("reports/ai"),
                     max_pages: int = 10, max_depth: int = 2) -> Path:
    """
    מריץ build_graph ושומר JSON ב-reports/ai/site_graph.json.
    מחזיר את הנתיב לקובץ.
    """
    graph = build_graph(page, start_url, max_pages=max_pages, max_depth=max_depth)
    out = reports_dir / "site_graph.json"
    return save_graph(graph, out)
