"""Rendu d'une scène en SVG autonome."""
from __future__ import annotations

from html import escape

from .scene import Edge, Scene, Shape

FONT = "Helvetica, Arial, sans-serif"
HALO = "#f1f8ef"


def _num(v: float) -> str:
    return f"{v:.1f}".rstrip("0").rstrip(".")


def _lines(s: Shape, cx: float, cy: float, size: float, weight: str) -> str:
    lines = s.label.split("\n")
    lh = size * 1.2
    y0 = cy - (len(lines) - 1) * lh / 2 + size * 0.35
    out = []
    for i, line in enumerate(lines):
        sz = size if i == 0 else size - 1.5
        out.append(f'<text x="{_num(cx)}" y="{_num(y0 + i * lh)}" text-anchor="middle" font-size="{_num(sz)}" '
                   f'font-weight="{weight if i == 0 else "normal"}" fill="{s.text_color}">{escape(line)}</text>')
    return "".join(out)


def shape_svg(s: Shape) -> str:
    data = f' data-block="{escape(s.block)}" class="blk"' if s.block else ""
    weight = "bold" if s.bold else "normal"
    dash = ' stroke-dasharray="5 3"' if s.dashed else ""
    if s.kind == "board":
        return (f'<rect x="{_num(s.x)}" y="{_num(s.y)}" width="{_num(s.w)}" height="{_num(s.h)}" rx="{_num(s.radius)}" '
                f'fill="{s.fill}" stroke="{s.stroke}" stroke-width="1.5"/>')
    if s.kind == "group":
        return (f'<g{data}><rect x="{_num(s.x)}" y="{_num(s.y)}" width="{_num(s.w)}" height="{_num(s.h)}" fill="{s.fill}" '
                f'stroke="{s.stroke}" stroke-width="1.3"/><text x="{_num(s.x + 8)}" y="{_num(s.y + 15)}" font-size="{_num(s.font)}" '
                f'font-weight="bold" letter-spacing="0.6" fill="{s.text_color}">{escape(s.label)}</text></g>')
    if s.kind in ("box", "bar"):
        sw = "1.6" if s.bold else "1.2"
        out = [f'<g{data}><rect x="{_num(s.x)}" y="{_num(s.y)}" width="{_num(s.w)}" height="{_num(s.h)}" fill="{s.fill}" '
               f'stroke="{s.stroke}" stroke-width="{sw}"{dash}/>']
        if s.label:
            out.append(_lines(s, s.x + s.w / 2, s.y + s.h / 2 + (2 if s.sub else 0), s.font, weight))
        if s.sub:
            out.append(f'<text x="{_num(s.x + 4)}" y="{_num(s.y + 10)}" font-size="8.5" fill="#555555">{escape(s.sub)}</text>')
        out.append("</g>")
        return "".join(out)
    if s.kind == "badge":
        return (f'<g class="badge"><rect x="{_num(s.x)}" y="{_num(s.y)}" width="{_num(s.w)}" height="{_num(s.h)}" '
                f'rx="{_num(s.h / 2)}" fill="{s.fill}"/><text x="{_num(s.x + s.w / 2)}" y="{_num(s.y + s.h / 2 + 3.2)}" '
                f'text-anchor="middle" font-size="{_num(s.font)}" font-weight="bold" fill="{s.text_color}">{escape(s.label)}</text></g>')
    if s.kind == "text":
        anchor = {"start": "start", "middle": "middle", "end": "end", "center": "middle"}.get(s.align, "start")
        return (f'<text x="{_num(s.x)}" y="{_num(s.y)}" text-anchor="{anchor}" font-size="{_num(s.font)}" '
                f'font-weight="{weight}" fill="{s.text_color}">{escape(s.label)}</text>')
    if s.kind == "dot":
        return f'<circle cx="{_num(s.x + s.w / 2)}" cy="{_num(s.y + s.h / 2)}" r="{_num(s.w / 2)}" fill="{s.fill}"/>'
    if s.kind == "cell":
        return (f'<g><rect x="{_num(s.x)}" y="{_num(s.y)}" width="{_num(s.w)}" height="{_num(s.h)}" fill="#ffffff" '
                f'stroke="#000000" stroke-width="1.2"/><text x="{_num(s.x + 6)}" y="{_num(s.y + 12)}" font-size="8" '
                f'letter-spacing="0.6" fill="#666666">{escape(s.sub)}</text><text x="{_num(s.x + 6)}" y="{_num(s.y + 29)}" '
                f'font-size="{_num(s.font)}" font-weight="bold">{escape(s.label)}</text></g>')
    return ""


def edge_svg(e: Edge, marker_id: str) -> str:
    d = "M" + " L".join(f"{_num(x)} {_num(y)}" for x, y in e.points)
    attrs = [f'd="{d}"', 'fill="none"', 'stroke="#000000"', f'stroke-width="{_num(e.width)}"', 'stroke-linejoin="round"']
    if e.dashed:
        attrs.append('stroke-dasharray="6 4"')
    if e.arrow_end:
        attrs.append(f'marker-end="url(#{marker_id})"')
    if e.arrow_start:
        attrs.append(f'marker-start="url(#{marker_id})"')
    out = [f'<g class="edge k-{escape(e.kind)}" data-kind="{escape(e.kind)}"><path {" ".join(attrs)}/>']
    if e.mark:
        x, y, n, vertical = e.mark
        if vertical:
            out.append(f'<line x1="{_num(x - 6)}" y1="{_num(y + 4)}" x2="{_num(x + 6)}" y2="{_num(y - 4)}" stroke="#000000" stroke-width="1.2"/>')
            out.append(f'<text x="{_num(x + 8)}" y="{_num(y + 3)}" font-size="9">{n}</text>')
        else:
            out.append(f'<line x1="{_num(x - 4)}" y1="{_num(y + 6)}" x2="{_num(x + 4)}" y2="{_num(y - 6)}" stroke="#000000" stroke-width="1.2"/>')
            out.append(f'<text x="{_num(x + 3)}" y="{_num(y + 15)}" font-size="9">{n}</text>')
    if e.label and e.label_pos:
        x, y, anchor = e.label_pos
        out.append(f'<text x="{_num(x)}" y="{_num(y)}" text-anchor="{anchor}" font-size="10" font-weight="bold" '
                   f'paint-order="stroke" stroke="{HALO}" stroke-width="3" stroke-linejoin="round">{escape(e.label)}</text>')
    out.append("</g>")
    return "".join(out)


def render_svg(scene: Scene, element_id: str = "") -> str:
    mid = f"arrow-{element_id or 'svg'}"
    w, h = _num(scene.width), _num(scene.height)
    ident = f' id="{escape(element_id)}"' if element_id else ""
    out = [f'<svg xmlns="http://www.w3.org/2000/svg"{ident} viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
           f'font-family="{FONT}" role="img" aria-label="{escape(scene.name)}">',
           f'<title>{escape(scene.name)}</title>',
           f'<defs><marker id="{mid}" viewBox="0 0 10 10" refX="9.5" refY="5" markerWidth="9" markerHeight="9" '
           f'orient="auto-start-reverse" markerUnits="userSpaceOnUse"><path d="M0 0 L10 5 L0 10 z" fill="#000000"/></marker></defs>',
           f'<rect width="{w}" height="{h}" fill="#ffffff"/>']
    shapes = sorted(scene.shapes, key=lambda s: s.z)
    out += [shape_svg(s) for s in shapes if s.z < 2]
    out += [edge_svg(e, mid) for e in scene.edges]
    out += [shape_svg(s) for s in shapes if s.z >= 2]
    out.append("</svg>")
    return "\n".join(out)
