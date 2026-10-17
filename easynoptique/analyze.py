"""Analyse d'une netlist : blocs, liaisons, bus, arbre d'alimentation."""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from .model import Block, Bus, BusDevice, Item, Link, PowerNode, Synoptic
from .netlist import Component, Net, Netlist
from .rules import Rules

# Préfixes de références ignorés comme extrémités de liaison (passifs, mécanique)
IGNORED_PREFIXES = {"R", "C", "L", "FB", "TP", "H", "MH", "NT", "JP", "Y", "X", "FID", "G", "LOGO", "#PWR", "#FLG"}
# Passifs 2 broches « transparents » pour les signaux (résistance série, ferrite, self)
BRIDGE_PREFIXES = {"R", "L", "FB"}
SOURCE_PREFIXES = {"J", "P", "BT", "CN", "X"}
SOURCE_RAIL_RE = re.compile(r"VBUS|VBAT|BAT|VIN|VEXT|VDC|DC_?IN|USB|PWR_?IN|^\+?\d+V_?IN", re.IGNORECASE)

GROUND_RE = re.compile(r"^(A|D|P|S|C|E)?GND\w*$|^VSS\w*$|^0V$|^EARTH$|^GNDREF$|^GND_\w+$", re.IGNORECASE)
POWER_RE = re.compile(
    r"^[+-]\d|^\d+V\d*\w*$|^\+|^V(CC|DD|BUS|BAT|IN|SYS|CORE|IO|DDA|DDIO|REF|USB|PP|MAIN|SUPPLY|EXT|LED|MOT)\w*$|"
    r"^(VBAT|VSYS|VBUS|VIN|BAT\+?)$|(^|_)\d+V\d*($|_)|^\d+[.,]\d+V$|^V_(BAT|BUS|IN|SYS|CC|DD|MAIN)\w*$|^(PWR|POWER)_",
    re.IGNORECASE,
)

# Suffixes qui désignent un signal même si le nom commence comme un rail (VBAT_SENSE, VBUS_DET…)
SIGNAL_SUFFIX_RE = re.compile(r"_(SENSE|SNS|MON|DIV|ADC|EN|PG|PGOOD|GOOD|FAULT|FLT|STAT|CTRL|DET|ON|OFF|OK)\d*$", re.IGNORECASE)

PRETTY_NAMES = {
    "mcu": "MCU", "usb": "USB", "ihm": "IHM", "hmi": "HMI", "alim": "Alimentation", "power": "Alimentation",
    "memoire": "Mémoire", "mémoire": "Mémoire", "memory": "Mémoire", "capteurs": "Capteurs", "sensors": "Capteurs",
    "debug": "Debug", "radio": "Radio", "rf": "RF", "can": "CAN", "eth": "Ethernet", "sd": "Carte SD",
}

OUT_TYPES = {"output", "tri_state", "open_collector", "open_emitter", "power_out"}

# Reconnaissance des protocoles
PERIPH_RE = re.compile(r"^(I2C|SPI|USART|UART|LPUART|CAN|FDCAN|USB|OTG_FS|OTG_HS|SWD|JTAG|SDMMC|QUADSPI|OCTOSPI)(\d*)_(\w+)$")
PERIPH_KIND = {
    "I2C": "i2c", "SPI": "spi", "USART": "uart", "UART": "uart", "LPUART": "uart", "CAN": "can", "FDCAN": "can",
    "USB": "usb", "OTG_FS": "usb", "OTG_HS": "usb", "SWD": "swd", "JTAG": "jtag", "QUADSPI": "spi", "OCTOSPI": "spi",
}
TOKEN_KIND = [
    ("usb", re.compile(r"^(USB\d*_?)?(D[PM+\-]|DN)$|^USB\d*_?D[PM+\-]$")),
    ("i2c", re.compile(r"^(I2C\d*_?)?(SDA|SCL)\d*$")),
    ("swd", re.compile(r"^(SWDIO|SWCLK|SWO|SWDCLK|NRST)$")),
    ("jtag", re.compile(r"^(TMS|TCK|TDI|TDO|TRST|NTRST)$")),
    ("can", re.compile(r"^CAN\d*_?(H|L|TX|RX)$|^CAN(H|L)$")),
    ("uart", re.compile(r"^(U?S?ART\d*_?)?(TXD?|RXD?|RTS|CTS)\d*$")),
    ("spi", re.compile(r"^(SPI\d*_?)?(MOSI|MISO|SCK|SCLK|NSS|N?CS\d*|SS|COPI|CIPO|PICO|POCI)$")),
    ("analog", re.compile(r"^ADC\d*(_IN\d+)?$|^AIN\d*$|^SENSE$|^\w*_SENSE$|^AN\d+$|^VSENSE$")),
]


def _tokens(text: str) -> list[str]:
    text = text.upper().replace("~{", "").replace("}", "").replace("#", "")
    parts = re.split(r"[/\s,()]+", text)
    out: list[str] = []
    for p in parts:
        if not p:
            continue
        out.append(p)
        if "_" in p and not PERIPH_RE.match(p):
            out.extend(s for s in p.split("_") if s)
    return out


def classify_text(text: str) -> tuple[str | None, str]:
    """Renvoie (type de bus, instance) reconnu dans un nom de broche ou de net."""
    for tok in _tokens(text):
        m = PERIPH_RE.match(tok)
        if m:
            kind = PERIPH_KIND.get(m.group(1))
            if m.group(1) in ("I2C", "SPI", "USART", "UART", "CAN", "FDCAN", "LPUART") and not m.group(3):
                continue
            if kind:
                if kind == "uart" and not re.match(r"(TX|RX|RTS|CTS|CK)", m.group(3)):
                    continue
                return kind, m.group(2)
        if re.match(r"^ADC\d*_IN\d+$", tok):
            return "analog", ""
    for tok in _tokens(text):
        for kind, rx in TOKEN_KIND:
            if rx.match(tok):
                return kind, ""
    return None, ""


def parse_current(text: str) -> float | None:
    """'12mA' -> 12.0 ; '0,7 mA' -> 0.7 ; '1.5A' -> 1500 ; '300uA' -> 0.3."""
    if not text:
        return None
    m = re.match(r"^\s*([\d.,]+)\s*(m|u|µ|k)?A?\s*$", text.strip(), re.IGNORECASE)
    if not m:
        return None
    v = float(m.group(1).replace(",", "."))
    unit = (m.group(2) or "").lower()
    return {"m": v, "u": v / 1000, "µ": v / 1000, "k": v * 1e6}.get(unit, v * 1000)


class _UF:
    def __init__(self) -> None:
        self.p: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


CATEGORY_RULES = [
    ("debug", re.compile(r"debug|\bswd\b|jtag|tag-?connect|tc20[35]0|\bprog", re.IGNORECASE)),
    ("power", re.compile(r"\balim|power|\bpwr|supply|batter|énergie|energie|regulat|ldo|buck|boost|charger|mcp738|bq2|tps\d|ap21|lm11|lm66", re.IGNORECASE)),
    ("memory", re.compile(r"m[ée]moire|memory|flash|eeprom|\bsd\b|sd ?card|micro ?sd|fram|w25q|at24|at45|emmc|sram|psram|mkdv|\bmem\b", re.IGNORECASE)),
    ("radio", re.compile(r"radio|\brf\b|lora|rfm\d|esp32|esp8266|wi-?fi|\bble\b|bluetooth|gnss|\bgps\b|sam-?m\d|nrf\d|sx12|cc1\d|gsm|lte|antenn|zigbee", re.IGNORECASE)),
    ("sensors", re.compile(r"capteur|sensor|bme\d|bmp\d|adxl|ism\d|lsm\d|mpu\d|icm\d|lis\d|accel|gyro|temp|humid|pressure|ina2\d|\bimu\b|\bctn\b|\bntc\b|thermist", re.IGNORECASE)),
    ("hmi", re.compile(r"\bihm\b|\bhmi\b|oled|lcd|display|[ée]cran|ssd13|button|bouton|\bled|\bsw\d|buzzer|keypad|clavier", re.IGNORECASE)),
    ("interface", re.compile(r"usb|interface|connect|\bconn|rs485|rs232|ethernet|\beth\b|\bcan\b|header|bornier", re.IGNORECASE)),
]


# Noms de broches d'alimentation (secours quand les types de broches du symbole sont faux)
IN_PIN_RE = re.compile(r"^(V_?IN\d*|IN\d*|VI|PVIN\d*|AVIN|VBUS|VSUP|VS|VCC|VDD|VBATT?)$", re.I)
OUT_PIN_RE = re.compile(r"^(V_?OUT\d*|OUT\d*|VO|OUTPUT|VREG\w*|VSYS|VBAT_?OUT)$", re.I)
LOAD_PIN_RE = re.compile(r"^(\d+([.,]\d+)?V\d*|V(CC|DD)\w*|[AD]VDD\w*|IOVDD|VDDIO\w*|VCCIO\w*|VIN|VBAT|VS|V\+|VLOGIC|VIO)$", re.I)


def _pin_name(p) -> str:
    return (p.function or "").split("/")[0].replace("~{", "").replace("}", "").strip()


# Connecteurs : masqués par défaut (règle « connecteurs: true » pour les afficher)
CONNECTOR_PREFIXES = {"J", "P", "CN", "CON", "CONN", "JP"}
_excluded: set[str] = set()


def _is_ignored(c: Component) -> bool:
    return c.prefix in IGNORED_PREFIXES or c.prefix in _excluded or c.ref.startswith("#")


def analyze(nl: Netlist, rules: Rules | None = None) -> Synoptic:
    rules = rules or Rules()
    global _excluded
    previous = _excluded
    _excluded = set() if rules.connectors else set(CONNECTOR_PREFIXES)
    try:
        return _analyze(nl, rules)
    finally:
        _excluded = previous


def _analyze(nl: Netlist, rules: Rules) -> Synoptic:
    comps = nl.components
    syn = Synoptic(project=nl.project_name, title=nl.title or nl.project_name, rev=nl.rev, date=nl.date, company=nl.company)

    # --- 1. Tri des nets -------------------------------------------------
    nets = [n for n in nl.nets if len(n.pins) >= 2 and not n.name.startswith("unconnected-")]
    nets = [n for n in nets if n.leaf not in rules.ignore_nets and n.name not in rules.ignore_nets]
    kind_of: dict[str, str] = {}
    for n in nets:
        leaf = n.leaf
        if GROUND_RE.match(leaf):
            kind_of[n.name] = "ground"
        elif not n.is_auto and POWER_RE.match(leaf) and not SIGNAL_SUFFIX_RE.search(leaf) or any(p.type == "power_out" for p in n.pins):
            kind_of[n.name] = "power"
        else:
            actives = [p for p in n.pins if p.ref in comps and not _is_ignored(comps[p.ref])]
            if actives and all(p.type == "power_in" for p in actives):
                kind_of[n.name] = "power"
            else:
                kind_of[n.name] = "signal"
    # Nets d'alimentation sans nom (Net-(U5-VCAP_1)…) : ni rail affiché, ni signal
    for n in nets:
        if kind_of[n.name] == "power" and n.is_auto:
            kind_of[n.name] = "power_aux"
    net_by_name = {n.name: n for n in nets}

    # --- 2. Blocs ----------------------------------------------------------
    comp_block: dict[str, str] = {}
    block_names: dict[str, str] = {}
    block_sheet: dict[str, str] = {}

    def _bid(name: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "bloc"

    for ref, c in comps.items():
        if c.ref.startswith("#"):
            continue
        forced = rules.components.get(ref, {}).get("block") or c.field("EN_Bloc", "Bloc", "Block")
        if forced:
            bid = _bid(forced)
            block_names.setdefault(bid, forced)
        elif c.sheet_path not in ("", "/"):
            sheet = c.sheet_path.strip("/").split("/")[-1]
            bid = _bid(sheet)
            block_names.setdefault(bid, PRETTY_NAMES.get(sheet.lower(), sheet[:1].upper() + sheet[1:]))
            block_sheet.setdefault(bid, c.sheet_file)
        elif not _is_ignored(c):
            bid = _bid(f"{c.ref}")
            block_names.setdefault(bid, c.value or c.ref)
        else:
            continue
        comp_block[ref] = bid

    # Passifs de la feuille racine : rattachés au bloc voisin majoritaire
    for ref, c in comps.items():
        if ref in comp_block or c.ref.startswith("#"):
            continue
        votes: Counter[str] = Counter()
        for n in nets:
            if kind_of[n.name] == "ground" or not any(p.ref == ref for p in n.pins):
                continue
            for p in n.pins:
                if p.ref != ref and p.ref in comp_block and not _is_ignored(comps[p.ref]):
                    votes[comp_block[p.ref]] += 1
        if votes:
            comp_block[ref] = votes.most_common(1)[0][0]

    # --- 3. Fusion des nets de signal à travers les passifs série -----------
    uf = _UF()
    pins_by_ref: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for n in nets:
        for p in n.pins:
            pins_by_ref[p.ref].append((n.name, p.pin))
    for ref, c in comps.items():
        if c.prefix not in BRIDGE_PREFIXES:
            continue
        pn = pins_by_ref.get(ref, [])
        if len(pn) == 2 and all(kind_of.get(nm) == "signal" for nm, _ in pn):
            uf.union(pn[0][0], pn[1][0])
    groups: dict[str, list[Net]] = defaultdict(list)
    for n in nets:
        if kind_of[n.name] == "signal":
            groups[uf.find(n.name)].append(n)

    def _group_name(g: list[Net]) -> str:
        named = [n for n in g if not n.is_auto]
        return (named[0] if named else g[0]).leaf

    # --- 4. Pré-passe : degré des blocs pour trouver le hub (MCU) -----------
    def _blocks_of(g: list[Net], with_passives: bool) -> list[str]:
        seen: list[str] = []
        for n in g:
            for p in n.pins:
                c = comps.get(p.ref)
                if not c or p.ref not in comp_block:
                    continue
                if _is_ignored(c) and not with_passives:
                    continue
                if comp_block[p.ref] not in seen:
                    seen.append(comp_block[p.ref])
        return seen

    neighbours: dict[str, set[str]] = defaultdict(set)
    for g in groups.values():
        bl = _blocks_of(g, False)
        for b in bl:
            neighbours[b].update(x for x in bl if x != b)
    hub = rules.hub and _bid(rules.hub)
    if not hub and neighbours:
        hub = max(neighbours, key=lambda b: (len(neighbours[b]), sum(1 for r in comp_block if comp_block[r] == b)))
    syn.hub = hub or None

    # --- 5. Liaisons de signal -----------------------------------------------
    raw: dict[tuple[str, str, str, str], list[dict]] = defaultdict(list)
    for g in groups.values():
        bl = _blocks_of(g, False)
        if len(bl) < 2:
            bl = _blocks_of(g, True)
        if len(bl) < 2:
            continue
        name = _group_name(g)
        forced = rules.nets.get(name)
        kind, inst = (forced, "") if forced else (None, "")
        if not kind:
            # Priorité : fonctions de broches du hub, puis nom du net, puis autres broches
            hub_pins = [p for n in g for p in n.pins if comp_block.get(p.ref) == hub]
            other_pins = [p for n in g for p in n.pins if comp_block.get(p.ref) != hub]
            for src in [*(p.function for p in hub_pins), *(n.leaf for n in g if not n.is_auto), *(p.function for p in other_pins)]:
                k, i = classify_text(src or "")
                if k:
                    kind, inst = k, i
                    break
        if not inst and kind:
            for p in (p for n in g for p in n.pins):
                k, i = classify_text(p.function or "")
                if k == kind and i:
                    inst = i
                    break
        kind = kind or "gpio"
        master = hub if hub in bl else max(bl, key=lambda b: len(neighbours[b]))
        for other in bl:
            if other == master:
                continue
            m_pins = [p for n in g for p in n.pins if comp_block.get(p.ref) == master]
            o_pins = [p for n in g for p in n.pins if comp_block.get(p.ref) == other]
            raw[(master, other, kind, inst)].append({"name": name, "m": m_pins, "o": o_pins})

    # Les nets sans instance rejoignent l'instance unique du même type entre deux blocs
    for (m, o, k, i) in list(raw):
        if i or (m, o, k, i) not in raw:
            continue
        insts = [key for key in raw if key[:3] == (m, o, k) and key[3]]
        if len(insts) == 1:
            raw[insts[0]].extend(raw.pop((m, o, k, i)))

    links: list[Link] = []
    for (m, o, k, i), entries in raw.items():
        direction = _direction(k, entries, comps)
        label = _label(k, i, len(entries))
        links.append(Link(id=f"L{len(links) + 1}", a=m, b=o, kind=k, label=label, instance=i,
                          nets=sorted(e["name"] for e in entries), direction=direction))

    # --- 6. Alimentation -------------------------------------------------------
    rails = sorted({n.leaf for n in nets if kind_of[n.name] == "power"})
    syn.rails = rails
    rail_pins: dict[str, list] = defaultdict(list)  # rail -> [(pin)]
    for n in nets:
        if kind_of[n.name] == "power":
            rail_pins[n.leaf].extend(n.pins)

    power_nodes: dict[str, PowerNode] = {}
    producers: dict[str, list[str]] = defaultdict(list)

    def _rails_of(ref: str, test) -> list[str]:
        return sorted({r for r, ps in rail_pins.items() for p in ps if p.ref == ref and test(p)})

    for ref, c in comps.items():
        if c.ref.startswith("#") or _is_ignored(c):
            continue
        outs = _rails_of(ref, lambda p: p.type == "power_out" or bool(OUT_PIN_RE.match(_pin_name(p))))
        ins = _rails_of(ref, lambda p: p.type in ("power_in", "input") or bool(IN_PIN_RE.match(_pin_name(p))))
        ins = [r for r in ins if r not in outs]
        cur = parse_current(c.field("EN_Courant", "Courant", "Current", "I_typ"))
        imax = parse_current(c.field("EN_Imax", "Imax", "I_max"))
        if outs and ins:
            power_nodes[ref] = PowerNode(ref, c.value, "converter", comp_block.get(ref, ""), ins, outs, cur, imax)
            for r in outs:
                producers[r].append(ref)
        elif outs and any(p.type == "power_out" for ps in rail_pins.values() for p in ps if p.ref == ref):
            power_nodes[ref] = PowerNode(ref, c.value, "source", comp_block.get(ref, ""), [], outs, cur, imax)
            for r in outs:
                producers[r].append(ref)
    for ref, c in comps.items():
        # Les connecteurs restent des sources d'énergie dans l'arbre d'alimentation, même masqués ailleurs
        if ref in power_nodes or c.ref.startswith("#") or c.prefix not in SOURCE_PREFIXES:
            continue
        srails = _rails_of(ref, lambda p: p.type in ("passive", "power_out", ""))
        srails = [r for r in srails if not producers.get(r) or SOURCE_RAIL_RE.search(r) or c.prefix == "BT"]
        if srails:
            power_nodes[ref] = PowerNode(ref, c.value, "source", comp_block.get(ref, ""), [], srails)
            for r in srails:
                producers[r].append(ref)
    for ref, c in comps.items():
        if ref in power_nodes or c.ref.startswith("#") or _is_ignored(c):
            continue
        lrails = _rails_of(ref, lambda p: p.type == "power_in" or bool(LOAD_PIN_RE.match(_pin_name(p))))
        if lrails:
            cur = parse_current(c.field("EN_Courant", "Courant", "Current", "I_typ"))
            power_nodes[ref] = PowerNode(ref, c.value, "load", comp_block.get(ref, ""), lrails, [], cur)
    syn.power = list(power_nodes.values())

    # Alimentation dans les synoptiques : flèche depuis le bloc qui produit le rail ;
    # si le rail dessert plus de 2 blocs, flèche vers le hub seulement et pastille sur les autres blocs.
    badges: dict[str, list[str]] = {}
    for rail in rails:
        prod_blocks = []
        for ref in producers.get(rail, []):
            b = power_nodes[ref].block
            if b and b not in prod_blocks:
                prod_blocks.append(b)
        cons_blocks = []
        for pn in power_nodes.values():
            if rail in pn.inputs and pn.block and pn.block not in prod_blocks and pn.block not in cons_blocks:
                cons_blocks.append(pn.block)
        if not cons_blocks:
            continue
        arrows_to = []
        if prod_blocks:
            arrows_to = cons_blocks if len(cons_blocks) <= 2 else [b for b in cons_blocks if b == hub]
            for cb in arrows_to:
                links.append(Link(id=f"L{len(links) + 1}", a=prod_blocks[0], b=cb, kind="power", label=rail,
                                  nets=[rail], direction="ab"))
        for b in cons_blocks:
            if b not in arrows_to and rail not in badges.setdefault(b, []):
                badges[b].append(rail)

    syn.links = links

    # --- 7. Blocs finaux -------------------------------------------------------
    bids = sorted(set(comp_block.values()), key=lambda b: (b != hub, b))
    for bid in bids:
        refs = sorted((r for r, b in comp_block.items() if b == bid), key=_ref_key)
        items = [Item(r, comps[r].value, comps[r].description) for r in refs if not _is_ignored(comps[r])]
        conf = rules.blocks.get(bid, {})
        name = conf.get("name") or block_names.get(bid, bid)
        cat = conf.get("category") or _category(bid, name, [comps[r] for r in refs], hub, power_nodes)
        syn.blocks.append(Block(id=bid, name=name, category=cat, sheet=block_sheet.get(bid, ""), items=items,
                                components=refs, rails=badges.get(bid, []), hidden=bool(conf.get("hide"))))
    # Blocs vides (par exemple faits uniquement de connecteurs masqués) : retirés
    syn.blocks = [b for b in syn.blocks if b.items or b.id == hub]
    kept = {b.id for b in syn.blocks if not b.hidden}
    syn.links = [lk for lk in syn.links if lk.a in kept and lk.b in kept]

    # --- 8. Bus (vue bus) --------------------------------------------------------
    syn.buses = _buses(syn, groups, comps, comp_block, hub, kind_of, net_by_name)

    # --- 9. Avertissements ---------------------------------------------------------
    syn.warnings = _warnings(syn, power_nodes, producers)
    return syn


def _ref_key(ref: str):
    m = re.match(r"([A-Za-z#_]+)(\d*)", ref)
    return (m.group(1), int(m.group(2) or 0)) if m else (ref, 0)


def _label(kind: str, inst: str, count: int) -> str:
    base = {"i2c": "I²C", "spi": "SPI", "uart": "UART", "usb": "USB", "can": "CAN", "swd": "SWD", "jtag": "JTAG"}.get(kind)
    if base:
        return f"{base}{inst}"
    if kind == "analog":
        return "Analogique" if count == 1 else f"Analogique ×{count}"
    return "GPIO" if count == 1 else f"GPIO ×{count}"


def _direction(kind: str, entries: list[dict], comps: dict[str, Component]) -> str:
    if kind in ("i2c", "spi", "swd", "jtag"):
        return "ab"
    if kind in ("uart", "usb", "can"):
        return "both"
    dirs = set()
    for e in entries:
        m_out = any(p.type in OUT_TYPES for p in e["m"])
        o_out = any(p.type in OUT_TYPES for p in e["o"])
        o_types = {p.type for p in e["o"] if not _is_ignored(comps[p.ref])}
        if o_out and not m_out:
            dirs.add("ba")
        elif m_out and not o_out:
            dirs.add("ab")
        elif o_types and o_types <= {"passive", ""}:
            prefixes = {comps[p.ref].prefix for p in e["o"] if not _is_ignored(comps[p.ref])}
            if prefixes & {"SW", "S", "BTN", "TH", "RV", "K"}:
                dirs.add("ba")
            elif prefixes & {"D", "LED", "BZ", "LS"}:
                dirs.add("ab")
            else:
                dirs.add("ba" if kind == "analog" else "none")
        elif kind == "analog":
            dirs.add("ba")
        else:
            dirs.add("both")
    if len(dirs) == 1:
        return dirs.pop()
    return "both"


def _category(bid: str, name: str, comps: list[Component], hub: str | None, power_nodes: dict[str, PowerNode]) -> str:
    if bid == hub:
        return "hub"
    if any(power_nodes.get(c.ref) and power_nodes[c.ref].role == "converter" for c in comps):
        return "power"
    actives = [c for c in comps if not _is_ignored(c)]
    text = " ".join([name] + [f"{c.ref} {c.value} {c.description}" for c in actives])
    for cat, rx in CATEGORY_RULES:  # le nom du bloc prime
        if rx.search(name):
            return cat
    for cat, rx in CATEGORY_RULES:
        if rx.search(text):
            return cat
    if actives and all(c.prefix in SOURCE_PREFIXES for c in actives):
        return "interface"
    return "other"


def _buses(syn: Synoptic, groups, comps, comp_block, hub, kind_of, net_by_name) -> list[Bus]:
    buses: dict[tuple[str, str], Bus] = {}
    hub_refs = [r for r, b in comp_block.items() if b == hub and not _is_ignored(comps[r])]
    for lk in syn.links:
        if lk.kind == "power" or lk.a != hub:
            continue
        key = (lk.kind, lk.instance)
        bus = buses.get(key)
        if not bus:
            bus = Bus(kind=lk.kind, instance=lk.instance, label=_label(lk.kind, lk.instance, 2).split(" ×")[0], master="")
            buses[key] = bus
        for net in lk.nets:
            if net not in bus.nets:
                bus.nets.append(net)
    # Composants reliés à chaque bus
    for bus in buses.values():
        devs: dict[str, BusDevice] = {}
        for g in groups.values():
            if not any(n.leaf in bus.nets for n in g):
                continue
            for n in g:
                for p in n.pins:
                    c = comps.get(p.ref)
                    if not c:
                        continue
                    if p.ref in hub_refs:
                        bus.master = bus.master or p.ref
                        continue
                    if c.prefix == "R":
                        # pull-up : une broche sur le bus, l'autre sur un rail
                        others = [nm for nm, nn in net_by_name.items() if any(q.ref == p.ref for q in nn.pins) and nm != n.name]
                        if any(kind_of.get(o) == "power" for o in others) and p.ref not in bus.pullups:
                            bus.pullups.append(p.ref)
                        continue
                    if _is_ignored(c) or p.ref in devs:
                        continue
                    devs[p.ref] = BusDevice(p.ref, c.value, comp_block.get(p.ref, ""),
                                            c.field("EN_Adresse", "I2C_ADDR", "Adresse", "Address"))
        bus.devices = sorted(devs.values(), key=lambda d: _ref_key(d.ref))
        bus.nets.sort()
    order = ["usb", "i2c", "spi", "uart", "can", "swd", "jtag", "analog", "gpio"]
    return sorted(buses.values(), key=lambda b: (order.index(b.kind) if b.kind in order else 99, b.instance))


def _warnings(syn: Synoptic, power_nodes, producers) -> list[str]:
    w: list[str] = []
    for bus in syn.buses:
        if bus.kind == "i2c":
            addrs = Counter(d.address.lower() for d in bus.devices if d.address)
            for a, n in addrs.items():
                if n > 1:
                    w.append(f"{bus.label} : conflit d'adresse {a} ({n} composants).")
            if not bus.pullups:
                w.append(f"{bus.label} : aucune résistance de pull-up détectée.")
            missing = [d.ref for d in bus.devices if not d.address]
            if missing:
                w.append(f"{bus.label} : adresse inconnue pour {', '.join(missing)} (champ I2C_ADDR).")
    for lk in syn.links:
        if lk.kind == "gpio" and lk.width >= 4:
            w.append(f"{lk.label} entre {lk.a} et {lk.b} : bus non reconnu ? Nets : {', '.join(lk.nets[:6])}.")
    for rail in syn.rails:
        if not producers.get(rail):
            w.append(f"Rail {rail} : aucune source ni convertisseur détecté.")
    linked = {lk.a for lk in syn.links} | {lk.b for lk in syn.links}
    for b in syn.blocks:
        if b.id not in linked and not b.hidden:
            w.append(f"Bloc « {b.name} » sans aucune liaison détectée.")
    return w
