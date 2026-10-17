"""Lecture du circuit ouvert dans l'éditeur de PCB (API Python ``pcbnew``, KiCad 6 à 9).

Le PCB contient tout ce dont l'analyse a besoin, à condition qu'il soit à jour par rapport au schéma
(Outils > Mettre à jour le PCB depuis le schéma) : références, valeurs, champs, feuille d'origine,
et pour chaque pastille son net, sa fonction de broche et son type électrique.
Aucune dépendance à ``kicad-cli`` : le plugin marche avec le Python fourni par KiCad.
"""
from __future__ import annotations

from pathlib import Path

from .netlist import Component, Net, Netlist, Pin


def _call(obj, *names, default=""):
    """Appelle la première méthode disponible (l'API change selon les versions de KiCad)."""
    for name in names:
        fn = getattr(obj, name, None)
        if fn is None:
            continue
        try:
            value = fn()
        except Exception:
            continue
        if value is not None:
            return value
    return default


def _fields(fp) -> dict[str, str]:
    out: dict[str, str] = {}
    try:  # KiCad 8/9 : objets champ
        for f in fp.GetFields():
            name, text = str(_call(f, "GetName")), str(_call(f, "GetText"))
            if name and name not in ("Reference", "Value", "Footprint", "Datasheet"):
                out[name] = text
    except Exception:
        pass
    if not out:
        try:  # KiCad 6/7 : propriétés texte
            props = fp.GetProperties()
            items = props.items() if hasattr(props, "items") else []
            for k, v in items:
                out[str(k)] = str(v)
        except Exception:
            pass
    return out


def netlist_from_board(board) -> Netlist:
    components: dict[str, Component] = {}
    nets: dict[str, Net] = {}
    for fp in board.GetFootprints():
        ref = str(_call(fp, "GetReference"))
        if not ref or "*" in ref or ref.startswith("#"):
            continue
        fields = _fields(fp)
        sheet = str(_call(fp, "GetSheetname") or fields.pop("Sheetname", "") or "")
        sheet_file = str(_call(fp, "GetSheetfile") or fields.pop("Sheetfile", "") or "")
        fields.pop("Sheetname", None)
        fields.pop("Sheetfile", None)
        sheet_path = "/" if not sheet or sheet_file.endswith(Path(str(_call(board, "GetFileName"))).stem + ".kicad_sch") \
            else f"/{sheet}/"
        components[ref] = Component(
            ref=ref,
            value=str(_call(fp, "GetValue")),
            footprint=str(_call(fp, "GetFPIDAsString")),
            description=fields.get("Description", "") or str(_call(fp, "GetLibDescription")),
            fields=fields,
            sheet_path=sheet_path,
            sheet_file=sheet_file,
        )
        for pad in fp.Pads():
            net_name = str(_call(pad, "GetNetname"))
            if not net_name:
                continue
            pin_type = str(_call(pad, "GetPinType")).split("+")[0].strip().lower()
            pin = Pin(ref=ref, pin=str(_call(pad, "GetNumber", "GetName", "GetPadName")),
                      function=str(_call(pad, "GetPinFunction")), type=pin_type)
            net = nets.setdefault(net_name, Net(code=str(len(nets) + 1), name=net_name))
            if not any(p.ref == pin.ref and p.pin == pin.pin for p in net.pins):
                net.pins.append(pin)

    tb = _call(board, "GetTitleBlock", default=None)
    source = str(_call(board, "GetFileName"))
    title = str(_call(tb, "GetTitle")) if tb is not None else ""
    return Netlist(
        components=components,
        nets=list(nets.values()),
        source=source,
        title=title or (Path(source).stem if source else ""),
        rev=str(_call(tb, "GetRevision")) if tb is not None else "",
        date=str(_call(tb, "GetDate")) if tb is not None else "",
        company=str(_call(tb, "GetCompany")) if tb is not None else "",
    )
