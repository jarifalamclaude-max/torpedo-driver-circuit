"""Build the SPICE netlist straight from the routed v3 board file (pad nets), so the simulated
circuit is exactly what is on the PCB. Battery, solenoids, buck and ESP32 pins are attached to the
connector pads by pad number (ESP pins by the SuperMini pinout, not by net name)."""
import pcbnew, re, subprocess, json, sys, os

PCB = "/home/claude/torpedo/pcb3/torpedo_driver_v3.kicad_pcb"
ESP = {"U1A": {1: "5V", 2: "GND", 3: "3V3", 4: "GPIO4", 5: "GPIO3", 6: "GPIO2", 7: "GPIO1", 8: "GPIO0"},
       "U1B": {1: "GPIO5", 2: "GPIO6", 3: "GPIO7", 4: "GPIO8", 5: "GPIO9", 6: "GPIO10", 7: "GPIO20", 8: "GPIO21"}}
RVAL = {"k": 1e3, "M": 1e6}

def node(n):
    if n == "GND": return "0"
    if not n: return None
    s = re.sub(r"[^a-z0-9_]", "", n.lower().replace("+", "p"))
    return ("n" + s) if s[0].isdigit() else s

def rnum(v):
    m = re.match(r"([\d.]+)\s*([kM]?)", v); return float(m.group(1)) * RVAL.get(m.group(2), 1)

def load():
    b = pcbnew.LoadBoard(PCB); parts = {}
    for fp in b.GetFootprints():
        parts[fp.GetReference()] = (fp.GetValue(), {int(p.GetNumber()): node(p.GetNetname()) for p in fp.Pads() if p.GetNumber()})
    return parts

MODELS = """
.model D1N5819 D(Is=31.7u Rs=0.051 N=1.373 Cjo=110p M=0.35 Eg=0.69 Xti=2 BV=40 IBV=1m)
.model DTVS D(Is=1e-12 Rs=0.3 N=1.5 BV=20 IBV=1m Cjo=500p)
.model DZ12 D(Is=1e-14 Rs=8 N=1 BV=12 IBV=5m Cjo=50p)
.model DLED D(Is=1e-19 N=1.6 Rs=5)
.model NLZ44 NMOS(Level=1 Vto=1.5 Kp=10 Lambda=0.002 Rd=0.006 Rs=0.004)
.model PF4905 PMOS(Level=1 Vto=-3 Kp=12 Lambda=0.002 Rd=0.005 Rs=0.003)
.model DBODY D(Is=1e-12 Rs=0.01 BV=55)
.subckt PC817 a k c e CTR=1
Dled a m DOPTO
Vs m k 0
Fph c b Vs {CTR/200}
Qp c b e QOPTO
Rbe b e 200meg
.model DOPTO D(Is=8.4e-13 N=2 Rs=2 Cjo=30p)
.model QOPTO NPN(Is=1e-14 Bf=200 Vaf=100 Cjc=15p Cje=10p Tf=5n)
.ends
"""

def netlist(sc):
    P = load(); L = ["* torpedo driver v3 - generated from the PCB file", ".param VB=%g LSOL=30m" % sc.get("VB", 16.8), MODELS]
    used = set()
    for ref in sorted(P):
        val, pd = P[ref]; used.add(ref)
        if ref[0] == "R":
            L.append(f"{ref} {pd[1]} {pd[2]} {rnum(val):g}")
        elif ref == "C1":
            L.append(f"C1 {pd[1]} c1m 470u IC={sc.get('c1_ic', '{VB}')}\nRC1 c1m {pd[2]} 0.08")
        elif ref[0] == "C":
            L.append(f"{ref} {pd[1]} {pd[2]} 100n")
        elif ref.startswith("LED"):
            L.append(f"D{ref} {pd[2]} {pd[1]} DLED")                       # pad2 = anode, pad1 = cathode
        elif ref in ("D1", "D2", "D3"):
            L.append(f"{ref} {pd[2]} {pd[1]} D1N5819")
        elif ref == "D4":
            L.append(f"D4 {pd[2]} {pd[1]} DTVS")
        elif ref == "D5":
            L.append(f"D5 {pd[2]} {pd[1]} DZ12")
        elif ref in ("Q1", "Q2"):                                           # TO-220: 1 G, 2 D, 3 S
            g, d, s = pd[1], pd[2], pd[3]
            L.append(f"M{ref} {d} {g} {s} {s} NLZ44\nDb{ref} {s} {d} DBODY\nCgs{ref} {g} {s} 1.5n\nCgd{ref} {g} {d} 0.2n")
        elif ref == "Q3":
            g, d, s = pd[1], pd[2], pd[3]
            L.append(f"M{ref} {d} {g} {s} {s} PF4905\nDb{ref} {d} {s} DBODY\nCgs{ref} {g} {s} 3n\nCgd{ref} {g} {d} 0.6n")
        elif ref in ("U2", "U3", "U4"):                                     # DIP-4: 1 A, 2 K, 3 E, 4 C
            L.append(f"X{ref} {pd[1]} {pd[2]} {pd[4]} {pd[3]} PC817 CTR={sc.get('CTR', 1.0)}")
        elif ref == "F1":
            L.append(f"RF1 {pd[1]} {pd[2]} 0.03")
        elif ref == "J1":                                                   # XT60: pad2 = +, pad1 = -
            assert pd[1] == "0", "battery minus must be GND"
            L.append(f"VBAT bat 0 {sc.get('vbat_src', '{VB}')}\nRbat bat nb1 0.03\nLwire nb1 {pd[2]} 0.5u")
        elif ref in ("J2", "J3"):                                           # solenoid across the terminal
            n = int(ref[1]) - 1                                             # J2 -> solenoid 1, J3 -> solenoid 2
            if sc.get("nosol") == n:
                L.append(f"Vdummy{n} dm{n} 0 0\nRdummy{n} dm{n} 0 1")           # keeps i(...) measurable, no coil
            else:
                L.append(f"Lsol{n} {pd[1]} sm{n} {{LSOL}}\nRsol{n} sm{n} {pd[2]} 15")
        elif ref == "J4":
            hot = [n for n in pd.values() if n != "0"]; assert len(hot) == 1 and "0" in pd.values()
            L.append(f"Vbuck buck 0 5.1\nRbuck buck {hot[0]} 0.1")
        elif ref in ESP:
            for num, name in ESP[ref].items():
                n = pd.get(num)
                if name == "GND": assert n == "0", "ESP GND pin must be on GND"
                elif name == "5V": L.append(f"Resp {n} 0 82")
                elif n is None: continue
                elif name in ("GPIO3", "GPIO4"): L.append(f"Radc{name[4:]} {n} 0 10meg")
                else:
                    g = name[4:]; w = sc.get("gpio", {}).get(int(g), "DC 0")
                    if w == "float":   L.append(f"Vpu{g} pu{g} 0 3.3\nRpu{g} pu{g} {n} 45k")
                    else:              L.append(f"Vgpio{g} gp{g}i 0 {w}\nRgpio{g} gp{g}i {n} 40")
        elif ref[0] == "H": pass
        else: raise SystemExit("unhandled part " + ref)
    L += sc.get("extra", [])
    L += [".options method=gear reltol=1e-4", f".tran {sc.get('tstep', '5u')} {sc.get('tstop', '400m')} 0 {sc.get('tmax', '20u')} uic", ".control", "run",
          "let ratio = v(vsw)/v(vbat)", "let vgs3 = v(g3)-v(vbat)"]
    L += sc.get("lets", [])
    for lab, expr, kind in sc["meas"]:
        L.append(f"meas tran {lab} {kind.replace('X', expr)}")
    if sc.get("wr"): L.append("wrdata %s %s" % (sc["wr"][0], " ".join(sc["wr"][1])))
    L += [".endc", ".end"]
    return "\n".join(L) + "\n"

def run(sc):
    path = f"/home/claude/torpedo/sim3/{sc['name']}.cir"; open(path, "w").write(netlist(sc))
    out = subprocess.run(["ngspice", "-b", path], capture_output=True, text=True, timeout=600)
    res = {}
    for line in (out.stdout + out.stderr).splitlines():
        m = re.match(r"^(\w+)\s+=\s+([-+\d.eE]+)", line.strip())
        if m: res[m.group(1).lower()] = float(m.group(2))
    errs = [l for l in (out.stdout + out.stderr).splitlines() if "rror" in l or "failed" in l.lower() or "singular" in l.lower()]
    return res, errs

if __name__ == "__main__":
    P = load()
    for r in sorted(P, key=lambda s: (re.sub(r"\d", "", s), int(re.sub(r"\D", "", s) or 0))):
        print(f"{r:5s} {P[r][0]:22s} {P[r][1]}")
