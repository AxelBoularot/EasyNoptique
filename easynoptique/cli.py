"""Ligne de commande : ``easynoptique analyse|render|dump <projet>``."""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

from . import __version__
from .analyze import analyze
from .kicad_cli import load
from .layout import VIEWS
from .render_drawio import render_drawio
from .render_svg import render_svg
from .report import render_report
from .rules import Rules


def slug(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "-", ascii_text).strip("-").lower() or "projet"


def _rules_for(src: str, explicit: str | None) -> Rules:
    return Rules.load(explicit or Rules.default_path(src))


def generate(src: str, out_dir: str | None = None, formats=("svg", "drawio", "html", "json"), rules: str | None = None,
             views=tuple(VIEWS)) -> dict[str, Path]:
    """Analyse le projet et écrit les fichiers demandés. Renvoie {nom: chemin}."""
    base = Path(src)
    out = Path(out_dir) if out_dir else (base if base.is_dir() else base.parent) / "synoptique"
    return generate_from_netlist(load(src), out, _rules_for(src, rules), formats, views)


def generate_from_netlist(nl, out: Path, rules: Rules | None = None, formats=("svg", "drawio", "html", "json"),
                          views=tuple(VIEWS)) -> dict[str, Path]:
    """Écrit les synoptiques d'une netlist déjà chargée (utilisé aussi par le plugin KiCad)."""
    syn = analyze(nl, rules or Rules())
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    stem = slug(syn.project or "projet")
    scenes = {v: VIEWS[v](syn) for v in views}
    written: dict[str, Path] = {}
    if "svg" in formats:
        for v, sc in scenes.items():
            p = out / f"{stem}-{v}.svg"
            p.write_text(render_svg(sc), encoding="utf-8")
            written[f"svg:{v}"] = p
    if "drawio" in formats:
        p = out / f"{stem}.drawio"
        p.write_text(render_drawio(list(scenes.values())), encoding="utf-8")
        written["drawio"] = p
    if "html" in formats:
        p = out / f"{stem}.html"
        p.write_text(render_report(syn, scenes), encoding="utf-8")
        written["html"] = p
    if "json" in formats:
        p = out / f"{stem}.json"
        p.write_text(json.dumps(syn.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        written["json"] = p
    return written


def _cmd_dump(a) -> int:
    nl = load(a.source)
    print(f"Projet : {nl.project_name}  (rév. {nl.rev or '—'})")
    print(f"\n{len(nl.components)} composants")
    for c in nl.components.values():
        print(f"  {c.ref:<6} {c.value:<28} {c.sheet_path}")
    print(f"\n{len(nl.nets)} nets")
    for n in nl.nets:
        pins = ", ".join(f"{p.ref}.{p.pin}" + (f"({p.function})" if p.function else "") for p in n.pins)
        print(f"  {n.name:<24} {pins}")
    return 0


def _cmd_analyse(a) -> int:
    syn = analyze(load(a.source), _rules_for(a.source, a.rules))
    if a.json:
        print(json.dumps(syn.to_dict(), ensure_ascii=False, indent=2))
        return 0
    names = {b.id: b.name for b in syn.blocks}
    print(f"{syn.title}  ·  hub : {names.get(syn.hub or '', '—')}\n")
    print("Blocs :")
    for b in syn.blocks:
        print(f"  [{b.category:<9}] {b.name:<16} {', '.join(f'{i.ref} {i.value}' for i in b.items)}")
    print("\nLiaisons :")
    arrow = {"ab": "──▶", "ba": "◀──", "both": "◀─▶", "none": "───"}
    for lk in syn.links:
        print(f"  {names[lk.a]:<14} {arrow[lk.direction]} {names[lk.b]:<14} {lk.label:<14} /{lk.width}  {', '.join(lk.nets)}")
    print("\nAlimentation :")
    for p in syn.power:
        io = f"{'+'.join(p.inputs) or '·'} → {'+'.join(p.outputs) or '·'}"
        cur = f"  {p.current_ma:g} mA" if p.current_ma is not None else ""
        print(f"  {p.role:<9} {p.ref:<5} {p.value:<24} {io}{cur}")
    if syn.warnings:
        print("\nAlertes :")
        for w in syn.warnings:
            print(f"  ⚠ {w}")
    return 0


def _cmd_render(a) -> int:
    formats = tuple(f.strip() for f in a.formats.split(","))
    views = tuple(v.strip() for v in a.views.split(",")) if a.views else tuple(VIEWS)
    written = generate(a.source, a.output, formats, a.rules, views)
    for k, p in written.items():
        print(f"{k:<20} {p}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="easynoptique", description="Synoptiques automatiques pour projets KiCad.")
    ap.add_argument("--version", action="version", version=f"easynoptique {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("dump", help="affiche composants et nets lus dans le projet")
    p.add_argument("source", help=".kicad_pro, .kicad_sch ou netlist .xml")
    p.set_defaults(func=_cmd_dump)

    p = sub.add_parser("analyse", help="affiche les blocs, liaisons et l'arbre d'alimentation détectés")
    p.add_argument("source")
    p.add_argument("--rules", help="fichier de règles YAML (défaut : <projet>.easynoptique.yaml)")
    p.add_argument("--json", action="store_true", help="sortie JSON")
    p.set_defaults(func=_cmd_analyse)

    p = sub.add_parser("render", help="génère les synoptiques (SVG, draw.io, HTML, JSON)")
    p.add_argument("source")
    p.add_argument("-o", "--output", help="dossier de sortie (défaut : <projet>/synoptique)")
    p.add_argument("-f", "--formats", default="svg,drawio,html,json")
    p.add_argument("--views", help="fonctionnel,complet,alimentation,bus")
    p.add_argument("--rules")
    p.set_defaults(func=_cmd_render)

    a = ap.parse_args(argv)
    try:
        return a.func(a)
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        print(f"Erreur : {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
