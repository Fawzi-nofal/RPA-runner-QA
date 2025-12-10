# core/graph/graph.py
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
from pathlib import Path
import json
import time


@dataclass
class Node:
    id: str               # מזהה לוגי (בד"כ path נקי)
    url: str              # URL מלא
    title: Optional[str]  # כותרת הדף (אם קיימת)
    snapshot: Dict[str, Any]  # תקציר הדף מ-perception (Observation dict)


@dataclass
class Edge:
    src: str
    dst: str
    kind: str             # "link" / "button" / "nav"
    label: Optional[str]  # טקסט כפתור/קישור אם יש


class PageGraph:
    """
    גרף עמודים פשוט:
    - nodes: id -> Node
    - edges: רשימת חיבורים
    """
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.nodes: Dict[str, Node] = {}
        self.edges: List[Edge] = []
        self.created_at = int(time.time())

    def add_node(self, node: Node) -> None:
        if node.id not in self.nodes:
            self.nodes[node.id] = node

    def add_edge(self, edge: Edge) -> None:
        # הימנע מכפילויות בסיסיות
        for e in self.edges:
            if e.src == edge.src and e.dst == edge.dst and e.kind == edge.kind and e.label == edge.label:
                return
        self.edges.append(edge)

    def has_node(self, node_id: str) -> bool:
        return node_id in self.nodes

    def to_dict(self) -> Dict[str, Any]:
        return {
            "base_url": self.base_url,
            "created_at": self.created_at,
            "nodes": [asdict(n) for n in self.nodes.values()],
            "edges": [asdict(e) for e in self.edges],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PageGraph":
        g = cls(data.get("base_url", ""))
        g.created_at = data.get("created_at") or g.created_at
        for nd in data.get("nodes", []):
            g.add_node(Node(**nd))
        for ed in data.get("edges", []):
            g.add_edge(Edge(**ed))
        return g


# ---------- שמירה/טעינה ----------
def save_graph(graph: PageGraph, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(graph.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path

def load_graph(path: Path) -> PageGraph:
    data = json.loads(path.read_text(encoding="utf-8"))
    return PageGraph.from_dict(data)
