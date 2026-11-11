"""Torpedo driver v3 (KiCad 7): opto-isolated gates, high-side arm switch, self-test sensing.
Places footprints, assigns nets, outline, silkscreen. Routing in route_v3.py."""
import pcbnew, os

FP = "/usr/share/kicad/footprints/"
OUT = "/home/claude/torpedo/pcb3"
OX, OY = 100.0, 100.0
W, H = 83.0, 52.0
mm = pcbnew.FromMM
def P(x, y): return pcbnew.VECTOR2I(mm(OX + x), mm(OY + y))

board = pcbnew.BOARD()
nets = {}
def net(name):
    if name not in nets:
        n = pcbnew.NETINFO_ITEM(board, name); board.Add(n); nets[name] = n
    return nets[name]

def ptc_footprint():
    fp = pcbnew.FOOTPRINT(board)
    fp.SetFPID(pcbnew.LIB_ID("torpedo", "PTC_Radial_P5.08mm_W11.5mm"))
    for i, x in enumerate((0.0, 5.08)):
        p = pcbnew.PAD(fp); p.SetNumber(str(i + 1)); p.SetAttribute(pcbnew.PAD_ATTRIB_PTH)
        p.SetShape(pcbnew.PAD_SHAPE_RECT if i == 0 else pcbnew.PAD_SHAPE_CIRCLE)
        p.SetSize(pcbnew.VECTOR2I(mm(2.0), mm(2.0))); p.SetDrillSize(pcbnew.VECTOR2I(mm(1.1), mm(1.1)))
        p.SetLayerSet(pcbnew.PAD.PTHMask()); p.SetPos0(pcbnew.VECTOR2I(mm(x), 0)); p.SetPosition(pcbnew.VECTOR2I(mm(x), 0)); fp.Add(p)
    for layer, (x0, y0, x1, y1) in ((pcbnew.F_SilkS, (-3.2, -1.7, 8.28, 1.7)), (pcbnew.F_CrtYd, (-3.45, -1.95, 8.53, 1.95))):
        s = pcbnew.FP_SHAPE(fp); s.SetShape(pcbnew.SHAPE_T_RECT); s.SetLayer(layer)
        s.SetStart0(pcbnew.VECTOR2I(mm(x0), mm(y0))); s.SetEnd0(pcbnew.VECTOR2I(mm(x1), mm(y1)))
        s.SetWidth(mm(0.12 if layer == pcbnew.F_SilkS else 0.05)); fp.Add(s)
    return fp

LAB = {}      # ref -> (x, y, angle) explicit reference-text positions
HIDE = {"U1A", "U1B", "H1", "H2", "H3", "H4", "J2", "J3", "J4"}
def place(ref, lib, name, x, y, rot, value, padnets):
    fp = ptc_footprint() if lib is None else pcbnew.FootprintLoad(FP + lib + ".pretty", name)
    if lib is not None: fp.SetFPID(pcbnew.LIB_ID(lib, name))
    fp.SetReference(ref); fp.SetValue(value)
    board.Add(fp)
    fp.SetPosition(P(x, y)); fp.SetOrientationDegrees(rot)
    for pad in fp.Pads():
        n = padnets.get(pad.GetNumber())
        if n: pad.SetNet(net(n))
    fp.Reference().SetTextSize(pcbnew.VECTOR2I(mm(0.9), mm(0.9))); fp.Reference().SetTextThickness(mm(0.14))
    fp.Value().SetVisible(False)
    two = [p.GetPosition() for p in fp.Pads() if p.GetNumber() in ("1", "2")]
    if ref[0] in "RD" and lib is not None and len(two) == 2:      # reference inside the body
        fp.Reference().SetPosition(pcbnew.VECTOR2I((two[0].x + two[1].x)//2, (two[0].y + two[1].y)//2))
        fp.Reference().SetTextAngleDegrees(rot % 180)
    if ref in LAB:
        lx, ly, a = LAB[ref]; fp.Reference().SetPosition(P(lx, ly)); fp.Reference().SetTextAngleDegrees(a)
    if ref in HIDE: fp.Reference().SetVisible(False)
    return fp

R10P = ("Resistor_THT", "R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal")
R7P = ("Resistor_THT", "R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal")
DO41 = ("Diode_THT", "D_DO-41_SOD81_P10.16mm_Horizontal")
TO220 = ("Package_TO_SOT_THT", "TO-220-3_Vertical")
DIP4 = ("Package_DIP", "DIP-4_W7.62mm")
CDISC = ("Capacitor_THT", "C_Disc_D5.0mm_W2.5mm_P5.00mm")
TERM = ("TerminalBlock", "TerminalBlock_bornier-2_P5.08mm")
SOCK = ("Connector_PinSocket_2.54mm", "PinSocket_1x08_P2.54mm_Vertical")
HOLE = ("MountingHole", "MountingHole_3.2mm_M3")
LAB.update({"F1": (22.4, 6.44, 90), "C1": (27.9, 3.7, 0), "J1": (8.0, 9.2, 0), "Q3": (38.9, 6.4, 90),
            "Q1": (61.6, 18.3, 0), "Q2": (61.6, 29.0, 0), "LED1": (63.4, 8.1, 0), "LED2": (63.4, 33.9, 0),
            "C3": (32.66, 24.7, 0), "C5": (27.5, 37.5, 0), "C4": (54.4, 22.3, 0),
            "U2": (44.8, 20.0, 0), "U3": (44.8, 29.6, 0), "U4": (44.8, 39.2, 0)})

# ---------------- power entry
place("J1", "Connector_AMASS", "AMASS_XT60PW-M_1x02_P7.20mm_Horizontal", 16.6, 12.85, 90, "XT60PW-M", {"1": "GND", "2": "VBAT_IN"})
place("F1", None, None, 22.4, 3.9, 270, "RUEF300 PTC 3A 30V", {"1": "VBAT_IN", "2": "VBAT"})
place("C1", "Capacitor_THT", "CP_Radial_D10.0mm_P5.00mm", 27.5, 6.6, 0, "470uF 35V", {"1": "VBAT", "2": "GND"})
place("D4", "Diode_THT", "D_DO-15_P10.16mm_Horizontal", 24.6, 14.6, 0, "P6KE20A TVS", {"1": "VBAT", "2": "GND"})
# ---------------- logic column (ESP side), pad1 at x = 25.0
X = 25.0
place("R5", *R10P, X, 18.3, 0, "22k", {"1": "VBAT", "2": "VSENSE"})
place("R6", *R10P, X, 21.5, 0, "2.2k", {"1": "GND", "2": "VSENSE"})
place("C3", *CDISC, 35.16, 24.7, 180, "100nF", {"1": "VSENSE", "2": "GND"})
place("R1", *R10P, X, 27.9, 0, "220", {"1": "FIRE1", "2": "OL1"})
place("R2", *R10P, X, 31.1, 0, "220", {"1": "FIRE2", "2": "OL2"})
place("R11", *R10P, X, 34.3, 0, "2.2k", {"1": "SWSENSE", "2": "GND"})
place("C5", *CDISC, X, 37.5, 0, "100nF", {"1": "SWSENSE", "2": "GND"})
place("R15", *R10P, X, 40.7, 0, "220", {"1": "ARM", "2": "OL3"})
# ---------------- high-side arm switch (P-MOSFET) + test pull-up
place("R12", *R7P, 40.0, 1.9, 0, "15k", {"1": "VBAT", "2": "VSW"})
place("Q3", *TO220, 48.08, 6.2, 180, "IRF4905", {"1": "G3", "2": "VSW", "3": "VBAT"})
place("R13", *R7P, 41.0, 11.4, 0, "4.7k", {"1": "VBAT", "2": "G3"})
place("R14", *R7P, 48.62, 14.6, 180, "2.2k", {"1": "G3", "2": "G3D"})
# ---------------- optocoupler column (LED pins 1/2 at x = 41.0, transistor pins 3/4 at x = 48.62)
place("U2", *DIP4, 41.0, 17.8, 0, "PC817", {"1": "OL1", "2": "GND", "3": "G1", "4": "VG"})
place("R3", *R7P, 48.62, 23.5, 180, "4.7k", {"1": "G1", "2": "GND"})
place("U3", *DIP4, 41.0, 27.4, 0, "PC817", {"1": "OL2", "2": "GND", "3": "G2", "4": "VG"})
place("R4", *R7P, 48.62, 33.1, 180, "4.7k", {"1": "G2", "2": "GND"})
place("U4", *DIP4, 41.0, 37.0, 0, "PC817", {"1": "OL3", "2": "GND", "3": "GND", "4": "G3D"})
# ---------------- 12 V gate supply (from the switched rail)
place("R9", *R7P, 53.8, 3.6, 270, "1k", {"1": "VSW", "2": "VG"})
place("D5", "Diode_THT", "D_DO-35_SOD27_P7.62mm_Horizontal", 51.4, 17.8, 270, "12V zener", {"1": "VG", "2": "GND"})
place("C4", *CDISC, 54.4, 15.4, 270, "100nF", {"1": "VG", "2": "GND"})
for g in [f for f in board.GetFootprints() if f.GetReference() == "D5"][0].GraphicalItems():
    if isinstance(g, pcbnew.FP_TEXT) and g.GetText() == "K":
        g.SetPosition(P(51.4, 16.2)); g.SetLocalCoord()
# ---------------- channel 1 / channel 2
place("Q1", *TO220, 59.0, 15.6, 0, "IRLZ44N", {"1": "G1", "2": "D1N", "3": "GND"})
place("Q2", *TO220, 59.0, 26.4, 0, "IRLZ44N", {"1": "G2", "2": "D2N", "3": "GND"})
place("R7", *R10P, 56.5, 3.6, 0, "3.3k", {"1": "VSW", "2": "LED1A"})
place("LED1", "LED_THT", "LED_D3.0mm", 68.0, 9.34, 90, "red 3mm", {"1": "D1N", "2": "LED1A"})
place("R8", *R10P, 56.5, 38.4, 0, "3.3k", {"1": "VSW", "2": "LED2A"})
place("LED2", "LED_THT", "LED_D3.0mm", 68.0, 32.66, 270, "red 3mm", {"1": "D2N", "2": "LED2A"})
place("D1", *DO41, 72.0, 1.9, 270, "1N5819", {"1": "VSW", "2": "D1N"})
place("D2", *DO41, 72.0, 40.1, 90, "1N5819", {"1": "VSW", "2": "D2N"})
place("J2", *TERM, 78.8, 8.48, 90, "SOL1", {"1": "D1N", "2": "VSW"})     # wire entry faces the board edge
place("J3", *TERM, 78.8, 38.6, 90, "SOL2", {"1": "VSW", "2": "D2N"})
place("R10", *R10P, 52.0, 45.0, 180, "22k", {"1": "VSW", "2": "SWSENSE"})
# ---------------- ESP32-C3 SuperMini (two 1x8 sockets, USB-C toward the left edge) + buck 5 V input
place("U1A", *SOCK, 2.54, 21.0, 90, "SuperMini 5V..IO0",
      {"1": "+5V", "2": "GND", "4": "SWSENSE", "5": "VSENSE", "7": "FIRE1", "8": "FIRE2"})
place("U1B", *SOCK, 2.54, 36.24, 90, "SuperMini IO5..IO21", {"6": "ARM"})
place("D3", *DO41, 3.5, 41.0, 0, "1N5819", {"1": "+5V", "2": "5V_IN"})
place("J4", *TERM, 8.92, 47.3, 0, "5V IN", {"1": "GND", "2": "5V_IN"})        # wire entry faces the board edge
# ---------------- mounting holes
for ref, (hx, hy) in {"H1": (77.5, 21.0), "H2": (22.5, 47.5), "H3": (78.5, 47.5), "H4": (63.0, 47.5)}.items():
    place(ref, *HOLE, hx, hy, 0, "M3", {})

# ---------------- outline
s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_RECT); s.SetLayer(pcbnew.Edge_Cuts)
s.SetStart(P(0, 0)); s.SetEnd(P(W, H)); s.SetWidth(mm(0.1)); board.Add(s)

def text(t, x, y, size=1.0, rot=0, layer=pcbnew.F_SilkS, bold=False):
    tx = pcbnew.PCB_TEXT(board); tx.SetText(t); tx.SetPosition(P(x, y)); tx.SetLayer(layer)
    tx.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size))); tx.SetTextThickness(mm(size * (0.2 if bold else 0.15)))
    tx.SetTextAngleDegrees(rot)
    if layer == pcbnew.B_SilkS: tx.SetMirrored(True)
    board.Add(tx)
def rect(x0, y0, x1, y1, layer=pcbnew.F_SilkS, w=0.15):
    r = pcbnew.PCB_SHAPE(board); r.SetShape(pcbnew.SHAPE_T_RECT); r.SetLayer(layer)
    r.SetStart(P(x0, y0)); r.SetEnd(P(x1, y1)); r.SetWidth(mm(w)); board.Add(r)

rect(0.15, 19.3, 22.6, 37.9)
text("ESP32-C3 SuperMini", 11.6, 27.4, 1.0, bold=True)
text("chip side up", 11.6, 29.0, 0.8)
text("USB-C", 1.3, 28.6, 0.9, rot=90)
for i, lab in enumerate(["5V", "G", "3V3", "4", "3", "2", "1", "0"]):
    text(lab, 2.54 + 2.54 * i, 23.2, 0.8)
text("SW", 10.16, 24.5, 0.8); text("VB", 12.7, 24.5, 0.8); text("S1", 17.78, 24.5, 0.8); text("S2", 20.32, 24.5, 0.8)
for i, lab in enumerate(["5", "6", "7", "8", "9", "10", "20", "21"]):
    text(lab, 2.54 + 2.54 * i, 33.9, 0.8)
text("ARM", 15.24, 32.6, 0.8)
text("+", 74.25, 3.4, 1.0, bold=True); text("-", 74.25, 8.5, 1.0, bold=True)
text("-", 74.25, 33.5, 1.0, bold=True); text("+", 74.25, 38.6, 1.0, bold=True)
text("SOL1", 78.8, 13.0, 1.0, bold=True); text("SOL2", 78.8, 29.0, 1.0, bold=True)
text("4S LiPo", 8.0, 18.2, 1.0, bold=True)
text("TORPEDO DRIVER v3", 68.3, 19.6, 0.9, bold=True)
text("opto + arm switch", 68.3, 21.2, 0.8)
text("CH1", 44.8, 18.4, 0.8); text("CH2", 44.8, 28.0, 0.8); text("ARM", 44.8, 37.6, 0.8)
text("BUCK 5V IN", 20.7, 43.7, 0.8, bold=True); text("+5V", 18.4, 47.3, 0.8, bold=True); text("GND", 4.6, 47.3, 0.8, bold=True)
text("GPIO1>SOL1  GPIO0>SOL2  GPIO10=ARM  GPIO3=VBAT/11  GPIO4=VSW/11", 43.0, 50.6, 0.8, layer=pcbnew.B_SilkS)
text("Torpedo driver v3", 62.0, 43.6, 0.9, layer=pcbnew.B_SilkS)

ds = board.GetDesignSettings()
ds.m_MinClearance = mm(0.2); ds.m_TrackMinWidth = mm(0.25); ds.m_ViasMinSize = mm(0.6)
ds.m_MinThroughDrill = mm(0.3); ds.m_CopperEdgeClearance = mm(0.4); ds.m_HoleClearance = mm(0.25)
nc = ds.m_NetSettings.m_DefaultNetClass
nc.SetClearance(mm(0.25)); nc.SetTrackWidth(mm(0.4)); nc.SetViaDiameter(mm(0.9)); nc.SetViaDrill(mm(0.45))

os.makedirs(OUT + "/torpedo.pretty", exist_ok=True)
pcbnew.FootprintSave(OUT + "/torpedo.pretty", ptc_footprint())
open(OUT + "/fp-lib-table", "w").write('(fp_lib_table\n  (lib (name "torpedo")(type "KiCad")(uri "${KIPRJMOD}/torpedo.pretty")(options "")(descr "project footprints"))\n)\n')
board.SetFileName(OUT + "/torpedo_driver_v3.kicad_pcb")
pcbnew.SaveBoard(OUT + "/torpedo_driver_v3.kicad_pcb", board)
print("saved", len(list(board.GetFootprints())), "footprints,", len(nets), "nets")
