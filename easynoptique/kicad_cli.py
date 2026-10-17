"""Accès au projet KiCad via ``kicad-cli`` (fourni avec KiCad 7 et plus)."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .netlist import Netlist, parse_netlist

_CANDIDATES = [
    r"C:\Program Files\KiCad\9.0\bin\kicad-cli.exe",
    r"C:\Program Files\KiCad\8.0\bin\kicad-cli.exe",
    "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli",
    "/usr/bin/kicad-cli",
    "/usr/local/bin/kicad-cli",
]


def _windows_candidates() -> list[str]:
    """Toutes les installations KiCad Windows (toutes versions, machine ou utilisateur), la plus récente d'abord."""
    roots = [os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", ""),
             os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs"), r"D:\Program Files"]
    found = []
    for root in filter(None, roots):
        base = Path(root) / "KiCad"
        if base.is_dir():
            found += list(base.glob("*/bin/kicad-cli.exe")) + list(base.glob("bin/kicad-cli.exe"))

    def version(p: Path):
        try:
            return tuple(int(x) for x in p.parent.parent.name.split("."))
        except ValueError:
            return (0,)

    return [str(p) for p in sorted(found, key=version, reverse=True)]


def find_kicad_cli() -> str | None:
    env = os.environ.get("KICAD_CLI")
    if env and Path(env).exists():
        return env
    found = shutil.which("kicad-cli")
    if found:
        return found
    candidates = (_windows_candidates() if os.name == "nt" else []) + _CANDIDATES
    return next((c for c in candidates if Path(c).exists()), None)


def export_netlist(schematic: Path, output: Path) -> Path:
    cli = find_kicad_cli()
    if not cli:
        raise RuntimeError(
            "kicad-cli introuvable. Installez KiCad 7+ ou indiquez son chemin dans la variable KICAD_CLI, "
            "ou exportez la netlist vous-même (format KiCad XML) et passez le fichier .xml."
        )
    cmd = [cli, "sch", "export", "netlist", "--format", "kicadxml", "-o", str(output), str(schematic)]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        raise RuntimeError(f"Échec de kicad-cli : {res.stderr.strip() or res.stdout.strip()}")
    return output


def load(path: str | Path) -> Netlist:
    """Charge un projet : ``.xml`` (netlist), ``.kicad_sch`` ou ``.kicad_pro``."""
    p = Path(path)
    if p.is_dir():
        pros = sorted(p.glob("*.kicad_pro"))
        if not pros:
            raise FileNotFoundError(f"Aucun .kicad_pro dans {p}")
        p = pros[0]
    if p.suffix in (".xml", ".net"):
        return parse_netlist(p)
    if p.suffix == ".kicad_pro":
        p = p.with_suffix(".kicad_sch")
    if p.suffix != ".kicad_sch":
        raise ValueError(f"Format non reconnu : {p.name} (attendu .kicad_pro, .kicad_sch ou .xml)")
    if not p.exists():
        raise FileNotFoundError(p)
    with tempfile.TemporaryDirectory() as tmp:
        out = export_netlist(p, Path(tmp) / "netlist.xml")
        nl = parse_netlist(out)
    if not nl.title:
        nl.title = p.stem
    return nl
