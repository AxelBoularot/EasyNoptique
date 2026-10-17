"""Génère ``meteo-poche.xml`` : netlist KiCad XML d'une carte fictive « station météo de poche ».

Le format reproduit celui de ``kicad-cli sch export netlist --format kicadxml`` (KiCad 8/9).
Lancer : ``python tests/fixtures/make_meteo.py``
"""
from pathlib import Path
from xml.sax.saxutils import quoteattr

SHEETS = {
    "usb": "usb.kicad_sch", "alim": "alim.kicad_sch", "mcu": "mcu.kicad_sch", "capteurs": "capteurs.kicad_sch",
    "ihm": "ihm.kicad_sch", "memoire": "memoire.kicad_sch", "debug": "debug.kicad_sch",
}

# ref: (valeur, feuille, description, champs)
COMPS = {
    "J1": ("USB_C_Receptacle_USB2.0", "usb", "USB 2.0-only Type-C Receptacle connector", {}),
    "U5": ("USBLC6-2SC6", "usb", "Very low capacitance ESD protection diode, 2 data-line", {}),
    "R1": ("5.1k", "usb", "Resistor", {}), "R2": ("5.1k", "usb", "Resistor", {}),
    "U2": ("MCP73831-2-OT", "alim", "Single cell, Li-Ion/Li-Po charge management controller", {"Courant": "1mA"}),
    "U3": ("LM66100", "alim", "Ideal diode, 1.5A", {}),
    "U9": ("LM66100", "alim", "Ideal diode, 1.5A", {}),
    "U4": ("AP2112K-3.3", "alim", "600mA low dropout linear regulator, 3.3V", {"EN_Imax": "600mA"}),
    "J2": ("Conn_01x02 LiPo", "alim", "Battery connector JST-PH", {}),
    "R3": ("4k", "alim", "Resistor", {}), "R7": ("100k", "alim", "Resistor", {}), "R8": ("100k", "alim", "Resistor", {}),
    "C1": ("10u", "alim", "Capacitor", {}), "C2": ("10u", "alim", "Capacitor", {}),
    "U1": ("STM32L432KCUx", "mcu", "STMicroelectronics Arm Cortex-M4 MCU, 256KB flash, 64KB RAM, 80 MHz", {"Courant": "12mA"}),
    "Y1": ("32.768kHz", "mcu", "Crystal", {}),
    "R5": ("4.7k", "mcu", "Resistor", {}), "R6": ("4.7k", "mcu", "Resistor", {}),
    "C10": ("100n", "mcu", "Capacitor", {}), "C11": ("100n", "mcu", "Capacitor", {}),
    "U6": ("BME280", "capteurs", "Combined humidity, pressure and temperature sensor", {"I2C_ADDR": "0x76", "Courant": "0,7mA"}),
    "TH1": ("10k NTC", "capteurs", "Temperature dependent resistor, negative temperature coefficient", {}),
    "R9": ("10k", "capteurs", "Resistor", {}),
    "U7": ("SSD1306 OLED 128x64", "ihm", "OLED display module, I2C", {"I2C_ADDR": "0x3C", "Courant": "20mA"}),
    "SW1": ("SW_Push", "ihm", "Push button switch", {}), "SW2": ("SW_Push", "ihm", "Push button switch", {}),
    "U8": ("W25Q32JVSS", "memoire", "32Mbit Serial Flash Memory, Standard/Dual/Quad SPI", {"Courant": "15mA"}),
    "C20": ("100n", "memoire", "Capacitor", {}),
    "J3": ("Tag-Connect_TC2050", "debug", "Tag-Connect TC2050 SWD + UART", {}),
    "R10": ("33", "debug", "Resistor", {}),
}

# nom du net : [(ref, broche, fonction, type)]
NETS = {
    "VBUS": [("J1", "A4", "VBUS", "passive"), ("J1", "B9", "VBUS", "passive"), ("U5", "5", "VBUS", "power_in"),
             ("U2", "4", "VDD", "power_in"), ("U3", "1", "VIN", "power_in"), ("C1", "1", "", "passive")],
    "VBAT": [("U2", "3", "VBAT", "power_out"), ("J2", "1", "Pin_1", "passive"), ("U9", "1", "VIN", "power_in"),
             ("R7", "1", "", "passive")],
    "/alim/VSYS": [("U3", "6", "VOUT", "power_out"), ("U9", "6", "VOUT", "power_out"), ("U4", "1", "VIN", "power_in"),
                   ("U4", "3", "EN", "input"), ("C2", "1", "", "passive")],
    "+3V3": [("U4", "5", "VOUT", "power_out"), ("U1", "1", "VDD", "power_in"), ("U1", "5", "VDDA", "power_in"),
             ("U6", "8", "VDD", "power_in"), ("U6", "6", "VDDIO", "power_in"), ("U7", "2", "VCC", "power_in"),
             ("U8", "8", "VCC", "power_in"), ("J3", "1", "Pin_1", "passive"), ("R5", "2", "", "passive"),
             ("R6", "2", "", "passive"), ("C10", "1", "", "passive"), ("C11", "1", "", "passive"),
             ("C20", "1", "", "passive"), ("R9", "1", "", "passive")],
    "GND": [("J1", "A1", "GND", "passive"), ("U5", "2", "GND", "power_in"), ("U2", "2", "VSS", "power_in"),
            ("U3", "2", "GND", "power_in"), ("U9", "2", "GND", "power_in"), ("U4", "2", "GND", "power_in"),
            ("J2", "2", "Pin_2", "passive"), ("R1", "2", "", "passive"), ("R2", "2", "", "passive"),
            ("R3", "2", "", "passive"), ("R8", "2", "", "passive"), ("C1", "2", "", "passive"), ("C2", "2", "", "passive"),
            ("U1", "16", "VSS", "power_in"), ("C10", "2", "", "passive"), ("C11", "2", "", "passive"),
            ("U6", "1", "GND", "power_in"), ("U6", "5", "SDO", "bidirectional"), ("U7", "1", "GND", "power_in"),
            ("SW1", "2", "2", "passive"), ("SW2", "2", "2", "passive"), ("U8", "4", "GND", "power_in"),
            ("C20", "2", "", "passive"), ("J3", "10", "Pin_10", "passive"), ("TH1", "2", "", "passive")],
    "/usb/CC1": [("J1", "A5", "CC1", "bidirectional"), ("R1", "1", "", "passive")],
    "/usb/CC2": [("J1", "B5", "CC2", "bidirectional"), ("R2", "1", "", "passive")],
    "/USB_D+": [("J1", "A6", "D+", "bidirectional"), ("J1", "B6", "D+", "bidirectional"), ("U5", "1", "I/O1", "passive"),
                ("U1", "22", "USB_DP", "bidirectional")],
    "/USB_D-": [("J1", "A7", "D-", "bidirectional"), ("J1", "B7", "D-", "bidirectional"), ("U5", "3", "I/O2", "passive"),
                ("U1", "21", "USB_DM", "bidirectional")],
    "Net-(U2-PROG)": [("U2", "5", "PROG", "input"), ("R3", "1", "", "passive")],
    "/CHG_STAT": [("U2", "1", "STAT", "open_collector"), ("U1", "18", "PA8", "bidirectional")],
    "/VBAT_SENSE": [("R7", "2", "", "passive"), ("R8", "1", "", "passive"), ("U1", "6", "PA0", "bidirectional")],
    "/I2C_SDA": [("U1", "30", "I2C1_SDA", "bidirectional"), ("R5", "1", "", "passive"), ("U6", "3", "SDI", "bidirectional"),
                 ("U7", "4", "SDA", "bidirectional")],
    "/I2C_SCL": [("U1", "29", "I2C1_SCL", "bidirectional"), ("R6", "1", "", "passive"), ("U6", "4", "SCK", "input"),
                 ("U7", "3", "SCL", "input")],
    "/SPI_SCK": [("U1", "11", "SPI1_SCK", "bidirectional"), ("U8", "6", "CLK", "input")],
    "/SPI_MOSI": [("U1", "13", "SPI1_MOSI", "bidirectional"), ("U8", "5", "DI(IO0)", "bidirectional")],
    "/SPI_MISO": [("U1", "12", "SPI1_MISO", "bidirectional"), ("U8", "2", "DO(IO1)", "bidirectional")],
    "/FLASH_CS": [("U1", "10", "PA4", "bidirectional"), ("U8", "1", "~{CS}", "input")],
    "/BTN1": [("U1", "14", "PB0", "bidirectional"), ("SW1", "1", "1", "passive")],
    "/BTN2": [("U1", "15", "PB1", "bidirectional"), ("SW2", "1", "1", "passive")],
    "/CTN": [("TH1", "1", "", "passive"), ("R9", "2", "", "passive"), ("U1", "7", "ADC1_IN6", "bidirectional")],
    "/SWDIO": [("U1", "23", "SWDIO", "bidirectional"), ("J3", "2", "Pin_2", "passive")],
    "/SWCLK": [("U1", "24", "SWCLK", "bidirectional"), ("J3", "4", "Pin_4", "passive")],
    "/NRST": [("U1", "4", "NRST", "input"), ("J3", "6", "Pin_6", "passive")],
    "/UART_TX": [("U1", "8", "USART2_TX", "bidirectional"), ("R10", "1", "", "passive")],
    "Net-(J3-Pin_8)": [("R10", "2", "", "passive"), ("J3", "8", "Pin_8", "passive")],
    "/UART_RX": [("U1", "25", "USART2_RX", "bidirectional"), ("J3", "7", "Pin_7", "passive")],
    "/mcu/OSC32_IN": [("U1", "2", "PC14", "bidirectional"), ("Y1", "1", "1", "passive")],
    "/mcu/OSC32_OUT": [("U1", "3", "PC15", "bidirectional"), ("Y1", "2", "2", "passive")],
    "unconnected-(U1-PB3-Pad26)": [("U1", "26", "PB3", "bidirectional")],
}


def build() -> str:
    out = ['<?xml version="1.0" encoding="utf-8"?>', '<export version="E">', "  <design>",
           "    <source>/projets/meteo-poche/meteo-poche.kicad_sch</source>",
           "    <date>17/10/2026 10:00:00</date>", "    <tool>Eeschema 9.0.4</tool>",
           '    <sheet number="1" name="/" tstamps="/">', "      <title_block>",
           "        <title>Station météo de poche</title>", "        <company>EasyNoptique</company>",
           "        <rev>A</rev>", "        <date>2026-10-17</date>", "        <source>meteo-poche.kicad_sch</source>",
           "      </title_block>", "    </sheet>"]
    for i, (name, f) in enumerate(SHEETS.items(), start=2):
        out.append(f'    <sheet number="{i}" name="/{name}/" tstamps="/{i:08x}/"><title_block><source>{f}</source></title_block></sheet>')
    out += ["  </design>", "  <components>"]
    for ref, (value, sheet, desc, fields) in COMPS.items():
        out.append(f'    <comp ref="{ref}">')
        out.append(f"      <value>{value}</value>")
        if fields:
            out.append("      <fields>")
            out += [f"        <field name={quoteattr(k)}>{v}</field>" for k, v in fields.items()]
            out.append("      </fields>")
        out.append(f'      <libsource lib="lib" part={quoteattr(value)} description={quoteattr(desc)}/>')
        out.append(f'      <property name="Sheetname" value="{sheet}"/>')
        out.append(f'      <property name="Sheetfile" value="{SHEETS[sheet]}"/>')
        out.append(f'      <sheetpath names="/{sheet}/" tstamps="/x/"/>')
        out.append("    </comp>")
    out += ["  </components>", "  <nets>"]
    for code, (name, nodes) in enumerate(NETS.items(), start=1):
        out.append(f'    <net code="{code}" name={quoteattr(name)} class="Default">')
        for ref, pin, func, ptype in nodes:
            fn = f" pinfunction={quoteattr(func)}" if func else ""
            out.append(f'      <node ref="{ref}" pin="{pin}"{fn} pintype="{ptype}"/>')
        out.append("    </net>")
    out += ["  </nets>", "</export>", ""]
    return "\n".join(out)


if __name__ == "__main__":
    dest = Path(__file__).with_name("meteo-poche.xml")
    dest.write_text(build(), encoding="utf-8")
    print(f"Écrit : {dest}")
