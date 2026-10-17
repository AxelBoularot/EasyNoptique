"""Modèle unifié du synoptique : blocs, liaisons, rails, convertisseurs, bus."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

# Catégories de blocs : libellé et couleurs (palette standard draw.io : remplissage, contour)
CATEGORIES: dict[str, tuple[str, str, str]] = {
    "hub": ("Traitement", "#ffffff", "#000000"),
    "power": ("Alimentation", "#f8cecc", "#b85450"),
    "memory": ("Mémoire", "#ffe6cc", "#d79b00"),
    "sensors": ("Capteurs", "#dae8fc", "#6c8ebf"),
    "radio": ("Radio", "#97d077", "#5a8f3c"),
    "hmi": ("IHM", "#d5e8d4", "#82b366"),
    "interface": ("Interfaces", "#fff2cc", "#d6b656"),
    "debug": ("Debug", "#e1d5e7", "#9673a6"),
    "other": ("Autres", "#f5f5f5", "#666666"),
}

# Types de liaisons : libellé affiché
LINK_KINDS: dict[str, str] = {
    "power": "Alimentation",
    "i2c": "I²C",
    "spi": "SPI",
    "uart": "UART",
    "usb": "USB",
    "can": "CAN",
    "swd": "SWD",
    "jtag": "JTAG",
    "analog": "Analogique",
    "gpio": "GPIO",
}


@dataclass
class Item:
    """Composant actif affiché dans un bloc."""
    ref: str
    value: str
    description: str = ""


@dataclass
class Block:
    id: str
    name: str
    category: str = "other"
    sheet: str = ""
    items: list[Item] = field(default_factory=list)
    components: list[str] = field(default_factory=list)
    rails: list[str] = field(default_factory=list)  # rails d'alim distribués par pastille
    hidden: bool = False


@dataclass
class Link:
    id: str
    a: str  # bloc source (maître)
    b: str  # bloc destination
    kind: str
    label: str
    instance: str = ""
    nets: list[str] = field(default_factory=list)
    direction: str = "ab"  # ab, ba, both, none
    note: str = ""

    @property
    def width(self) -> int:
        return len(self.nets)


@dataclass
class PowerNode:
    ref: str
    value: str
    role: str  # source, converter, load
    block: str = ""
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    current_ma: float | None = None
    imax_ma: float | None = None


@dataclass
class BusDevice:
    ref: str
    value: str
    block: str
    address: str = ""


@dataclass
class Bus:
    kind: str
    instance: str
    label: str
    master: str  # ref du maître
    nets: list[str] = field(default_factory=list)
    devices: list[BusDevice] = field(default_factory=list)
    pullups: list[str] = field(default_factory=list)


@dataclass
class Synoptic:
    project: str
    title: str = ""
    rev: str = ""
    date: str = ""
    company: str = ""
    hub: str | None = None
    blocks: list[Block] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)
    rails: list[str] = field(default_factory=list)
    power: list[PowerNode] = field(default_factory=list)
    buses: list[Bus] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def block(self, bid: str) -> Block:
        return next(b for b in self.blocks if b.id == bid)

    def to_dict(self) -> dict:
        return asdict(self)
