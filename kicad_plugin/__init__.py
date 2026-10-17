"""Plugin KiCad EasyNoptique (éditeur de PCB, KiCad 6 à 9).

KiCad importe ce paquet au démarrage de l'éditeur de PCB et enregistre l'action :
un bouton apparaît dans la barre d'outils, et l'entrée « EasyNoptique » dans Outils > Outils externes.
"""
try:
    from .easynoptique_action import EasyNoptiquePlugin

    EasyNoptiquePlugin().register()
except Exception as exc:  # ne jamais empêcher KiCad de démarrer
    import logging

    logging.getLogger("easynoptique").exception("Chargement du plugin EasyNoptique impossible : %s", exc)
