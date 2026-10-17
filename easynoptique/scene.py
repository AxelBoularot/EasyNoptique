"""Scène graphique neutre : produite par le placement, rendue en SVG, draw.io ou HTML."""
from __future__ import annotations

from dataclasses import dataclass, field

Point = tuple[float, float]


@dataclass
class Shape:
    id: str
    kind: str  # board, group, box, bar, badge, text, dot, cell
    x: float
    y: float
    w: float = 0
    h: float = 0
    label: str = ""
    sub: str = ""  # petit texte en haut à gauche (référence)
    fill: str = "#ffffff"
    stroke: str = "#000000"
    bold: bool = False
    font: float = 12
    align: str = "center"  # center, topleft, left, start, middle, end (pour text)
    text_color: str = "#000000"
    radius: float = 0
    dashed: bool = False
    block: str = ""  # identifiant du bloc (interactivité)
    z: int = 3


@dataclass
class Edge:
    id: str
    kind: str  # type de liaison (power, i2c, …) ou "legend"
    points: list[Point]
    arrow_start: bool = False
    arrow_end: bool = True
    label: str = ""
    label_pos: tuple[float, float, str] | None = None  # x, y, ancre
    mark: tuple[float, float, int, bool] | None = None  # x, y, nombre de fils, segment vertical ?
    width: float = 1.3
    dashed: bool = False
    source: str = ""
    target: str = ""


@dataclass
class Scene:
    name: str
    width: float
    height: float
    shapes: list[Shape] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)

    def add(self, shape: Shape) -> Shape:
        self.shapes.append(shape)
        return shape

    def shape(self, sid: str) -> Shape | None:
        return next((s for s in self.shapes if s.id == sid), None)
