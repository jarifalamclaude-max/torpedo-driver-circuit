"""Build the SPICE netlist straight from the routed v4 board file (pad nets), so the simulated circuit is
exactly what is on the PCB. Battery, solenoids, logic supply and ESP32 pins are attached to the connector
pads by pad number (ESP pins by the SuperMini pinout, not by net name).

GNDP (battery minus) is SPICE ground. GNDL (logic ground) is a separate node tied to it only by 1 Gohm and
10 pF, which is what the isolation barrier looks like electrically.

Run with KiCad 7's python:  python3 board2spice.py   (prints the part list)
"""
import os, re, subprocess
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, "..", "torpedo_driver_v4.kicad_pcb")
MODELS = os.path.join(HERE, "models.lib")
OUTDIR = os.path.join(HERE, "out")
ESP = {"U1A": {1: "5V", 2: "GND", 3: "3V3", 4: "GPIO4", 5: "GPIO3", 6: "GPIO2", 7: "GPIO1", 8: "GPIO0"},
       "U1B": {1: "GPIO5", 2: "GPIO6", 3: "GPIO7", 4: "GPIO8", 5: "GPIO9", 6: "GPIO10", 7: "GPIO20", 8: "GPIO21"}}
ESP_INPUTS = {"GPIO7"}          # SDA read-back from U7
RVAL = {"k": 1e3, "M": 1e6, "": 1.0}
SOL_DEFAULT = dict(R=15, LO="25m", LC="75m", S="8m", M="30m", K=200, F0=0.8, C=2)

def node(n):
    if n == "GNDP": return "0"
    if not n: return None
    s = re.sub(r"[^a-z0-9_]", "", n.lower().replace("+", "p"))
    return ("n" + s) if s[0].isdigit() else s

def rnum(v):
    m = re.match(r"([\d.]+)\s*([kM]?)", v); return float(m.group(1)) * RVAL[m.group(2)]

def load():
    b = pcbnew.LoadBoard(PCB); parts = {}
    for fp in b.GetFootprints():
        parts[fp.GetReference()] = (fp.GetValue(), {int(p.GetNumber()): node(p.GetNetname()) for p in fp.Pads() if p.GetNumber().isdigit()})
    return parts

def netlist(sc):
    P = load(); sol = dict(SOL_DEFAULT, **sc.get("sol", {}))
    L = [f"* torpedo driver v4 - generated from the PCB file, scenario {sc['name']}",
         f".param VB={sc.get('VB', 16.8)}", f".include {MODELS}",
         "Riso gndl 0 1G", "Ciso gndl 0 10p"]
    vto_n, vto_p, ctr, cjc = sc.get("VTO_N", 1.75), sc.get("VTO_P", -3.0), sc.get("CTR", 1.0), sc.get("CJC", "15p")
    for ref in sorted(P):
        val, pd = P[ref]
        if ref[0] == "R":
            L.append(f"{ref} {pd[1]} {pd[2]} {rnum(val):g}")
        elif ref == "C1":
            L.append(f"C1 {pd[1]} c1m 470u IC={sc.get('c1_ic', '{VB}')}\nRC1 c1m {pd[2]} 0.08")
        elif ref in ("C8", "C9"):
            L.append(f"{ref} {pd[1]} {ref.lower()}m 10u\nR{ref}esr {ref.lower()}m {pd[2]} 1")
        elif ref[0] == "C":
            L.append(f"{ref} {pd[1]} {pd[2]} {'100n' if val.startswith('100nF') else val.split()[0].replace('F', '')}")
        elif ref.startswith("LED"):
            L.append(f"D{ref} {pd[2]} {pd[1]} DLED")                         # pad 2 anode, pad 1 cathode
        elif ref in ("D1", "D2"):
            L.append(f"{ref} {pd[2]} {pd[1]} {sc.get('flyback', 'DUF5408')}")   # pad 1 = K
        elif ref == "D3":
            L.append(f"D3 {pd[2]} {pd[1]} D1N5819")
        elif ref == "D4":
            L.append(f"D4 {pd[2]} {pd[1]} DTVS22")
        elif ref in ("D5", "D6", "D7"):
            L.append(f"{ref} {pd[2]} {pd[1]} {dict(D5='DZ12', D6='DZ15', D7='DZ20')[ref]}")
        elif ref in ("Q1", "Q2"):                                             # TO-220: 1 G, 2 D, 3 S
            L.append(f"X{ref} {pd[2]} {pd[1]} {pd[3]} IRLZ44N VTO={vto_n}")
        elif ref == "Q3":
            L.append(f"XQ3 {pd[2]} {pd[1]} {pd[3]} IRF4905 VTO={vto_p}")
        elif ref in ("U2", "U3", "U4", "U5", "U6", "U7"):                     # DIP-4: 1 A, 2 K, 3 E, 4 C
            c = sc.get("CTR_" + ref, ctr)
            L.append(f"X{ref} {pd[1]} {pd[2]} {pd[4]} {pd[3]} PC817 CTR={c} CJC={cjc}")
        elif ref == "U8":
            L.append(f"XU8 {pd[1]} {pd[2]} {pd[3]} LDO33")
        elif ref == "U9":                                                     # ADS1115 module: VDD current, input loads
            L.append(f"Iads {pd[1]} {pd[2]} 200u")
            for k in (7, 8, 9, 10):
                L.append(f"Radc{k} {pd[k]} {pd[2]} 6meg")
            L.append(f"Rmpu1 {pd[3]} {pd[1]} 10k\nRmpu2 {pd[4]} {pd[1]} 10k")   # module's own I2C pull-ups
        elif ref == "F1":
            L.append(f"RF1 {pd[1]} {pd[2]} 0.03")
        elif ref == "F2":
            L.append(f"RF2 {pd[1]} {pd[2]} 0.02")
        elif ref == "J1":                                                     # XT60: pad 2 = +, pad 1 = -
            assert pd[1] == "0", "battery minus must be GNDP"
            L.append(f"VBAT bat 0 {sc.get('vbat_src', '{VB}')}\nRbat bat nb1 0.03\nLwire nb1 {pd[2]} 0.5u")
        elif ref in ("J2", "J3"):                                             # solenoid: + = VSW pad, - = DxN pad
            plus = [k for k in pd if pd[k] == "vsw"][0]; minus = [k for k in pd if k != plus][0]
            n = 1 if ref == "J2" else 2
            if sc.get("nosol") == n: continue
            L.append(f"Vsens{n} {pd[plus]} s{n}a 0")
            L.append(f"XSOL{n} s{n}a {pd[minus]} SOLENOID R={sol['R']} LO={sol['LO']} LC={sol['LC']} S={sol['S']} "
                     f"M={sol['M']} K={sol['K']} F0={sol['F0']} C={sol['C']}")
        elif ref == "J4":
            assert pd[1] == "gndl"
            L.append(f"Vlogic l5 gndl 5.1\nRlogic l5 {pd[2]} 0.1")
        elif ref in ESP:
            for num, name in ESP[ref].items():
                n = pd.get(num)
                if n is None: continue
                if name == "GND": assert n == "gndl", "ESP GND pin must be on GNDL"
                elif name == "5V": L.append(f"Resp {n} gndl 82")
                elif name == "3V3": L.append(f"V3v3 v3i gndl 3.3\nR3v3 v3i {n} 1")
                elif name in ESP_INPUTS: L.append(f"Rin{name[4:]} {n} gndl 10meg")
                else:
                    g = name[4:]; w = sc.get("gpio", {}).get(int(g), "DC 0")
                    if w == "float": L.append(f"Vpu{g} pu{g} gndl 3.3\nRpu{g} pu{g} {n} 45k")
                    else:            L.append(f"Vgpio{g} gp{g}i gndl {w}\nRgpio{g} gp{g}i {n} 40")
        elif ref[0] == "H": pass
        else: raise SystemExit("unhandled part " + ref)
    L += sc.get("extra", [])
    L += [".options method=gear reltol=1e-4 itl4=100", f".tran {sc.get('tstep', '10u')} {sc.get('tstop', '400m')} 0 {sc.get('tmax', '20u')} uic",
          ".control", "set noaskquit", "run",
          "let ratio = v(vsw)/v(vbat)", "let vgs3 = v(g3)-v(vbat)"]
    # drop measurements whose vectors do not exist in this scenario (missing solenoid, floating GPIO)
    gone = [f"vsens{sc['nosol']}", f"xsol{sc['nosol']}."] if sc.get("nosol") else []
    gone += [f"vgpio{g}" for g, w in sc.get("gpio", {}).items() if w == "float"]
    lets = [(a, b) for a, b in sc.get("lets", []) if not any(x in b for x in gone)]
    names = {a for a, _ in lets}; dropped = {a for a, _ in sc.get("lets", [])} - names
    L += [f"let {a} = {b}" for a, b in lets]
    for lab, expr, kind in sc["meas"]:
        if expr in dropped or any(x in expr for x in gone): continue
        L.append(f"meas tran {lab} {kind.replace('X', expr)}")
    if sc.get("wr"): L.append("wrdata %s %s" % (os.path.join(OUTDIR, sc["wr"][0]), " ".join(sc["wr"][1])))
    L += [".endc", ".end"]
    return "\n".join(L) + "\n"

def run(sc):
    os.makedirs(OUTDIR, exist_ok=True)
    path = os.path.join(OUTDIR, f"{sc['name']}.cir"); open(path, "w").write(netlist(sc))
    out = subprocess.run(["ngspice", "-b", path], capture_output=True, text=True, timeout=1200)
    res = {}
    for line in (out.stdout + out.stderr).splitlines():
        m = re.match(r"^(\w+)\s+=\s+([-+\d.eE]+)", line.strip())
        if m: res[m.group(1).lower()] = float(m.group(2))
    errs = [l for l in (out.stdout + out.stderr).splitlines() if ("rror" in l or "failed" in l.lower() or "singular" in l.lower())]
    return res, errs

if __name__ == "__main__":
    P = load()
    for r in sorted(P, key=lambda s: (re.sub(r"\d", "", s), int(re.sub(r"\D", "", s) or 0))):
        print(f"{r:5s} {P[r][0]:28s} {P[r][1]}")
