"""Action de l'éditeur de PCB : génère les synoptiques du circuit ouvert et les ouvre dans le navigateur."""
import os
import sys
import traceback
import webbrowser
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
# Le paquet easynoptique est embarqué à côté de ce fichier (paquet PCM) ou dans le dépôt (développement)
for candidate in (HERE, HERE.parent):
    if (candidate / "easynoptique" / "__init__.py").exists() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))
        break


def _message(text: str, error: bool = False) -> None:
    try:
        import wx

        wx.MessageBox(text, "EasyNoptique", wx.OK | (wx.ICON_ERROR if error else wx.ICON_INFORMATION))
    except Exception:
        print(text)


class EasyNoptiquePlugin(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = "EasyNoptique : générer le synoptique"
        self.category = "Documentation"
        self.description = "Génère les synoptiques (fonctionnel, alimentation, bus) en SVG, draw.io et HTML"
        self.show_toolbar_button = True
        icon = HERE / "icon-24.png"
        self.icon_file_name = str(icon)
        self.dark_icon_file_name = str(icon)

    def Run(self):
        try:
            # KiCad garde les modules en mémoire : on les recharge pour utiliser la version installée
            for name in [m for m in sys.modules if m == "easynoptique" or m.startswith("easynoptique.")]:
                del sys.modules[name]
            from easynoptique import __version__
            from easynoptique.cli import generate_from_netlist
            from easynoptique.kicad_board import netlist_from_board
            from easynoptique.rules import Rules

            board = pcbnew.GetBoard()
            board_file = Path(board.GetFileName())
            if not board.GetFileName():
                _message("Enregistrez d'abord le circuit imprimé.", error=True)
                return
            nl = netlist_from_board(board)
            if not nl.components:
                _message("Le PCB ne contient aucun composant.\n"
                         "Faites d'abord : Outils > Mettre à jour le PCB depuis le schéma (F8).", error=True)
                return
            rules = Rules()
            rules_file = Rules.default_path(board_file.with_suffix(".kicad_pro"))
            if rules_file.exists():
                try:
                    rules = Rules.load(rules_file)
                except Exception as e:  # PyYAML absent du Python de KiCad
                    _message(f"Fichier de règles ignoré : {e}")
            out = board_file.parent / "synoptique"
            written = generate_from_netlist(nl, out, rules)
            html = written.get("html")
            if html:
                webbrowser.open(html.resolve().as_uri())
            _message(f"EasyNoptique {__version__}\n\nSynoptique généré dans :\n{out}\n\n"
                     f"Fichiers : {', '.join(sorted(p.name for p in written.values()))}")
        except Exception:
            _message("Erreur pendant la génération du synoptique :\n\n" + traceback.format_exc(), error=True)


if os.environ.get("EASYNOPTIQUE_DEBUG"):
    print(f"EasyNoptique chargé depuis {HERE}")
