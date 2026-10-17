"""Export draw.io (diagrams.net) : une page par vue, un calque par type de liaison."""
from __future__ import annotations

from html import escape

from .model import LINK_KINDS
from .scene import Scene, Shape


def _a(v: str) -> str:
    return escape(v, quote=True)


def _n(v: float) -> str:
    return f"{v:.1f}".rstrip("0").rstrip(".")


def _vertex_style(s: Shape) -> str:
    bold = "fontStyle=1;" if s.bold else ""
    dash = "dashed=1;" if s.dashed else ""
    common = f"whiteSpace=wrap;html=1;fontFamily=Helvetica;fontSize={_n(s.font)};{bold}{dash}"
    if s.kind == "board":
        return f"rounded=1;absoluteArcSize=1;arcSize={_n(s.radius * 2)};fillColor={s.fill};strokeColor={s.stroke};strokeWidth=1.5;{common}"
    if s.kind == "group":
        return (f"rounded=0;fillColor={s.fill};strokeColor={s.stroke};verticalAlign=top;align=left;spacingLeft=6;"
                f"spacingTop=-3;fontColor={s.text_color};{common}")
    if s.kind == "badge":
        return f"rounded=1;arcSize=50;fillColor={s.fill};strokeColor={s.stroke};fontColor={s.text_color};{common}"
    if s.kind == "text":
        align = {"start": "left", "middle": "center", "center": "center", "end": "right"}.get(s.align, "left")
        return f"text;align={align};verticalAlign=middle;fontColor={s.text_color};{common}"
    if s.kind == "dot":
        return "ellipse;fillColor=#000000;strokeColor=none;html=1;"
    if s.kind == "cell":
        return f"rounded=0;fillColor=#ffffff;strokeColor=#000000;align=left;spacingLeft=6;{common}"
    return f"rounded=0;fillColor={s.fill};strokeColor={s.stroke};{common}"


def _vertex_value(s: Shape) -> str:
    label = escape(s.label).replace("\n", "<br>")
    if s.kind == "cell":
        return f'<font style="font-size:8px" color="#666666">{escape(s.sub)}</font><br><b>{label}</b>'
    if s.sub and s.kind in ("box", "bar"):
        return f'<font style="font-size:8px" color="#555555">{escape(s.sub)}</font><br>{label}'
    return label


def _geom(s: Shape) -> tuple[float, float, float, float]:
    if s.kind == "text":
        w = max(20, 6.6 * len(s.label) * s.font / 10)
        x = s.x - (w / 2 if s.align in ("middle", "center") else (w if s.align == "end" else 0))
        return x, s.y - s.font, w, s.font * 1.6
    return s.x, s.y, s.w, s.h


def scene_to_diagram(scene: Scene, index: int) -> str:
    cells = ['<mxCell id="0"/>', '<mxCell id="1" value="Blocs" parent="0"/>']
    kinds = []
    for e in scene.edges:
        if e.kind != "legend" and e.kind not in kinds:
            kinds.append(e.kind)
    for k in kinds:
        cells.append(f'<mxCell id="layer-{index}-{k}" value="{_a(LINK_KINDS.get(k, k))}" parent="0"/>')
    rects = {}
    for s in sorted(scene.shapes, key=lambda s: s.z):
        x, y, w, h = _geom(s)
        cid = f"v{index}-{s.id}"
        rects[s.id] = (cid, x, y, w, h)
        cells.append(f'<mxCell id="{_a(cid)}" value="{_a(_vertex_value(s))}" style="{_a(_vertex_style(s))}" vertex="1" parent="1">'
                     f'<mxGeometry x="{_n(x)}" y="{_n(y)}" width="{_n(w)}" height="{_n(h)}" as="geometry"/></mxCell>')
    for e in scene.edges:
        parent = f"layer-{index}-{e.kind}" if e.kind != "legend" else "1"
        style = [f"endArrow={'block' if e.arrow_end else 'none'}", "endFill=1",
                 f"startArrow={'block' if e.arrow_start else 'none'}", "startFill=1", "rounded=0", "html=1",
                 f"strokeWidth={_n(e.width)}", "fontFamily=Helvetica", "fontSize=10", "fontStyle=1",
                 "labelBackgroundColor=#f1f8ef", "endSize=6", "startSize=6"]
        if e.dashed:
            style.append("dashed=1")
        conn = ""
        (sx, sy), (tx, ty) = e.points[0], e.points[-1]
        for attr, sid, (px, py), prefix in (("source", e.source, (sx, sy), "exit"), ("target", e.target, (tx, ty), "entry")):
            if sid and sid in rects:
                cid, rx, ry, rw, rh = rects[sid]
                if rx - 1 <= px <= rx + rw + 1 and ry - 1 <= py <= ry + rh + 1:
                    conn += f' {attr}="{_a(cid)}"'
                    style += [f"{prefix}X={(px - rx) / rw:.4f}", f"{prefix}Y={(py - ry) / rh:.4f}", f"{prefix}Dx=0", f"{prefix}Dy=0",
                              f"{prefix}Perimeter=0"]
        value = e.label
        if e.mark and e.mark[2] > 1:
            value = f"{value} /{e.mark[2]}".strip()
        pts = "".join(f'<mxPoint x="{_n(x)}" y="{_n(y)}"/>' for x, y in e.points[1:-1])
        cells.append(f'<mxCell id="e{index}-{_a(e.id)}" value="{_a(value)}" style="{_a(";".join(style) + ";")}" edge="1" '
                     f'parent="{_a(parent)}"{conn}><mxGeometry relative="1" as="geometry">'
                     f'<mxPoint x="{_n(sx)}" y="{_n(sy)}" as="sourcePoint"/><mxPoint x="{_n(tx)}" y="{_n(ty)}" as="targetPoint"/>'
                     + (f'<Array as="points">{pts}</Array>' if pts else "") + "</mxGeometry></mxCell>")
    return (f'<diagram id="easynoptique-{index}" name="{_a(scene.name)}"><mxGraphModel dx="1000" dy="800" grid="1" '
            f'gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
            f'pageWidth="{int(scene.width)}" pageHeight="{int(scene.height)}" math="0" shadow="0"><root>'
            + "".join(cells) + "</root></mxGraphModel></diagram>")


def render_drawio(scenes: list[Scene]) -> str:
    body = "".join(scene_to_diagram(s, i) for i, s in enumerate(scenes))
    return f'<mxfile host="EasyNoptique" type="device">{body}</mxfile>\n'
