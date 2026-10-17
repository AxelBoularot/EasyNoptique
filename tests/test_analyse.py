import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from easynoptique.analyze import analyze, classify_text, parse_current
from easynoptique.cli import generate, main
from easynoptique.netlist import parse_netlist
from easynoptique.rules import Rules

FIXTURE = Path(__file__).parent / "fixtures" / "meteo-poche.xml"


@pytest.fixture(scope="module")
def syn():
    return analyze(parse_netlist(FIXTURE))


def links(syn, a, b):
    return {lk.label: lk for lk in syn.links if lk.a == a and lk.b == b}


def test_lecture_netlist():
    nl = parse_netlist(FIXTURE)
    assert nl.title == "Station météo de poche"
    assert nl.rev == "A"
    assert nl.components["U6"].field("I2C_ADDR") == "0x76"
    assert nl.components["U1"].sheet_path == "/mcu/"


def test_blocs_et_hub(syn):
    assert syn.hub == "mcu"
    cats = {b.id: b.category for b in syn.blocks}
    assert cats == {"mcu": "hub", "alim": "power", "capteurs": "sensors", "debug": "debug",
                    "ihm": "hmi", "memoire": "memory", "usb": "interface"}


def test_bus_detectes(syn):
    assert set(links(syn, "mcu", "capteurs")) == {"I²C1", "Analogique"}
    spi = links(syn, "mcu", "memoire")["SPI1"]
    assert spi.width == 4 and "FLASH_CS" in spi.nets  # CS rattaché par son nom de net
    assert links(syn, "mcu", "usb")["USB"].direction == "both"
    dbg = links(syn, "mcu", "debug")
    assert dbg["SWD"].width == 3
    assert set(dbg["UART2"].nets) == {"UART_RX", "UART_TX"}  # fusion à travers R10 (33 Ω série)


def test_sens_des_fleches(syn):
    assert links(syn, "mcu", "capteurs")["I²C1"].direction == "ab"
    assert links(syn, "mcu", "ihm")["GPIO ×2"].direction == "ba"  # boutons -> MCU
    assert links(syn, "mcu", "alim")["GPIO"].direction == "ba"  # STAT du chargeur -> MCU


def test_alimentation(syn):
    roles = {p.ref: (p.role, p.inputs, p.outputs) for p in syn.power}
    assert roles["U4"] == ("converter", ["VSYS"], ["+3V3"])
    assert roles["U2"] == ("converter", ["VBUS"], ["VBAT"])
    assert roles["J1"][0] == "source" and roles["J2"][0] == "source"
    assert "VBAT_SENSE" not in syn.rails
    assert links(syn, "usb", "alim")["VBUS"].kind == "power"
    assert syn.block("capteurs").rails == ["+3V3"]


def test_vue_bus(syn):
    i2c = next(b for b in syn.buses if b.kind == "i2c")
    assert {(d.ref, d.address) for d in i2c.devices} == {("U6", "0x76"), ("U7", "0x3C")}
    assert sorted(i2c.pullups) == ["R5", "R6"]
    assert syn.warnings == []


def test_regles(tmp_path, syn):
    f = tmp_path / "r.yaml"
    f.write_text("blocks:\n  debug: {hide: true}\n  capteurs: {name: Environnement}\nnets:\n  BTN1: gpio\n", encoding="utf-8")
    s2 = analyze(parse_netlist(FIXTURE), Rules.load(f))
    assert all("debug" not in (lk.a, lk.b) for lk in s2.links)
    assert s2.block("capteurs").name == "Environnement"


@pytest.mark.parametrize("text,expected", [
    ("I2C1_SDA", ("i2c", "1")), ("PB7/I2C1_SDA", ("i2c", "1")), ("SPI2_MOSI", ("spi", "2")),
    ("USART2_TX", ("uart", "2")), ("~{CS}", ("spi", "")), ("D+", ("usb", "")), ("CANH", ("can", "")),
    ("SWDIO", ("swd", "")), ("ADC1_IN6", ("analog", "")), ("PA4", (None, "")), ("BTN1", (None, "")),
])
def test_classification(text, expected):
    assert classify_text(text) == expected


def test_courant():
    assert parse_current("12mA") == 12
    assert parse_current("0,7 mA") == 0.7
    assert parse_current("1.5A") == 1500
    assert parse_current("") is None


def test_generation_fichiers(tmp_path):
    written = generate(str(FIXTURE), str(tmp_path))
    for key, path in written.items():
        assert path.exists() and path.stat().st_size > 500, key
        if path.suffix in (".svg", ".drawio"):
            ET.parse(path)
    root = ET.parse(written["drawio"]).getroot()
    assert len(root.findall("diagram")) == 4


def test_cli(capsys):
    assert main(["analyse", str(FIXTURE)]) == 0
    assert "I²C1" in capsys.readouterr().out
