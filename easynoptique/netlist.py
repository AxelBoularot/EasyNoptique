"""Lecture d'une netlist KiCad au format XML (``kicad-cli sch export netlist --format kicadxml``)."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Pin:
    ref: str
    pin: str
    function: str = ""
    type: str = ""


@dataclass
class Component:
    ref: str
    value: str = ""
    footprint: str = ""
    description: str = ""
    fields: dict[str, str] = field(default_factory=dict)
    sheet_path: str = "/"
    sheet_file: str = ""

    @property
    def prefix(self) -> str:
        out = ""
        for ch in self.ref:
            if ch.isalpha() or ch in "_#":
                out += ch
            else:
                break
        return out.upper()

    def field(self, *names: str) -> str:
        """Valeur du premier champ trouvé parmi ``names`` (insensible à la casse)."""
        lower = {k.lower(): v for k, v in self.fields.items()}
        for name in names:
            v = lower.get(name.lower())
            if v not in (None, ""):
                return v
        return ""


@dataclass
class Net:
    code: str
    name: str
    pins: list[Pin] = field(default_factory=list)

    @property
    def leaf(self) -> str:
        """Nom sans le chemin de feuille : ``/alim/VSYS`` -> ``VSYS``."""
        return self.name.rstrip("/").rsplit("/", 1)[-1] if self.name else ""

    @property
    def is_auto(self) -> bool:
        return self.name.startswith(("Net-(", "unconnected-", "/Net-(")) or "Net-(" in self.name


@dataclass
class Netlist:
    components: dict[str, Component]
    nets: list[Net]
    source: str = ""
    title: str = ""
    rev: str = ""
    date: str = ""
    company: str = ""

    @property
    def project_name(self) -> str:
        if self.title:
            return self.title
        return Path(self.source).stem if self.source else "projet"


def _text(node: ET.Element | None, tag: str) -> str:
    if node is None:
        return ""
    child = node.find(tag)
    return (child.text or "").strip() if child is not None and child.text else ""


def parse_netlist(path: str | Path) -> Netlist:
    root = ET.parse(str(path)).getroot()
    if root.tag != "export":
        raise ValueError(f"{path} n'est pas une netlist KiCad XML (balise racine <{root.tag}>)")

    design = root.find("design")
    source = _text(design, "source")
    title = rev = date = company = ""
    if design is not None:
        for sheet in design.findall("sheet"):
            if sheet.get("number") in ("1", None):
                tb = sheet.find("title_block")
                title, rev = _text(tb, "title"), _text(tb, "rev")
                date, company = _text(tb, "date"), _text(tb, "company")
                break

    components: dict[str, Component] = {}
    comps = root.find("components")
    for c in comps.findall("comp") if comps is not None else []:
        ref = c.get("ref", "")
        fields = {f.get("name", ""): (f.text or "").strip() for f in c.findall("fields/field")}
        desc = ""
        libsource = c.find("libsource")
        if libsource is not None:
            desc = libsource.get("description", "")
        sheet_file = ""
        for prop in c.findall("property"):
            name, value = prop.get("name", ""), prop.get("value", "")
            if name == "Sheetfile":
                sheet_file = value
            elif name in ("ki_description", "Description") and not desc:
                desc = value
            elif name not in ("Sheetname", "Sheetfile") and name not in fields and not name.startswith("ki_"):
                fields[name] = value
        if not desc:
            desc = _text(c, "description") or fields.get("Description", "")
        sp = c.find("sheetpath")
        components[ref] = Component(
            ref=ref,
            value=_text(c, "value"),
            footprint=_text(c, "footprint"),
            description=desc,
            fields=fields,
            sheet_path=sp.get("names", "/") if sp is not None else "/",
            sheet_file=sheet_file,
        )

    nets: list[Net] = []
    nets_el = root.find("nets")
    for n in nets_el.findall("net") if nets_el is not None else []:
        pins = [
            Pin(ref=p.get("ref", ""), pin=p.get("pin", ""), function=p.get("pinfunction", ""), type=p.get("pintype", ""))
            for p in n.findall("node")
        ]
        nets.append(Net(code=n.get("code", ""), name=n.get("name", ""), pins=pins))

    return Netlist(components=components, nets=nets, source=source, title=title, rev=rev, date=date, company=company)
