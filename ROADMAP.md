# Feuille de route

État au 17/10/2026 : ✅ fait · 🟡 commencé · ⬜ à faire

## Étape 0 : Fondations ✅
- ✅ Structure du dépôt, `pyproject.toml`, intégration continue (tests + lint).
- ✅ Netlist d'exemple réaliste (`tests/fixtures/meteo-poche.xml`).
- ⬜ Ajouter 2 ou 3 vrais projets KiCad (dont un à plat et un gros projet hiérarchique).
- ⬜ Choisir la licence.

## Étape 1 : Lecture du projet ✅
- ✅ Lecture de la netlist KiCad XML (composants, feuilles, champs, broches, `pinfunction`, `pintype`, cartouche).
- ✅ Export automatique via `kicad-cli` depuis un `.kicad_pro` ou `.kicad_sch`.
- ⬜ Tester sur KiCad 7, 8 et 9 (variations du format).

## Étape 2 : Modèle et détection des liaisons 🟡
- ✅ Blocs par feuille hiérarchique, champ `EN_Bloc`, un bloc par circuit intégré si schéma à plat.
- ✅ Tri des nets (masse, alim, signal), fusion à travers les passifs série.
- ✅ Bus I²C, SPI, UART, USB, CAN, SWD, JTAG, analogique, GPIO ; instance (`I2C1`) via les fonctions de broches.
- ✅ Sens des flèches, hub (MCU) automatique, arbre d'alimentation (sources, convertisseurs, charges, courants).
- ✅ Alertes : conflit d'adresse I²C, pull-up manquantes, rail sans source, bloc isolé.
- ⬜ Bus multiples entre composants non-MCU (ex. capteur relié à un FPGA).
- ⬜ Connecteurs vers l'extérieur traités comme interfaces (vue d'interconnexion).
- ⬜ Valider la détection sur 5 à 10 projets open source.

## Étape 3 : Règles et surcharges 🟡
- ✅ Fichier `<projet>.easynoptique.yaml` (hub, bloc d'un composant, renommage, catégorie, masquage, type de bus, nets ignorés).
- ⬜ Fusion de blocs, couleurs personnalisées, ordre imposé.

## Étape 4 : Placement automatique 🟡
- ✅ Vue fonctionnelle (MCU au centre, alimentation à gauche, périphériques à droite, debug en bas).
- ✅ Arbre d'alimentation en colonnes, vue bus en lignes.
- ✅ Répartition des ports et ordre des couloirs pour limiter les croisements.
- ⬜ Gros projets : plusieurs colonnes de périphériques, retour à la ligne.
- ⬜ Mémoriser les positions retouchées à la main.

## Étape 5 : Exports 🟡
- ✅ SVG, draw.io (4 pages, un calque par type de liaison, flèches attachées aux blocs), HTML interactif, JSON.
- ✅ Légende et cartouche automatiques.
- ⬜ PDF, PNG.

## Étape 6 : Interface ⬜
- 🟡 Le rapport HTML sert d'interface de consultation (onglets, calques, détail des blocs, alertes).
- ⬜ Fenêtre d'édition (wxPython) : listes des blocs et des liaisons, corrections enregistrées dans le YAML.

## Étape 7 : Intégration KiCad 🟡
- 🟡 Action IPC (`plugin/`) écrite : à tester sous KiCad 9 (détection du projet ouvert via `kicad-python`).
- ⬜ Paquet PCM (métadonnées, paquet Python embarqué), publication.

## Étape 8 : Version 1.0 ⬜
- ⬜ Documentation utilisateur avec captures, tests sur projets réels, publication dans le dépôt de plugins KiCad.

## Plus tard (v2)
- Insertion du synoptique comme feuille `.kicad_sch`, synoptique multi-cartes, séquencement des alimentations.
