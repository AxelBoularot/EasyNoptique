"""Construit le paquet à installer dans KiCad (Gestionnaire de plugins et de contenus > Installer depuis un fichier).

Usage : ``python tools/build_pcm.py`` -> ``release/EasyNoptique-<version>-kicad.zip``
"""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from easynoptique import __version__  # noqa: E402

METADATA = {
    "$schema": "https://go.kicad.org/pcm/schemas/v1",
    "name": "EasyNoptique",
    "description": "Synoptiques automatiques : fonctionnel, alimentation et bus (SVG, draw.io, HTML).",
    "description_full": (
        "EasyNoptique analyse le circuit (composants, feuilles hiérarchiques, nets, fonctions et types de broches) "
        "et génère automatiquement les synoptiques du projet : vue fonctionnelle, arbre d'alimentation avec bilan "
        "de courant, vue des bus (I2C, SPI, UART, USB, CAN, SWD...) avec adresses. Exports SVG, draw.io "
        "(retouchable, un calque par type de liaison), rapport HTML interactif et JSON.\n\n"
        "Utilisation : dans l'éditeur de PCB, cliquez sur le bouton EasyNoptique. Les fichiers sont écrits dans "
        "le dossier 'synoptique' du projet."
    ),
    "identifier": "com.github.axelboularot.easynoptique",
    "type": "plugin",
    "author": {"name": "Axel Boularot", "contact": {"github": "https://github.com/AxelBoularot"}},
    "license": "MIT",
    "resources": {"homepage": "https://github.com/AxelBoularot/EasyNoptique"},
    "tags": ["documentation", "diagram", "synoptique", "block diagram"],
    "versions": [{"version": __version__, "status": "testing", "kicad_version": "6.0"}],
}


def build() -> Path:
    out_dir = ROOT / "release"
    out_dir.mkdir(exist_ok=True)
    dest = out_dir / f"EasyNoptique-{__version__}-kicad.zip"
    plugin = ROOT / "kicad_plugin"
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("metadata.json", json.dumps(METADATA, ensure_ascii=False, indent=2))
        z.write(plugin / "icon-64.png", "resources/icon.png")
        for name in ("__init__.py", "easynoptique_action.py", "icon-24.png"):
            z.write(plugin / name, f"plugins/{name}")
        for f in sorted((ROOT / "easynoptique").glob("*.py")):
            z.write(f, f"plugins/easynoptique/{f.name}")
    return dest


if __name__ == "__main__":
    print(f"Paquet KiCad : {build()}")
