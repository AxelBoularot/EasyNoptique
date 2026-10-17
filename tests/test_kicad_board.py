"""Lecture d'un PCB via une imitation de l'API pcbnew (KiCad n'est pas disponible dans les tests)."""
from easynoptique.analyze import analyze
from easynoptique.kicad_board import netlist_from_board


class FakeField:
    def __init__(self, name, text):
        self._n, self._t = name, text

    def GetName(self):
        return self._n

    def GetText(self):
        return self._t


class FakePad:
    def __init__(self, number, net, function="", ptype="passive"):
        self.n, self.net, self.f, self.t = number, net, function, ptype

    def GetNumber(self):
        return self.n

    def GetNetname(self):
        return self.net

    def GetPinFunction(self):
        return self.f

    def GetPinType(self):
        return self.t


class FakeFootprint:
    def __init__(self, ref, value, sheet, pads, fields=None):
        self.ref, self.value, self.sheet, self.pads, self.fields = ref, value, sheet, pads, fields or {}

    def GetReference(self):
        return self.ref

    def GetValue(self):
        return self.value

    def GetSheetname(self):
        return self.sheet

    def GetSheetfile(self):
        return f"{self.sheet}.kicad_sch" if self.sheet else "carte.kicad_sch"

    def GetFields(self):
        return [FakeField(k, v) for k, v in self.fields.items()]

    def Pads(self):
        return self.pads


class FakeTitle:
    def GetTitle(self):
        return "Carte test"

    def GetRevision(self):
        return "B"

    def GetDate(self):
        return ""

    def GetCompany(self):
        return ""


class FakeBoard:
    def __init__(self, fps):
        self.fps = fps

    def GetFootprints(self):
        return self.fps

    def GetFileName(self):
        return "/projets/carte/carte.kicad_pcb"

    def GetTitleBlock(self):
        return FakeTitle()


def make_board():
    return FakeBoard([
        FakeFootprint("U1", "STM32G031", "mcu", [
            FakePad("1", "+3V3", "VDD", "power_in"), FakePad("2", "GND", "VSS", "power_in"),
            FakePad("3", "/SDA", "I2C1_SDA", "bidirectional"), FakePad("4", "/SCL", "I2C1_SCL", "bidirectional"),
        ]),
        FakeFootprint("U2", "BMP280", "capteurs", [
            FakePad("1", "+3V3", "VDD", "power_in"), FakePad("2", "GND", "GND", "power_in"),
            FakePad("3", "/SDA", "SDI", "bidirectional"), FakePad("4", "/SCL", "SCK", "input"),
        ], {"I2C_ADDR": "0x77"}),
        FakeFootprint("U3", "AP2112K-3.3", "alim", [
            FakePad("1", "VBUS", "VIN", "power_in"), FakePad("2", "GND", "GND", "power_in"),
            FakePad("5", "+3V3", "VOUT", "power_out+no_connect"),
        ]),
        FakeFootprint("J1", "USB_C", "alim", [FakePad("A4", "VBUS", "VBUS"), FakePad("A1", "GND", "GND")]),
        FakeFootprint("REF**", "logo", "", []),
    ])


def test_lecture_pcb():
    nl = netlist_from_board(make_board())
    assert set(nl.components) == {"U1", "U2", "U3", "J1"}
    assert nl.title == "Carte test" and nl.rev == "B"
    assert nl.components["U2"].field("I2C_ADDR") == "0x77"
    assert nl.components["U1"].sheet_path == "/mcu/"
    sda = next(n for n in nl.nets if n.name == "/SDA")
    assert {(p.ref, p.function) for p in sda.pins} == {("U1", "I2C1_SDA"), ("U2", "SDI")}


def test_analyse_depuis_pcb():
    syn = analyze(netlist_from_board(make_board()))
    assert syn.hub == "mcu"
    lk = next(lk for lk in syn.links if lk.kind == "i2c")
    assert (lk.a, lk.b, lk.label, lk.width) == ("mcu", "capteurs", "I²C1", 2)
    conv = next(p for p in syn.power if p.ref == "U3")
    assert conv.role == "converter" and conv.outputs == ["+3V3"]


def test_plugin_depuis_le_zip(tmp_path, monkeypatch):
    """Extrait le paquet PCM et exécute l'action comme le ferait KiCad (pcbnew simulé)."""
    import importlib
    import sys
    import types
    import zipfile

    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "tools"))
    import build_pcm

    with zipfile.ZipFile(build_pcm.build()) as z:
        names = z.namelist()
        assert "metadata.json" in names and "resources/icon.png" in names
        z.extractall(tmp_path / "pkg")

    board = make_board()
    board.GetFileName = lambda: str(tmp_path / "carte.kicad_pcb")
    registered = []

    class ActionPlugin:
        def register(self):
            self.defaults()
            registered.append(self)

    fake = types.ModuleType("pcbnew")
    fake.ActionPlugin = ActionPlugin
    fake.GetBoard = lambda: board
    monkeypatch.setitem(sys.modules, "pcbnew", fake)
    monkeypatch.setattr("webbrowser.open", lambda url: True)
    monkeypatch.syspath_prepend(str(tmp_path / "pkg"))
    for mod in [m for m in sys.modules if m == "easynoptique" or m.startswith("easynoptique.")]:
        monkeypatch.delitem(sys.modules, mod)
    importlib.import_module("plugins")
    assert registered and registered[0].show_toolbar_button
    registered[0].Run()
    out = tmp_path / "synoptique"
    assert (out / "carte-test.html").exists() and (out / "carte-test.drawio").exists()


def test_metadonnees_conformes_au_schema_kicad():
    """Le gestionnaire de plugins de KiCad refuse un paquet dont metadata.json ne respecte pas son schéma."""
    import json
    import sys
    from pathlib import Path

    import pytest

    jsonschema = pytest.importorskip("jsonschema")
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "tools"))
    import build_pcm

    schema = json.loads((root / "tests" / "fixtures" / "pcm.v1.schema.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator({**schema, "$ref": "#/definitions/Package"})
    errors = [f"{list(e.path)}: {e.message}" for e in validator.iter_errors(build_pcm.METADATA)]
    assert errors == []


def test_regulateur_mal_type_et_alims_visibles():
    """Régulateur dont toutes les broches sont 'passive' (symbole mal typé) : reconnu par les noms de broches.
    Le MCU reçoit une flèche d'alimentation, les autres blocs une pastille, et sa référence est affichée."""
    from easynoptique.layout import layout_functional

    fps = [
        FakeFootprint("U1", "STM32H745", "mcu", [
            FakePad("1", "/3V3", "VDD", "passive"), FakePad("2", "GND", "VSS", "passive"),
            FakePad("3", "/SDA", "I2C1_SDA", "bidirectional"), FakePad("4", "/SCL", "I2C1_SCL", "bidirectional"),
            FakePad("5", "/MOSI", "SPI1_MOSI", "bidirectional"), FakePad("6", "/TX", "USART1_TX", "bidirectional"),
        ]),
        FakeFootprint("U2", "BMP280", "capteurs", [FakePad("1", "/3V3", "VDD", "passive"), FakePad("3", "/SDA", "SDI"),
                                                   FakePad("4", "/SCL", "SCK")]),
        FakeFootprint("U4", "RFM95W", "radio", [FakePad("1", "/3V3", "3.3V", "passive"), FakePad("2", "/MOSI", "MOSI")]),
        FakeFootprint("U5", "SAM-M10Q", "gnss", [FakePad("1", "/3V3", "VCC", "passive"), FakePad("2", "/TX", "RXD")]),
        FakeFootprint("U3", "LDO 3V3", "alim", [FakePad("1", "/VIN_5V", "VIN", "passive"),
                                               FakePad("2", "GND", "GND", "passive"),
                                               FakePad("3", "/3V3", "VOUT", "passive")]),
        FakeFootprint("J1", "USB_C", "alim", [FakePad("A4", "/VIN_5V", "VBUS"), FakePad("A1", "GND", "GND")]),
    ]
    syn = analyze(netlist_from_board(FakeBoard(fps)))
    ldo = next(p for p in syn.power if p.ref == "U3")
    assert (ldo.role, ldo.inputs, ldo.outputs) == ("converter", ["VIN_5V"], ["3V3"])
    assert any(lk.kind == "power" and (lk.a, lk.b, lk.label) == ("alim", "mcu", "3V3") for lk in syn.links)
    assert all(syn.block(b).rails == ["3V3"] for b in ("capteurs", "radio", "gnss"))
    scene = layout_functional(syn)
    hub_box = next(s for s in scene.shapes if s.block == "mcu" and s.kind == "box")
    assert hub_box.sub == "U1"
