"""Generate torpedo_driver_v3_sim.kicad_sch: a simulation-ready KiCad schematic of the torpedo driver.
Connectors and the ESP32 are replaced by sources and loads so the built-in simulator can run it.
Run:  python3 make_sim_schematic.py   (needs the KiCad symbol libraries installed)"""
import re, uuid, math, os

SYMDIR = "/usr/share/kicad/symbols"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "torpedo_driver_v3_sim.kicad_sch")
PROJECT = "torpedo_driver_v3_sim"

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

ROWS = [
 ("POWER INPUT  (battery, fuse, bulk cap, TVS, battery sense)", [
   V("V1", "4S LiPo 16.8V", "DC 16.8", "BAT", "GND"), R("R20", "0.03", "BAT", "NB1"), ("L", "L3", "0.5u", {1: "NB1", 2: "VBAT_IN"}),
   R("R19", "0.03", "VBAT_IN", "VBAT"), C("C1", "470u", "VBAT", "GND"), DIO("D4", "P6KE20A", "DTVS", "VBAT", "GND", "D_Zener"),
   R("R5", "22k", "VBAT", "VSENSE"), R("R6", "2.2k", "VSENSE", "GND"), C("C3", "100n", "VSENSE", "GND")]),
 ("ARM SWITCH  (GPIO10 -> U4 -> Q3)", [
   V("V2", "GPIO10 ARM", "PWL(0 0 20m 0 20.001m 3.3 310m 3.3 310.001m 0)", "GP10", "GND"), R("R23", "40", "GP10", "ARM"),
   R("R15", "220", "ARM", "OL3"), ("OPTO", "U4", "PC817", {1: "OL3", 2: "GND", 3: "GND", 4: "G3D"}, ("X", "PC817")),
   R("R14", "2.2k", "G3", "G3D"), R("R13", "4.7k", "VBAT", "G3"),
   ("PMOS", "Q3", "IRF4905", {1: "G3", 2: "VSW", 3: "VBAT"}, ("X", "IRF4905")), R("R12", "15k", "VBAT", "VSW")]),
 ("12 V GATE SUPPLY  and  ARMED-RAIL SENSE", [
   R("R9", "1k", "VSW", "VG"), DIO("D5", "12V zener", "DZ12", "VG", "GND", "D_Zener"), C("C4", "100n", "VG", "GND"),
   R("R10", "22k", "VSW", "SWSENSE"), R("R11", "2.2k", "SWSENSE", "GND"), C("C5", "100n", "SWSENSE", "GND")]),
 ("CHANNEL 1  (GPIO1 -> U2 -> Q1 -> solenoid 1)", [
   V("V3", "GPIO1 FIRE1", "PWL(0 0 30m 0 30.001m 3.3 280m 3.3 280.001m 0)", "GP1", "GND"), R("R21", "40", "GP1", "FIRE1"),
   R("R1", "220", "FIRE1", "OL1"), ("OPTO", "U2", "PC817", {1: "OL1", 2: "GND", 3: "G1", 4: "VG"}, ("X", "PC817")),
   R("R3", "4.7k", "G1", "GND"), ("NMOS", "Q1", "IRLZ44N", {1: "G1", 2: "D1N", 3: "GND"}, ("X", "IRLZ44N")),
   ("L", "L1", "30m", {1: "VSW", 2: "SOL1M"}), R("R31", "15", "SOL1M", "D1N"),
   DIO("D1", "1N5819", "D1N5819", "VSW", "D1N"), R("R7", "3.3k", "VSW", "LED1A"), DIO("LED1", "red", "DLED", "D1N", "LED1A", "LED")]),
 ("CHANNEL 2  (GPIO0 -> U3 -> Q2 -> solenoid 2)", [
   V("V4", "GPIO0 FIRE2", "DC 0", "GP0", "GND"), R("R22", "40", "GP0", "FIRE2"),
   R("R2", "220", "FIRE2", "OL2"), ("OPTO", "U3", "PC817", {1: "OL2", 2: "GND", 3: "G2", 4: "VG"}, ("X", "PC817")),
   R("R4", "4.7k", "G2", "GND"), ("NMOS", "Q2", "IRLZ44N", {1: "G2", 2: "D2N", 3: "GND"}, ("X", "IRLZ44N")),
   ("L", "L2", "30m", {1: "VSW", 2: "SOL2M"}), R("R32", "15", "SOL2M", "D2N"),
   DIO("D2", "1N5819", "D1N5819", "VSW", "D2N"), R("R8", "3.3k", "VSW", "LED2A"), DIO("LED2", "red", "DLED", "D2N", "LED2A", "LED")]),
 ("5 V INPUT  (buck -> D3 -> ESP32 5V pin; RESP stands in for the ESP32)", [
   V("V5", "buck 5.1V", "DC 5.1", "BUCK", "GND"), R("R41", "0.1", "BUCK", "5V_IN"),
   DIO("D3", "1N5819", "D1N5819", "+5V", "5V_IN"), R("R40", "82", "+5V", "GND")]),
]
SYM = {"R": ("Device", "R"), "C": ("Device", "C"), "L": ("Device", "L"), "D": ("Device", "D"), "D_Zener": ("Device", "D_Zener"),
       "LED": ("Device", "LED"), "V": ("Simulation_SPICE", "VDC"), "OPTO": ("Isolator", "PC817"),
       "NMOS": ("Device", "Q_NMOS_GDS"), "PMOS": ("Device", "Q_PMOS_GDS")}

X0, Y0, DX, DY = 30.48, 40.64, 35.56, 38.1
for r, (title, parts) in enumerate(ROWS):
    text(title, X0 - 10.16, Y0 + r * DY - 15.24, 1.778)
    for c, p in enumerate(parts):
        kind, ref, val, nets = p[:4]; raw = p[4] if len(p) > 4 else None
        part(ref, *SYM[kind], val, X0 + c * DX, Y0 + r * DY, nets, raw)

MODELS = """.subckt D1N5819 k a
D1 a k MD1N5819
.model MD1N5819 D(Is=31.7u Rs=0.051 N=1.373 Cjo=110p M=0.35 Eg=0.69 Xti=2 BV=40 IBV=1m)
.ends
.subckt DTVS k a
D1 a k MDTVS
.model MDTVS D(Is=1e-12 Rs=0.3 N=1.5 BV=20 IBV=1m Cjo=500p)
.ends
.subckt DZ12 k a
D1 a k MDZ12
.model MDZ12 D(Is=1e-14 Rs=8 N=1 BV=12 IBV=5m Cjo=50p)
.ends
.subckt DLED k a
D1 a k MDLED
.model MDLED D(Is=1e-19 N=1.6 Rs=5)
.ends
.model DBODY D(Is=1e-12 Rs=0.01 BV=55)
.model NLZ44 NMOS(Level=1 Vto=1.5 Kp=10 Lambda=0.002 Rd=0.006 Rs=0.004)
.model PF4905 PMOS(Level=1 Vto=-3 Kp=12 Lambda=0.002 Rd=0.005 Rs=0.003)
.subckt IRLZ44N g d s
M1 d g s s NLZ44
Db s d DBODY
Cgs g s 1.5n
Cgd g d 0.2n
.ends
.subckt IRF4905 g d s
M1 d g s s PF4905
Db d s DBODY
Cgs g s 3n
Cgd g d 0.6n
.ends
.subckt PC817 a k e c
Dled a m DOPTO
Vs m k 0
Fph c b Vs 0.005
Qp c b e QOPTO
Rbe b e 200meg
.model DOPTO D(Is=8.4e-13 N=2 Rs=2 Cjo=30p)
.model QOPTO NPN(Is=1e-14 Bf=200 Vaf=100 Cjc=15p Cje=10p Tf=5n)
.ends"""
text(MODELS, 300.0, 250.0, 1.0)
text(".tran 20u 400m", 300.0, 150.0, 1.778)
text("Simplified models, same as simulation/normal.cir.\nTimeline: ARM on at 20 ms, FIRE1 on at 30 ms, FIRE1 off at 280 ms, ARM off at 310 ms.\nR19 = fuse F1, R20/L3 = battery and lead, L1+R31 = solenoid 1, L2+R32 = solenoid 2, R21..R23 = GPIO output resistance, R40 = ESP32 load.\nPlot: V(/VSW), V(/D1N), V(/G1), V(/G3), I(L1), V(/SWSENSE), V(/VSENSE)", 300.0, 140.0, 1.27)

doc = (f'(kicad_sch (version 20230121) (generator eeschema)\n (uuid {ROOT})\n (paper "A2")\n (lib_symbols\n  '
       + "\n  ".join(used.values()) + "\n )\n " + "\n ".join(items)
       + '\n (sheet_instances (path "/" (page "1")))\n)\n')
open(OUT, "w").write(doc)
print("wrote", OUT, len(items), "items")
