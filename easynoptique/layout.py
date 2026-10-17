"""Placement automatique des trois vues : fonctionnelle, alimentation, bus.

Règles de présentation (inspirées de l'IEC 61082-1) :
- lecture de gauche à droite : sources et alimentation à gauche, traitement au centre, périphériques à droite ;
- représentation unifilaire : un trait par bus, avec le nombre de fils (trait oblique « /n ») ;
- flèche simple = sens du flux, double flèche = bidirectionnel ; trait épais = énergie ; pointillés = debug ;
- légende et cartouche systématiques.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .model import CATEGORIES, LINK_KINDS, Block, Link, Synoptic
from .scene import Edge, Scene, Shape

W = 180
ITEM_H = 28
ITEM_GAP = 8
HEAD = 26
PAD = 10
MAX_ITEMS = 5
BOARD_FILL, BOARD_STROKE = "#f1f8ef", "#82b366"
BADGE_FILL = "#b85450"
TOP = 74


@dataclass
class Rect:
    sid: str
    x: float
    y: float
    w: float
    h: float
    col: str = ""

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def bottom(self) -> float:
        return self.y + self.h

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2


def short(value: str, n: int = 22) -> str:
    v = value.replace("_", " ").strip()
    return v if len(v) <= n else v[: n - 1] + "…"


def edge_style(kind: str) -> tuple[float, bool]:
    if kind == "power":
        return 2.6, False
    if kind in ("swd", "jtag"):
        return 1.3, True
    return 1.3, False


def arrows(direction: str) -> tuple[bool, bool]:
    return direction in ("ba", "both"), direction in ("ab", "both")


# ----------------------------------------------------------------------------- ports et routage


class Router:
    """Répartit les points d'accroche sur les côtés des rectangles et trace des liaisons orthogonales."""

    def __init__(self) -> None:
        self.ends: dict[tuple[str, str], list[tuple[str, int, float]]] = defaultdict(list)
        self.ports: dict[tuple[str, int], tuple[float, float]] = {}

    def want(self, rect: Rect, side: str, link_id: str, end: int, other: Rect) -> None:
        key = other.cy if side in ("left", "right") else other.cx
        self.ends[(rect.sid, side)].append((link_id, end, key))

    def solve(self, rects: dict[str, Rect]) -> None:
        """Répartit les ports ; 2e et 3e passes : tri selon la position de l'autre extrémité (moins de croisements)."""
        self._assign(rects, None)
        for _ in range(2):
            self._assign(rects, self.ports.copy())

    def _assign(self, rects: dict[str, Rect], prev: dict | None) -> None:
        for (sid, side), lst in self.ends.items():
            r = rects[sid]
            axis = 1 if side in ("left", "right") else 0

            def key(t, axis=axis):
                lid, end, default = t
                if prev and (lid, 1 - end) in prev:
                    return (prev[(lid, 1 - end)][axis], default)
                return (default, 0)

            lst.sort(key=key)
            n = len(lst)
            for i, (lid, end, _) in enumerate(lst):
                f = (i + 1) / (n + 1)
                if side == "left":
                    p = (r.x, r.y + r.h * f)
                elif side == "right":
                    p = (r.right, r.y + r.h * f)
                elif side == "top":
                    p = (r.x + r.w * f, r.y)
                else:
                    p = (r.x + r.w * f, r.bottom)
                self.ports[(lid, end)] = p


def channel_order(pairs: list[tuple[str, tuple[float, float], tuple[float, float]]]) -> list[str]:
    """Ordre des couloirs verticaux (de gauche à droite) qui évite les croisements.

    ``pairs`` : (id, point gauche, point droit). Les liaisons qui montent sont triées du haut vers le bas,
    celles qui descendent du bas vers le haut.
    """
    ups = sorted((p for p in pairs if p[2][1] < p[1][1] - 0.5), key=lambda p: p[1][1])
    downs = sorted((p for p in pairs if p[2][1] > p[1][1] + 0.5), key=lambda p: -p[1][1])
    flat = [p for p in pairs if abs(p[2][1] - p[1][1]) <= 0.5]
    return [p[0] for p in ups + downs + flat]


def sides(a: Rect, b: Rect) -> tuple[str, str]:
    if b.x >= a.right + 20:
        return "right", "left"
    if a.x >= b.right + 20:
        return "left", "right"
    if b.y >= a.bottom:
        return "bottom", "top"
    if a.y >= b.bottom:
        return "top", "bottom"
    return "right", "right"


def route(p1, p2, s1, s2, channel: float) -> list[tuple[float, float]]:
    (x1, y1), (x2, y2) = p1, p2
    if s1 in ("left", "right") and s2 in ("left", "right") and s1 != s2:
        if abs(y1 - y2) < 1:
            return [p1, p2]
        return [p1, (channel, y1), (channel, y2), p2]
    if s1 == s2 and s1 in ("left", "right"):
        return [p1, (channel, y1), (channel, y2), p2]
    if s1 in ("top", "bottom") and s2 in ("top", "bottom") and s1 != s2:
        if abs(x1 - x2) < 1:
            return [p1, p2]
        return [p1, (x1, channel), (x2, channel), p2]
    if s1 == s2:
        return [p1, (x1, channel), (x2, channel), p2]
    # mixte (côté / dessus) : coude simple
    if s1 in ("left", "right"):
        return [p1, (x2, y1), p2]
    return [p1, (x1, y2), p2]


def place_label(points, label: str, n_wires: int, left: bool = False) -> tuple[tuple[float, float, str] | None, tuple | None]:
    best, best_len = 0, -1.0
    for i in range(len(points) - 1):
        (xa, ya), (xb, yb) = points[i], points[i + 1]
        seg = abs(xa - xb) + abs(ya - yb)
        if seg > best_len:
            best, best_len = i, seg
    (xa, ya), (xb, yb) = points[best], points[best + 1]
    vertical = abs(xa - xb) < 0.5
    mark = None
    if vertical:
        my = ya + (yb - ya) * 0.5
        lab = ((xa - 6, my + 4, "end") if left else (xa + 6, my + 4, "start")) if label else None
        if n_wires > 1:
            mark = (xa, ya + (yb - ya) * 0.25, n_wires, True)
    else:
        mx = xa + (xb - xa) * 0.55
        lab = (mx, ya - 6, "middle") if label else None
        if n_wires > 1:
            mark = (xa + (xb - xa) * 0.2, ya, n_wires, False)
    return lab, mark


# ----------------------------------------------------------------------------- éléments communs


def block_rect_size(b: Block, is_hub: bool) -> tuple[float, float]:
    n = min(len(b.items), MAX_ITEMS + 1)
    if is_hub and len(b.items) <= 1:
        return 210, 100
    n = max(1, n)
    return W, HEAD + n * ITEM_H + (n - 1) * ITEM_GAP + PAD


def draw_block(scene: Scene, b: Block, r: Rect, is_hub: bool, detailed: bool) -> None:
    _, fill, stroke = CATEGORIES.get(b.category, CATEGORIES["other"])
    if is_hub and len(b.items) <= 1:
        it = b.items[0] if b.items else None
        scene.add(Shape(r.sid, "box", r.x, r.y, r.w, r.h, label=short(it.value if it else b.name, 24),
                        sub=(it.ref if it and detailed else ""), fill="#ffffff", stroke="#000000", bold=True,
                        font=15, block=b.id, z=3))
    else:
        scene.add(Shape(r.sid, "group", r.x, r.y, r.w, r.h, label=b.name.upper(), fill=fill, stroke=stroke,
                        align="topleft", font=9.5, bold=True, text_color=stroke, block=b.id, z=1))
        items = b.items[:MAX_ITEMS]
        extra = len(b.items) - MAX_ITEMS
        for i, it in enumerate(items):
            y = r.y + HEAD + i * (ITEM_H + ITEM_GAP)
            scene.add(Shape(f"{r.sid}-{it.ref}", "box", r.x + 10, y, r.w - 20, ITEM_H, label=short(it.value),
                            sub=it.ref if detailed else "", block=b.id, z=3))
        if extra > 0:
            y = r.y + HEAD + MAX_ITEMS * (ITEM_H + ITEM_GAP)
            scene.add(Shape(f"{r.sid}-more", "box", r.x + 10, y, r.w - 20, ITEM_H, label=f"+ {extra} autres",
                            stroke=stroke, dashed=True, block=b.id, z=3))
    for k, rail in enumerate(b.rails):
        bw = 8 + 6.2 * len(rail)
        scene.add(Shape(f"{r.sid}-badge-{k}", "badge", r.right - bw - 6 - k * (bw + 4), r.y - 8, bw, 16, label=rail,
                        fill=BADGE_FILL, stroke=BADGE_FILL, text_color="#ffffff", bold=True, font=9, radius=8, z=4))


def add_board(scene: Scene, x2: float, y2: float, title: str) -> Rect:
    scene.add(Shape("board", "board", 20, 20, x2 - 20, y2 - 20, fill=BOARD_FILL, stroke=BOARD_STROKE, radius=30, z=0))
    scene.add(Shape("board-title", "text", 44, 50, label=title, align="start", bold=True, font=15, z=5))
    return Rect("board", 20, 20, x2 - 20, y2 - 20)


def add_legend_and_cartouche(scene: Scene, syn: Synoptic, view: str, kinds: set[str], cats: set[str], y: float,
                             board_right: float) -> None:
    x = 24
    scene.add(Shape("legend-title", "text", x, y + 12, label="LÉGENDE", align="start", bold=True, font=10,
                    text_color="#555555", z=5))
    row = y + 30
    items = []
    if "power" in kinds:
        items.append(("power", "Alimentation (énergie)", False, True, 2.6, False))
    sig = [k for k in kinds if k != "power"]
    if sig:
        items.append(("sig", "Signal (sens du flux)", False, True, 1.3, False))
        items.append(("bi", "Bidirectionnel", True, True, 1.3, False))
    if kinds & {"swd", "jtag"}:
        items.append(("dbg", "Programmation / debug", True, True, 1.3, True))
    cx = x
    limit = max(board_right, 600)

    def wrap(width: float) -> None:
        nonlocal cx, row
        if cx + width > limit:
            cx = x
            row += 24

    for key, text, a_s, a_e, wdt, dash in items:
        wrap(60 + 6 * len(text))
        scene.edges.append(Edge(f"legend-{key}", "legend", [(cx, row), (cx + 34, row)], a_s, a_e, width=wdt, dashed=dash))
        scene.add(Shape(f"legend-{key}-t", "text", cx + 42, row + 4, label=text, align="start", font=10, z=5))
        cx += 60 + 6 * len(text)
    if sig:
        wrap(60 + 6 * 18)
        scene.edges.append(Edge("legend-mark", "legend", [(cx, row), (cx + 34, row)], False, False,
                                mark=(cx + 17, row, 4, False)))
        scene.add(Shape("legend-mark-t", "text", cx + 42, row + 4, label="/n : nombre de fils", align="start", font=10, z=5))
        cx += 60 + 6 * 18
    if any(s.kind == "badge" for s in scene.shapes):
        wrap(60 + 6 * 27)
        scene.add(Shape("legend-badge", "badge", cx, row - 8, 38, 16, label="+3V3", fill=BADGE_FILL, stroke=BADGE_FILL,
                        text_color="#ffffff", bold=True, font=9, radius=8, z=4))
        scene.add(Shape("legend-badge-t", "text", cx + 46, row + 4, label="Rail d'alimentation du bloc", align="start",
                        font=10, z=5))
    row += 26
    cx = x
    for cat in [c for c in CATEGORIES if c in cats]:
        label, fill, stroke = CATEGORIES[cat]
        wrap(40 + 6.2 * len(label))
        scene.add(Shape(f"legend-cat-{cat}", "box", cx, row - 9, 18, 14, fill=fill, stroke=stroke, z=3))
        scene.add(Shape(f"legend-cat-{cat}-t", "text", cx + 24, row + 2, label=label, align="start", font=10, z=5))
        cx += 40 + 6.2 * len(label)

    # Cartouche (ISO 7200, simplifié)
    cells = [("Projet", syn.title or syn.project), ("Vue", view), ("Rév.", syn.rev or "—"),
             ("Date", syn.date or "—"), ("Généré par", "EasyNoptique")]
    widths = [max(110, 7.2 * len(v) + 20) for _, v in cells]
    total = sum(widths)
    cx = max(board_right - total, x)
    cy = row + 22
    for (cap, val), wd in zip(cells, widths):
        scene.add(Shape(f"cart-{cap}", "cell", cx, cy, wd, 38, label=val, sub=cap.upper(), bold=True, font=11.5, z=3))
        cx += wd
    scene.width = max(scene.width, cx + 20)
    scene.height = cy + 38 + 20


# ----------------------------------------------------------------------------- vue fonctionnelle


def layout_functional(syn: Synoptic, detailed: bool = False) -> Scene:
    view = "Synoptique complet" if detailed else "Synoptique fonctionnel"
    scene = Scene(view, 0, 0)
    blocks = [b for b in syn.blocks if not b.hidden]
    if not blocks:
        add_board(scene, 400, 200, syn.title)
        scene.width, scene.height = 420, 220
        return scene
    by_id = {b.id: b for b in blocks}
    hub = syn.hub if syn.hub in by_id else blocks[0].id
    source_blocks = {p.block for p in syn.power if p.role == "source"}
    links = [lk for lk in syn.links if lk.a in by_id and lk.b in by_id]

    left, right, bottom = [], [], []
    for b in blocks:
        if b.id == hub:
            continue
        if b.category == "debug":
            bottom.append(b)
        elif b.category == "power" or (b.id in source_blocks and b.category == "interface"):
            left.append(b)
        else:
            right.append(b)
    left.sort(key=lambda b: (b.category == "power", b.name))
    order = ["radio", "hmi", "sensors", "memory", "interface", "other", "power"]
    right.sort(key=lambda b: (order.index(b.category) if b.category in order else 99, b.name))
    col = {b.id: "L" for b in left} | {b.id: "R" for b in right} | {b.id: "B" for b in bottom} | {hub: "H"}

    def count(c1: str, c2: str) -> int:
        return sum(1 for lk in links if {col[lk.a], col[lk.b]} == {c1, c2} or (c1 == c2 and col[lk.a] == col[lk.b] == c1))

    n_ll, n_rr, n_lr = count("L", "L"), count("R", "R"), count("L", "R")
    gap_l = max(130, 60 + 20 * count("L", "H"))
    gap_r = max(130, 60 + 20 * count("H", "R"))
    outer_l = 30 + 14 * n_ll
    hub_w, hub_h = block_rect_size(by_id[hub], True)

    sizes = {b.id: block_rect_size(b, False) for b in left + right}
    col_h = lambda bs: sum(sizes[b.id][1] for b in bs) + 34 * max(0, len(bs) - 1)
    hub_h = max(hub_h, 30 + 22 * (count("L", "H") + count("H", "R")) // 2)
    total_h = max(col_h(left), col_h(right), hub_h)

    x_l = 40 + outer_l
    x_h = x_l + W + gap_l if left else x_l
    x_r = x_h + hub_w + gap_r
    rects: dict[str, Rect] = {}

    def stack(bs, x, c):
        y = TOP + (total_h - col_h(bs)) / 2
        for b in bs:
            w, h = sizes[b.id]
            rects[b.id] = Rect(f"blk-{b.id}", x, y, w, h, c)
            y += h + 34

    stack(left, x_l, "L")
    stack(right, x_r, "R")
    rects[hub] = Rect(f"blk-{hub}", x_h, TOP + (total_h - hub_h) / 2, hub_w, hub_h, "H")
    content_bottom = TOP + total_h + 24 + 14 * n_lr
    y_bar = content_bottom + 40
    for i, b in enumerate(bottom):
        bw = max(360, hub_w + 160)
        rects[b.id] = Rect(f"blk-{b.id}", rects[hub].cx - bw / 2, y_bar + i * 56, bw, 40, "B")

    # Blocs
    for b in blocks:
        r = rects[b.id]
        if col[b.id] == "B":
            _, fill, stroke = CATEGORIES.get(b.category, CATEGORIES["other"])
            detail = ", ".join((f"{it.ref} " if detailed else "") + short(it.value, 26) for it in b.items[:4])
            scene.add(Shape(r.sid, "bar", r.x, r.y, r.w, r.h, label=f"{b.name} : {detail}" if detail else b.name,
                            fill=fill, stroke=stroke, block=b.id, z=3))
            for k, rail in enumerate(b.rails):
                bw = 8 + 6.2 * len(rail)
                scene.add(Shape(f"{r.sid}-badge-{k}", "badge", r.right - bw - 6, r.y - 8, bw, 16, label=rail,
                                fill=BADGE_FILL, stroke=BADGE_FILL, text_color="#ffffff", bold=True, font=9, radius=8, z=4))
        else:
            draw_block(scene, b, r, b.id == hub, detailed)

    # Liaisons
    router = Router()
    side_of: dict[str, tuple[str, str]] = {}
    for lk in links:
        a, b = rects[lk.a], rects[lk.b]
        ca, cb = col[lk.a], col[lk.b]
        if ca == cb == "L":
            s = ("left", "left")
        elif ca == cb == "R":
            s = ("right", "right")
        elif {ca, cb} == {"L", "R"}:
            s = ("bottom", "bottom")
        elif "B" in (ca, cb):
            s = ("bottom", "top") if cb == "B" else ("top", "bottom")
        else:
            s = sides(a, b)
        side_of[lk.id] = s
        router.want(a, s[0], lk.id, 0, b)
        router.want(b, s[1], lk.id, 1, a)
    router.solve({r.sid: r for r in rects.values()})

    # Alignement vertical hub -> barre du bas
    for lk in links:
        if side_of[lk.id] in (("bottom", "top"), ("top", "bottom")) and "B" in (col[lk.a], col[lk.b]):
            src_end, bar_end = (0, 1) if col[lk.b] == "B" else (1, 0)
            bar = rects[lk.b if bar_end == 1 else lk.a]
            sx, _ = router.ports[(lk.id, src_end)]
            _, by = router.ports[(lk.id, bar_end)]
            if bar.x + 8 < sx < bar.right - 8:
                router.ports[(lk.id, bar_end)] = (sx, by)

    gap_index: dict[tuple, list[Link]] = defaultdict(list)
    for lk in links:
        key = tuple(sorted((col[lk.a], col[lk.b])))
        gap_index[key].append(lk)
    for key, lst in gap_index.items():
        if key in (("H", "L"), ("H", "R")):
            pairs = []
            for lk in lst:
                p1, p2 = router.ports[(lk.id, 0)], router.ports[(lk.id, 1)]
                pl, pr = (p1, p2) if p1[0] <= p2[0] else (p2, p1)
                pairs.append((lk.id, pl, pr))
            rank = {lid: i for i, lid in enumerate(channel_order(pairs))}
            lst.sort(key=lambda lk: rank[lk.id])
        else:
            lst.sort(key=lambda lk: router.ports[(lk.id, 0)][1])
        for k, lk in enumerate(lst):
            p1, p2 = router.ports[(lk.id, 0)], router.ports[(lk.id, 1)]
            s1, s2 = side_of[lk.id]
            if key == ("H", "L"):
                ch = x_l + W + gap_l * (k + 1) / (len(lst) + 1)
            elif key == ("H", "R"):
                ch = x_h + hub_w + gap_r * (k + 1) / (len(lst) + 1)
            elif key == ("L", "L"):
                ch = x_l - 16 - 14 * k
            elif key == ("R", "R"):
                ch = x_r + W + 16 + 14 * k
            elif key == ("L", "R"):
                ch = TOP + total_h + 16 + 14 * k
            else:
                ch = (p1[1] + p2[1]) / 2
            pts = route(p1, p2, s1, s2, ch)
            a_s, a_e = arrows(lk.direction)
            wdt, dash = edge_style(lk.kind)
            n = 1 if lk.kind == "power" else lk.width
            lab, mark = place_label(pts, lk.label, n, left=(key == ("L", "L")))
            scene.edges.append(Edge(lk.id, lk.kind, pts, a_s, a_e, label=lk.label, label_pos=lab, mark=mark,
                                    width=wdt, dashed=dash, source=rects[lk.a].sid, target=rects[lk.b].sid))

    right_edge = (x_r + W + 30 + 14 * n_rr) if right else (x_h + hub_w + 50)
    board_bottom = (max(r.bottom for r in rects.values() if r.col == "B") + 30) if bottom else content_bottom + 10
    add_board(scene, right_edge, board_bottom, syn.title)
    scene.width = right_edge + 20
    kinds = {lk.kind for lk in links}
    add_legend_and_cartouche(scene, syn, view, kinds, {b.category for b in blocks}, board_bottom + 14, right_edge)
    return scene


# ----------------------------------------------------------------------------- arbre d'alimentation


def layout_power(syn: Synoptic, detailed: bool = False) -> Scene:
    view = "Arbre d'alimentation"
    scene = Scene(view, 0, 0)
    nodes = syn.power
    sources = [n for n in nodes if n.role == "source"]
    convs = [n for n in nodes if n.role == "converter"]
    loads = [n for n in nodes if n.role == "load"]
    producers: dict[str, list] = defaultdict(list)
    for n in sources + convs:
        for r in n.outputs:
            producers[r].append(n)

    level = {s.ref: 0 for s in sources}
    for _ in range(len(convs) + 2):
        for c in convs:
            level[c.ref] = 1 + max([level.get(p.ref, 0) for r in c.inputs for p in producers[r]] or [0])
    load_rails: list[str] = []
    for ld in loads:
        for r in ld.inputs:
            if r not in load_rails:
                load_rails.append(r)
    group_col = {r: 1 + max([level.get(p.ref, 0) for p in producers[r]] or [0]) for r in load_rails}

    columns: dict[int, list[tuple[str, object]]] = defaultdict(list)
    for s in sorted(sources, key=lambda s: s.outputs):
        columns[0].append(("node", s))
    for c in sorted(convs, key=lambda c: (level[c.ref], c.inputs)):
        columns[level[c.ref]].append(("node", c))
    for r in sorted(load_rails, key=lambda r: group_col[r]):
        columns[group_col[r]].append(("group", r))

    # Ordre dans les colonnes : barycentre des voisins (moins de croisements)
    def _key(kind, obj):
        return obj.ref if kind == "node" else f"rail:{obj}"

    nbrs: dict[str, set[str]] = defaultdict(set)
    for rail, prods in producers.items():
        cons = [c.ref for c in convs if rail in c.inputs] + ([f"rail:{rail}"] if rail in load_rails else [])
        for p in prods:
            for c in cons:
                nbrs[p.ref].add(c)
                nbrs[c].add(p.ref)
    for _ in range(3):
        pos = {_key(k, o): i for items in columns.values() for i, (k, o) in enumerate(items)}
        for c in sorted(columns):
            items = columns[c]
            def bary(it, pos=pos):
                ns = [pos[n] for n in nbrs[_key(*it)] if n in pos]
                return sum(ns) / len(ns) if ns else pos[_key(*it)]
            items.sort(key=bary)

    gap = 150
    rects: dict[str, Rect] = {}
    sizes: dict[str, tuple[float, float]] = {}
    loads_of = {r: [ld for ld in loads if r in ld.inputs] for r in load_rails}
    for col_items in columns.values():
        for kind, obj in col_items:
            if kind == "node":
                sizes[obj.ref] = (W, 50)
            else:
                n = len(loads_of[obj])
                sizes[f"rail:{obj}"] = (W + 30, HEAD + n * 26 + (n - 1) * 6 + PAD)
    col_heights = {}
    for c, items in columns.items():
        keys = [o.ref if k == "node" else f"rail:{o}" for k, o in items]
        col_heights[c] = sum(sizes[k][1] for k in keys) + 40 * (len(keys) - 1)
    total_h = max(col_heights.values() or [100])
    max_col = max(columns or [0])
    for c, items in columns.items():
        y = TOP + (total_h - col_heights[c]) / 2
        x = 50 + c * (W + gap)
        for kind, obj in items:
            key = obj.ref if kind == "node" else f"rail:{obj}"
            w, h = sizes[key]
            rects[key] = Rect(f"pw-{key}", x, y, w, h, str(c))
            y += h + 40

    cat_of_role = {"source": "interface", "converter": "power"}
    for kind_obj in [it for items in columns.values() for it in items]:
        kind, obj = kind_obj
        if kind == "node":
            r = rects[obj.ref]
            _, fill, stroke = CATEGORIES[cat_of_role[obj.role]]
            desc = " + ".join(obj.inputs) + " → " + " + ".join(obj.outputs) if obj.role == "converter" else "→ " + ", ".join(obj.outputs)
            scene.add(Shape(r.sid, "box", r.x, r.y, r.w, r.h, label=f"{short(obj.value, 20)}\n{desc}", sub=obj.ref,
                            fill=fill, stroke=stroke, block=obj.block, z=3))
        else:
            r = rects[f"rail:{obj}"]
            _, fill, stroke = CATEGORIES["sensors"]
            scene.add(Shape(r.sid, "group", r.x, r.y, r.w, r.h, label=f"CHARGES {obj}", fill=fill, stroke=stroke,
                            align="topleft", font=9.5, bold=True, text_color=stroke, z=1))
            total = 0.0
            known = True
            for i, ld in enumerate(loads_of[obj]):
                cur = f" · {_fmt_ma(ld.current_ma)}" if ld.current_ma is not None else ""
                if ld.current_ma is None:
                    known = False
                else:
                    total += ld.current_ma
                scene.add(Shape(f"{r.sid}-{ld.ref}", "box", r.x + 10, r.y + HEAD + i * 32, r.w - 20, 26,
                                label=f"{short(ld.value, 18)}{cur}", sub=ld.ref, block=ld.block, font=11, z=3))
            imax = next((p.imax_ma for p in producers[obj] if p.imax_ma), None)
            txt = f"Σ {_fmt_ma(total)}" + ("" if known else " (incomplet)")
            if imax:
                txt += f" / {_fmt_ma(imax)} ({100 * total / imax:.0f} %)"
            scene.add(Shape(f"{r.sid}-total", "text", r.x, r.bottom + 16, label=txt, align="start", font=10.5,
                            bold=True, z=5))

    # Liaisons : producteur -> consommateurs de chaque rail
    edges: list[tuple[str, str, str]] = []
    for rail, prods in producers.items():
        consumers = [c.ref for c in convs if rail in c.inputs]
        if rail in load_rails:
            consumers.append(f"rail:{rail}")
        for p in prods:
            for c in consumers:
                if c != p.ref:
                    edges.append((p.ref, c, rail))
        if "BAT" in rail.upper():
            for s in sources:
                if rail in s.outputs:
                    for p in prods:
                        if p.role == "converter":
                            edges.append((p.ref, s.ref, "charge"))
    router = Router()
    side_of = {}
    for i, (a, b, _) in enumerate(edges):
        ra, rb = rects[a], rects[b]
        s = sides(ra, rb)
        side_of[i] = s
        router.want(ra, s[0], str(i), 0, rb)
        router.want(rb, s[1], str(i), 1, ra)
    router.solve({r.sid: r for r in rects.values()})
    per_gap: dict[tuple, list[int]] = defaultdict(list)
    for i, (a, b, _) in enumerate(edges):
        per_gap[tuple(sorted((int(rects[a].col), int(rects[b].col))))].append(i)
    labelled: set[tuple[str, str]] = set()
    for (c1, c2), lst in per_gap.items():
        pairs = []
        for i in lst:
            p1, p2 = router.ports[(str(i), 0)], router.ports[(str(i), 1)]
            pl, pr = (p1, p2) if p1[0] <= p2[0] else (p2, p1)
            pairs.append((str(i), pl, pr))
        rank = {lid: n for n, lid in enumerate(channel_order(pairs))}
        lst.sort(key=lambda i: rank[str(i)])
        for k, i in enumerate(lst):
            a, b, rail = edges[i]
            x0 = 50 + c1 * (W + gap) + W + 15
            ch = x0 + (gap - 30) * (k + 1) / (len(lst) + 1) if c1 != c2 else rects[a].right + 20 + 12 * k
            pts = route(router.ports[(str(i), 0)], router.ports[(str(i), 1)], *side_of[i], ch)
            show = (a, rail) not in labelled
            labelled.add((a, rail))
            lab, _ = place_label(pts, rail if show else "", 1)
            scene.edges.append(Edge(f"P{i}", "power", pts, False, True, label=rail if show else "", label_pos=lab, width=2.6,
                                    source=rects[a].sid, target=rects[b].sid))

    right_edge = 50 + max_col * (W + gap) + W + 60
    bottom = TOP + total_h + 40
    add_board(scene, right_edge, bottom, syn.title)
    scene.width = right_edge + 20
    add_legend_and_cartouche(scene, syn, view, {"power"} if edges else set(), {"interface", "power", "sensors"} if nodes else set(),
                             bottom + 14, right_edge)
    return scene


def _fmt_ma(v: float) -> str:
    if v >= 1000:
        return f"{v / 1000:.2f} A".replace(".", ",")
    s = f"{v:.1f}".rstrip("0").rstrip(".")
    return s.replace(".", ",") + " mA"


# ----------------------------------------------------------------------------- vue bus


def layout_bus(syn: Synoptic, detailed: bool = False) -> Scene:
    view = "Synoptique des bus"
    scene = Scene(view, 0, 0)
    buses = syn.buses
    blocks = {b.id: b for b in syn.blocks}
    row_h = 100
    hub_h = max(100, len(buses) * row_h - 40)
    hub = Rect("bus-hub", 50, TOP, 210, hub_h)
    master = next((b.master for b in buses if b.master), "")
    hub_block = blocks.get(syn.hub or "")
    hub_item = next((it for it in (hub_block.items if hub_block else []) if it.ref == master), None)
    scene.add(Shape(hub.sid, "box", hub.x, hub.y, hub.w, hub.h, label=short(hub_item.value if hub_item else (hub_block.name if hub_block else "MCU"), 24),
                    sub=master, bold=True, font=15, block=syn.hub or "", z=3))
    max_x = hub.right + 100
    dir_of = {}
    for lk in syn.links:
        dir_of.setdefault((lk.kind, lk.instance), lk.direction)
    for i, bus in enumerate(buses):
        yb = TOP + i * row_h + 18
        y_box = yb + 22
        a_s, a_e = arrows(dir_of.get((bus.kind, bus.instance), "ab"))
        xs = []
        for j, d in enumerate(bus.devices):
            x = hub.right + 150 + j * 190
            blk = blocks.get(d.block)
            _, fill, stroke = CATEGORIES.get(blk.category if blk else "other", CATEGORIES["other"])
            lab = short(d.value, 20) + (f"\n@ {d.address}" if d.address else "")
            scene.add(Shape(f"bus-{i}-{d.ref}", "box", x, y_box, 170, 42, label=lab, sub=d.ref, fill=fill, stroke=stroke,
                            block=d.block, font=11.5, z=3))
            xs.append(x + 85)
            max_x = max(max_x, x + 170)
        if not xs:
            continue
        wdt, dash = edge_style(bus.kind)
        last = xs[-1]
        pts = [(hub.right, yb), (last, yb), (last, y_box)]
        lab_txt = bus.label
        scene.edges.append(Edge(f"B{i}", bus.kind, pts, a_s, a_e, label=lab_txt, label_pos=(hub.right + 12, yb - 6, "start"),
                                mark=(hub.right + 100, yb, len(bus.nets), False) if len(bus.nets) > 1 else None,
                                width=wdt, dashed=dash, source=hub.sid, target=f"bus-{i}-{bus.devices[-1].ref}"))
        for j, x in enumerate(xs[:-1]):
            scene.edges.append(Edge(f"B{i}-{j}", bus.kind, [(x, yb), (x, y_box)], False, a_e, width=wdt, dashed=dash,
                                    target=f"bus-{i}-{bus.devices[j].ref}"))
            scene.add(Shape(f"B{i}-{j}-dot", "dot", x - 3, yb - 3, 6, 6, fill="#000000", z=4))
        if bus.pullups and bus.kind == "i2c":
            scene.add(Shape(f"B{i}-pu", "text", last + 95, yb + 4, label="pull-up " + ", ".join(bus.pullups), align="start",
                            font=10, text_color="#444444", z=5))
            max_x = max(max_x, last + 95 + 60 + 7 * len(bus.pullups))
    right_edge = max_x + 50
    bottom = TOP + max(hub_h, len(buses) * row_h) + 20
    add_board(scene, right_edge, bottom, syn.title)
    scene.width = right_edge + 20
    cats = {blocks[d.block].category for b in buses for d in b.devices if d.block in blocks} | {"hub"}
    add_legend_and_cartouche(scene, syn, view, {b.kind for b in buses}, cats, bottom + 14, right_edge)
    return scene


VIEWS = {
    "fonctionnel": lambda s: layout_functional(s, False),
    "complet": lambda s: layout_functional(s, True),
    "alimentation": layout_power,
    "bus": layout_bus,
}

__all__ = ["LINK_KINDS", "VIEWS", "layout_bus", "layout_functional", "layout_power"]
