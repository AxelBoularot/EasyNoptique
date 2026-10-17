"""Action KiCad (API IPC, KiCad 9+) : génère le synoptique du projet ouvert et l'ouvre dans le navigateur.

KiCad lance ce script dans l'environnement Python du plugin (dépendances : requirements.txt).
Le projet ouvert est retrouvé via l'API IPC (paquet ``kicad-python``) ; à défaut, une fenêtre demande le fichier.
"""
from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

# En développement, le paquet easynoptique se trouve à côté du dossier plugin/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from easynoptique.cli import generate  # noqa: E402


def project_from_kicad() -> Path | None:
    """Chemin du projet ouvert dans KiCad, via l'API IPC. ``None`` si indisponible."""
    try:
        from kipy import KiCad  # paquet kicad-python
    except ImportError:
        return None
    try:
        board = KiCad().get_board()
    except Exception:
        return None
    # Selon les versions de kicad-python, le chemin est exposé différemment
    for getter in (
        lambda: Path(board.get_project().path),
        lambda: Path(board.document.project.path),
        lambda: Path(board.name),
    ):
        try:
            p = getter()
        except Exception:
            continue
        if p.suffix == ".kicad_pcb":
            p = p.with_suffix(".kicad_pro")
        if p.is_dir():
            pros = sorted(p.glob("*.kicad_pro"))
            p = pros[0] if pros else p
        if p.exists():
            return p
    return None


def ask_for_project() -> Path | None:
    try:
        import tkinter
        from tkinter import filedialog
    except ImportError:
        return None
    root = tkinter.Tk()
    root.withdraw()
    name = filedialog.askopenfilename(
        title="EasyNoptique : choisir le projet KiCad",
        filetypes=[("Projet KiCad", "*.kicad_pro"), ("Schéma KiCad", "*.kicad_sch"), ("Netlist XML", "*.xml")],
    )
    root.destroy()
    return Path(name) if name else None


def notify(message: str) -> None:
    print(message)
    try:
        import tkinter
        from tkinter import messagebox

        root = tkinter.Tk()
        root.withdraw()
        messagebox.showinfo("EasyNoptique", message)
        root.destroy()
    except Exception:
        pass


def main() -> int:
    project = Path(sys.argv[1]) if len(sys.argv) > 1 else (project_from_kicad() or ask_for_project())
    if not project:
        notify("Aucun projet KiCad trouvé.")
        return 1
    try:
        written = generate(str(project))
    except Exception as e:  # message lisible dans KiCad
        notify(f"Échec de la génération : {e}")
        return 1
    html = written.get("html")
    if html:
        webbrowser.open(html.resolve().as_uri())
    notify(f"Synoptique généré dans {html.parent if html else project.parent}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
