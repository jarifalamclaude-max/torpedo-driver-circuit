"""Generate the veroboard part/net data for index.html from the v4 PCB, so the hand-wiring plan has exactly
the PCB's connections. Every pad is snapped to the 2.54 mm hole grid; collisions are reported.
Run with KiCad 7's python:  python3 make_vero_data.py   (rewrites the data block in index.html)
"""
import json, os, re
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, "..", "kicad", "torpedo_driver_v4.kicad_pcb")
HTML = os.path.join(HERE, "index.html")
OX = OY = 100.0
G = 2.54
NUDGE = {"C3": (1, 0), "C5": (1, 0), "C6": (1, 0), "C7": (1, 0)}   # ref -> (dcol, drow) manual moves where snapping collides

NETS = {
 "VBAT_IN": ("#c2185b", "Battery + before the fuse"), "VFUSE": ("#ad1457", "Between the 5 A fuse F2 and the PTC F1"),
 "VBAT": ("#d32f2f", "Battery + after the fuses"), "VSW": ("#f57c00", "Switched battery rail, live when armed"),
 "GNDP": ("#111111", "Power ground: battery minus and all solenoid returns"),
 "GNDL": ("#5d4037", "Logic ground: ESP32 side only, never joined to GNDP"),
 "D1N": ("#1565c0", "Solenoid 1 low side, Q1 drain"), "D2N": ("#00838f", "Solenoid 2 low side, Q2 drain"),
 "VG": ("#6a1b9a", "12 V gate supply from the zener"), "G1": ("#2e7d32", "Q1 gate"), "G2": ("#558b2f", "Q2 gate"),
 "G3": ("#ad1457", "Q3 gate"), "G3D": ("#795548", "Q3 gate drive through the ARM opto"),
 "LED1A": ("#c62828", "LED1 anode"), "LED2A": ("#ad5a00", "LED2 anode"),
 "OL1": ("#00695c", "U2 LED anode"), "OL2": ("#4527a0", "U3 LED anode"), "OL3": ("#bf360c", "U4 (ARM) LED anode"),
 "OSCL": ("#1b5e20", "U5 LED anode (I2C clock)"), "OSDA": ("#0d47a1", "U6 LED anode (I2C data out)"),
 "FIRE1": ("#0277bd", "GPIO1, fires solenoid 1"), "FIRE2": ("#283593", "GPIO0, fires solenoid 2"), "ARM": ("#e65100", "GPIO10, closes the arm switch"),
 "SCL_TX": ("#2e7d32", "GPIO5, I2C clock out"), "SDA_TX": ("#1565c0", "GPIO6, I2C data out"), "SDA_RX": ("#6a1b9a", "GPIO7, I2C data read-back"),
 "3V3L": ("#00796b", "ESP32 3.3 V pin (pull-up for GPIO7)"), "+5V": ("#00796b", "ESP32 5 V pin"), "5V_IN": ("#5d4037", "Logic 5 V input"),
 "SBAT": ("#827717", "ADS1115 A0: battery / 11"), "SSW": ("#4e342e", "ADS1115 A1: switched rail / 11"),
 "SD1": ("#1a237e", "ADS1115 A2: solenoid 1 low side / 11"), "SD2": ("#004d40", "ADS1115 A3: solenoid 2 low side / 11"),
 "VPRE": ("#bf360c", "LDO input after the 20 V pre-regulator"), "3V3P": ("#00897b", "3.3 V for the ADS1115, power side"),
 "SCL_P": ("#33691e", "I2C clock at the ADS1115"), "SDA_P": ("#01579b", "I2C data at the ADS1115"), "U7A": ("#880e4f", "U7 LED anode (read-back)"),
}
HEAVY = {"VBAT_IN": ["J1.+", "F2.1"], "VFUSE": ["F2.2", "F1.1"], "VBAT": ["F1.2", "C1.+", "D4.K", "Q3.S"],
         "VSW": ["Q3.D", "D1.K", "J2.+", "D2.K", "J3.+"], "D1N": ["Q1.D", "D1.A", "J2.-"], "D2N": ["Q2.D", "D2.A", "J3.-"],
         "GNDP": ["J1.-", "C1.-", "D4.A", "Q1.S", "Q2.S"]}
ESPNAMES = {"U1A": ["5V", "GND", "3V3", "IO4", "IO3", "IO2", "IO1", "IO0"], "U1B": ["IO5", "IO6", "IO7", "IO8", "IO9", "IO10", "IO20", "IO21"]}
ADSNAMES = ["VDD", "GND", "SCL", "SDA", "ADR", "ALR", "A0", "A1", "A2", "A3"]

def kind_and_names(ref, fpname, pads):
    if fpname.startswith("R_Axial") or fpname.startswith("C_Disc") or fpname.startswith("PTC"): return "ax", {"1": "1", "2": "2"}
    if fpname.startswith("Fuseholder"): return "ax", {"1": "1", "2": "2"}
    if fpname.startswith("CP_Radial_D10"): return "elec", {"1": "+", "2": "-"}
    if fpname.startswith("CP_Radial"): return "elec5", {"1": "+", "2": "-"}
    if fpname.startswith("D_DO"): return "dio", {"1": "K", "2": "A"}
    if fpname.startswith("LED"): return "led", {"1": "K", "2": "A"}
    if fpname.startswith("TO-220"): return "to220", {"1": "G", "2": "D", "3": "S"}
    if fpname.startswith("TO-92"): return "to92", {"1": "O", "2": "G", "3": "I"}
    if fpname.startswith("DIP-4"): return "dip", {k: k for k in "1234"}
    if fpname.startswith("AMASS_XT60"): return "term", {"1": "-", "2": "+"}
    if fpname.startswith("TerminalBlock"):
        plus = [p for p in pads if pads[p] in ("VSW", "5V_IN")][0]
        return "term", {plus: "+", ("2" if plus == "1" else "1"): "-"}
    if fpname.startswith("PinSocket_1x10"): return "hdr", {str(i + 1): n for i, n in enumerate(ADSNAMES)}
    raise SystemExit("no veroboard kind for " + ref + " " + fpname)

def main():
    b = pcbnew.LoadBoard(PCB)
    parts, esp = [], {"ref": "U1", "val": "ESP32-C3 SuperMini", "k": "esp", "p": []}
    occupied = {}
    for fp in sorted(b.GetFootprints(), key=lambda f: f.GetReference()):
        ref = fp.GetReference(); name = fp.GetFPID().GetLibItemName().wx_str()
        if ref.startswith("H"): continue
        pads = {}; pos = {}
        for p in fp.Pads():
            n = p.GetNumber()
            if not n or n in pos: continue                       # skip XT60 pegs and the second leg of each fuse clip
            pos[n] = (pcbnew.ToMM(p.GetPosition().x) - OX, pcbnew.ToMM(p.GetPosition().y) - OY); pads[n] = p.GetNetname()
        dc, dr = NUDGE.get(ref, (0, 0))
        # snap pin 1, then place the other pins by their rounded pitch (at least one hole apart)
        first = sorted(pos, key=lambda s: int(s))[0]; x1, y1 = pos[first]
        c1, r1 = int(round(x1 / G)) + dc, int(round(y1 / G)) + dr
        cell = {}
        for n, (x, y) in pos.items():
            ddx, ddy = int(round((x - x1) / G)), int(round((y - y1) / G))
            if n != first and ddx == 0 and ddy == 0:
                if abs(x - x1) >= abs(y - y1): ddx = 1 if x > x1 else -1
                else: ddy = 1 if y > y1 else -1
            cell[n] = (c1 + ddx, r1 + ddy)
        if ref in ESPNAMES:
            for n, (c, r) in cell.items():
                esp["p"].append([ESPNAMES[ref][int(n) - 1], c, r, pads[n] or None])
                occupied.setdefault((c, r), []).append(ref + "." + n)
            continue
        k, names = kind_and_names(ref, name, pads)
        val = fp.GetValue()
        val = {"PC817": "PC817"}.get(val, val)
        pins = []
        for n in sorted(cell, key=lambda s: int(s)):
            c, r = cell[n]; pins.append([names[n], c, r, pads[n] or None]); occupied.setdefault((c, r), []).append(ref + "." + n)
        parts.append({"ref": ref, "val": val, "k": k, "p": pins})
    parts.append(esp)
    clashes = {k: v for k, v in occupied.items() if len(v) > 1}
    cols = max(p[1] for pt in parts for p in pt["p"]) + 2; rows = max(p[2] for pt in parts for p in pt["p"]) + 2
    return parts, clashes, cols, rows

if __name__ == "__main__":
    parts, clashes, cols, rows = main()
    if clashes: raise SystemExit("hole collisions: " + "; ".join(f"{k}: {v}" for k, v in sorted(clashes.items())))
    js = ("/* ---------- generated by make_vero_data.py from ../kicad/torpedo_driver_v4.kicad_pcb ---------- */\n"
          f"const NETS={json.dumps({k: {'c': c, 'd': d} for k, (c, d) in NETS.items()}, ensure_ascii=False)};\n"
          f"const HEAVY={json.dumps(HEAVY)};\n"
          f"const BASE_PARTS={json.dumps(parts, ensure_ascii=False)};\n"
          f"const BASE_COLS={cols}, BASE_ROWS={rows}, P=20, OFF=34;\n/* ---------- end generated ---------- */\n")
    t = open(HTML).read()
    s = t.index("/* ---------- nets ---------- */") if "/* ---------- nets ---------- */" in t else t.index("/* ---------- generated")
    e = t.index("const holeName")
    t = t[:s] + js + t[e:]
    open(HTML, "w").write(t)
    print(f"{len(parts)} parts, board {cols} x {rows} holes, no collisions")
