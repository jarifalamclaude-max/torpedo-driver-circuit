"""Generate torpedo_driver_v4_sim.kicad_sch: a simulation-ready KiCad schematic of the v4 driver.
Connectors and the ESP32 are replaced by sources and loads so KiCad's built-in simulator can run it.
The logic side sits on its own ground net GNDL, tied to GND only by 1 Gohm and 10 pF (the isolation barrier).
The models (MOSFETs fitted to the IR datasheets, electromechanical solenoid) are written on the sheet,
copied from ../kicad/simulation/models.lib.
Run:  python3 make_sim_schematic.py   (needs the KiCad symbol libraries installed)"""
import re, uuid, math, os

SYMDIR = "/usr/share/kicad/symbols"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "torpedo_driver_v4_sim.kicad_sch")
PROJECT = "torpedo_driver_v4_sim"

def block(text, start):
    d = 0
    for i in range(start, len(text)):
        if text[i] == "(": d += 1
        elif text[i] == ")":
            d -= 1
            if d == 0: return text[start:i + 1]

_cache = {}
def lib_symbol(lib, name):
    if (lib, name) in _cache: return _cache[(lib, name)]
    t = open(f"{SYMDIR}/{lib}.kicad_sym").read()
    i = t.find(f'(symbol "{name}"'); assert i >= 0, name
    b = block(t, i)
    m = re.search(r'\(extends "([^"]+)"\)', b)
    if m:                                   # derived symbol: use the parent's graphics under this name
        base = block(t, t.find(f'(symbol "{m.group(1)}"'))
        b = base.replace(f'"{m.group(1)}', f'"{name}')
    pins = {}
    for pm in re.finditer(r'\(pin \w+ \w+\s*\(at ([-\d.]+) ([-\d.]+) (\d+)\)', b):
        num = re.search(r'\(number "([^"]+)"', b[pm.end():]).group(1)
        pins[num] = (float(pm.group(1)), float(pm.group(2)), int(pm.group(3)))
    b = b.replace(f'(symbol "{name}"', f'(symbol "{lib}:{name}"', 1)
    _cache[(lib, name)] = (b, pins)
    return _cache[(lib, name)]

U = lambda: str(uuid.uuid4())
ROOT = U()
items, used, pwr = [], {}, [0]

def prop(k, v, x, y, hide=False):
    v = v.replace("\\", "\\\\").replace('"', '\\"')
    return f'(property "{k}" "{v}" (at {x:.2f} {y:.2f} 0) (effects (font (size 1.27 1.27)){" hide" if hide else ""}))'

def part(ref, lib, name, value, x, y, nets, raw=None):
    body, pins = lib_symbol(lib, name); used[f"{lib}:{name}"] = body
    ps = [prop("Reference", ref, x + 6.35, y - 1.27), prop("Value", value, x + 6.35, y + 1.27),
          prop("Footprint", "", x, y, True), prop("Datasheet", "", x, y, True)]
    if raw:
        ps += [prop("Sim.Device", "SPICE", x, y, True), prop("Sim.Params", f'type="{raw[0]}" model="{raw[1]}" lib=""', x, y, True)]
        if len(raw) > 2: ps.append(prop("Sim.Pins", raw[2], x, y, True))
    pinl = " ".join(f'(pin "{n}" (uuid {U()}))' for n in pins)
    items.append(f'(symbol (lib_id "{lib}:{name}") (at {x:.2f} {y:.2f} 0) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid {U()})\n  '
                 + "\n  ".join(ps) + f'\n  {pinl}\n  (instances (project "{PROJECT}" (path "/{ROOT}" (reference "{ref}") (unit 1)))))')
    for n, net in nets.items():
        px, py, a = pins[str(n)]
        sx, sy = x + px, y - py                                   # pin end on the sheet
        ex, ey = sx - 2.54 * round(math.cos(math.radians(a))), sy + 2.54 * round(math.sin(math.radians(a)))
        items.append(f'(wire (pts (xy {sx:.2f} {sy:.2f}) (xy {ex:.2f} {ey:.2f})) (stroke (width 0) (type default)) (uuid {U()}))')
        if net == "GND":
            pwr[0] += 1; b2, _ = lib_symbol("power", "GND"); used["power:GND"] = b2
            items.append(f'(symbol (lib_id "power:GND") (at {ex:.2f} {ey:.2f} 0) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid {U()})\n  '
                         + prop("Reference", f"#PWR{pwr[0]:03d}", ex, ey, True) + " " + prop("Value", "GND", ex, ey + 3.81, True)
                         + f' (pin "1" (uuid {U()}))\n  (instances (project "{PROJECT}" (path "/{ROOT}" (reference "#PWR{pwr[0]:03d}") (unit 1)))))')
            continue
        ang, just = {0: (180, "right bottom"), 180: (0, "left bottom"), 90: (270, "right bottom"), 270: (90, "left bottom")}[a]
        items.append(f'(label "{net}" (at {ex:.2f} {ey:.2f} {ang}) (effects (font (size 1.27 1.27)) (justify {just})) (uuid {U()}))')

def text(s, x, y, size=1.27):
    s = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    items.append(f'(text "{s}" (at {x:.2f} {y:.2f} 0) (effects (font (size {size} {size})) (justify left bottom)) (uuid {U()}))')

R = lambda ref, val, a, b: ("R", ref, val, {1: a, 2: b})
C = lambda ref, val, a, b: ("C", ref, val, {1: a, 2: b})
DIO = lambda ref, val, model, k, a, sym="D": (sym, ref, val, {1: k, 2: a}, ("X", model))
V = lambda ref, val, spec, p, n: ("V", ref, val, {1: p, 2: n}, ("V", spec))

ARM = "PWL(0 0 20m 0 20.001m 3.3 330m 3.3 330.001m 0)"
FIRE = "PWL(0 0 30m 0 30.001m 3.3 230m 3.3 230.001m 0)"
X = lambda ref, val, model, nets, sym: (sym, ref, val, nets, ("X", model))
ROWS = [
 ("POWER INPUT  (battery, F2 fast fuse, F1 PTC, bulk cap, TVS, battery divider 1/11)", [
   V("V1", "4S LiPo 16.8V", "DC 16.8", "BAT", "GND"), R("R30", "0.03", "BAT", "NB1"), ("L", "L3", "0.5u", {1: "NB1", 2: "VBAT_IN"}),
   R("R31", "0.02", "VBAT_IN", "VFUSE"), R("R32", "0.03", "VFUSE", "VBAT"), C("C1", "470u", "VBAT", "C1M"), R("R33", "0.08", "C1M", "GND"),
   DIO("D4", "P6KE22A", "DTVS22_KA", "VBAT", "GND", "D_Zener"), R("R5", "200k", "VBAT", "SBAT"), R("R6", "20k", "SBAT", "GND"), C("C3", "100n", "SBAT", "GND")]),
 ("ARM SWITCH  (GPIO10 on GNDL -> U4 -> Q3, C11 holds Q3 off at plug-in, D6 clamps Vgs at 15 V)", [
   V("V2", "GPIO10 ARM", ARM, "GP10", "GNDL"), R("R40", "40", "GP10", "ARM"), R("R15", "150", "ARM", "OL3"),
   X("U4", "PC817", "PC817_AKEC", {1: "OL3", 2: "GNDL", 3: "GND", 4: "G3D"}, "OPTO"),
   R("R14", "1k", "G3", "G3D"), R("R13", "4.7k", "VBAT", "G3"), DIO("D6", "15V zener", "DZ15_KA", "VBAT", "G3", "D_Zener"),
   C("C11", "100n", "VBAT", "G3"), X("Q3", "IRF4905", "IRF4905_GDS", {1: "G3", 2: "VSW", 3: "VBAT"}, "PMOS"), R("R12", "68k", "VBAT", "VSW")]),
 ("12 V GATE RAIL  and  SWITCHED-RAIL SENSE 1/11", [
   R("R9", "680", "VSW", "VG"), DIO("D5", "12V zener", "DZ12_KA", "VG", "GND", "D_Zener"), C("C4", "100n", "VG", "GND"),
   R("R10", "200k", "VSW", "SSW"), R("R11", "20k", "SSW", "GND"), C("C5", "100n", "SSW", "GND")]),
 ("CHANNEL 1  (GPIO1 -> U2 -> Q1 -> solenoid 1, gate LED, low-side sense 1/11)", [
   V("V3", "GPIO1 FIRE1", FIRE, "GP1", "GNDL"), R("R41", "40", "GP1", "FIRE1"), R("R1", "150", "FIRE1", "OL1"),
   X("U2", "PC817", "PC817_AKEC", {1: "OL1", 2: "GNDL", 3: "G1", 4: "VG"}, "OPTO"),
   R("R3", "4.7k", "G1", "GND"), R("R7", "10k", "G1", "LED1A"), DIO("LED1", "red", "DLED_KA", "GND", "LED1A", "LED"),
   X("Q1", "IRLZ44N", "IRLZ44N_GDS", {1: "G1", 2: "D1N", 3: "GND"}, "NMOS"),
   X("SOL1", "solenoid", "SOLENOID", {1: "VSW", 2: "D1N"}, "L"), DIO("D1", "UF5408", "DUF5408_KA", "VSW", "D1N"),
   R("R22", "200k", "D1N", "SD1"), R("R23", "20k", "SD1", "GND"), C("C6", "100n", "SD1", "GND")]),
 ("CHANNEL 2  (GPIO0 -> U3 -> Q2 -> solenoid 2)", [
   V("V4", "GPIO0 FIRE2", "DC 0", "GP0", "GNDL"), R("R42", "40", "GP0", "FIRE2"), R("R2", "150", "FIRE2", "OL2"),
   X("U3", "PC817", "PC817_AKEC", {1: "OL2", 2: "GNDL", 3: "G2", 4: "VG"}, "OPTO"),
   R("R4", "4.7k", "G2", "GND"), R("R8", "10k", "G2", "LED2A"), DIO("LED2", "red", "DLED_KA", "GND", "LED2A", "LED"),
   X("Q2", "IRLZ44N", "IRLZ44N_GDS", {1: "G2", 2: "D2N", 3: "GND"}, "NMOS"),
   X("SOL2", "solenoid", "SOLENOID", {1: "VSW", 2: "D2N"}, "L"), DIO("D2", "UF5408", "DUF5408_KA", "VSW", "D2N"),
   R("R24", "200k", "D2N", "SD2"), R("R25", "20k", "SD2", "GND"), C("C7", "100n", "SD2", "GND")]),
 ("3.3 V ADC RAIL, LOGIC SUPPLY, ISOLATION BARRIER (R45 + C12 stand for the gap between GNDL and GND)", [
   R("R26", "1k", "VBAT", "VPRE"), DIO("D7", "20V zener", "DZ20_KA", "VPRE", "GND", "D_Zener"), C("C8", "10u", "VPRE", "GND"),
   X("U8", "LP2950-3.3", "LDO33", {1: "3V3P", 2: "GND", 3: "VPRE"}, "LDO"), C("C9", "10u", "3V3P", "GND"), R("R46", "16.5k", "3V3P", "GND"),
   V("V5", "logic 5.1V", "DC 5.1", "5V_IN", "GNDL"), DIO("D3", "1N5819", "D1N5819_KA", "+5V", "5V_IN"), R("R44", "82", "+5V", "GNDL"),
   R("R45", "1G", "GNDL", "GND"), C("C12", "10p", "GNDL", "GND")]),
]
SYM = {"R": ("Device", "R"), "C": ("Device", "C"), "L": ("Device", "L"), "D": ("Device", "D"), "D_Zener": ("Device", "D_Zener"),
       "LED": ("Device", "LED"), "V": ("Simulation_SPICE", "VDC"), "OPTO": ("Isolator", "PC817"),
       "NMOS": ("Device", "Q_NMOS_GDS"), "PMOS": ("Device", "Q_PMOS_GDS"), "LDO": ("Regulator_Linear", "LP2950-3.3_TO92")}

X0, Y0, DX, DY = 30.48, 40.64, 35.56, 38.1
for r, (title, parts) in enumerate(ROWS):
    text(title, X0 - 10.16, Y0 + r * DY - 15.24, 1.778)
    for c, p in enumerate(parts):
        kind, ref, val, nets = p[:4]; raw = p[4] if len(p) > 4 else None
        part(ref, *SYM[kind], val, X0 + c * DX, Y0 + r * DY, nets, raw)

WRAP = """.subckt IRLZ44N_GDS g d s
X1 d g s IRLZ44N
.ends
.subckt IRF4905_GDS g d s
X1 d g s IRF4905
.ends
.subckt PC817_AKEC a k e c
X1 a k c e PC817
.ends
.subckt DUF5408_KA k a
D1 a k DUF5408
.ends
.subckt D1N5819_KA k a
D1 a k D1N5819
.ends
.subckt DTVS22_KA k a
D1 a k DTVS22
.ends
.subckt DZ12_KA k a
D1 a k DZ12
.ends
.subckt DZ15_KA k a
D1 a k DZ15
.ends
.subckt DZ20_KA k a
D1 a k DZ20
.ends
.subckt DLED_KA k a
D1 a k DLED
.ends"""
MODELS = WRAP + "\n" + "\n".join(l for l in open(os.path.join(HERE, "..", "kicad", "simulation", "models.lib")).read().splitlines() if l.strip())
text(MODELS, 545.0, 20.0, 1.0)
text(".tran 20u 400m", 20.0, 272.0, 1.778)
text("Same circuit and models as ../kicad/simulation (generated from the v4 PCB).\nTimeline: ARM on at 20 ms, FIRE1 on at 30 ms, FIRE1 off at 230 ms, ARM off at 330 ms.\nR30/L3 = battery and lead, R31 = fuse F2, R32 = PTC F1, R33 = C1 ESR, R40..R42 = GPIO output resistance,\nR44 = ESP32 load, R46 = ADS1115 + pull-up load on 3V3P, R45/C12 = isolation barrier. SOL1/SOL2 = electromechanical solenoid.\nPlot: V(/VSW), V(/D1N), V(/G1), V(/G3), I(SOL1), V(/SD1), V(/SBAT), and the plunger position V(xsol1.x)", 20.0, 282.0, 1.27)

doc = (f'(kicad_sch (version 20230121) (generator eeschema)\n (uuid {ROOT})\n (paper "A1")\n (lib_symbols\n  '
       + "\n  ".join(used.values()) + "\n )\n " + "\n ".join(items)
       + '\n (sheet_instances (path "/" (page "1")))\n)\n')
open(OUT, "w").write(doc)
print("wrote", OUT, len(items), "items")
