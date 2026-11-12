"""Torpedo driver v4 (KiCad 7): galvanically isolated logic side, opto-isolated I2C sensing (ADS1115),
high-side arm switch, two low-side fire switches. Places footprints, assigns nets, board outline,
isolation channel, silkscreen and design rules. Routing is done by route_v4.py.

Run with KiCad 7's python from this folder:  python3 build_v4.py
"""
import os
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
FP = "/usr/share/kicad/footprints/"
OUT = HERE
PCB = os.path.join(OUT, "torpedo_driver_v4.kicad_pcb")
OX, OY = 100.0, 100.0          # board origin on the KiCad sheet
W, H = 100.0, 88.0             # board size, mm
BARRIER = (33.6, 40.4)         # isolation channel (x range): no copper of either side inside it
mm = pcbnew.FromMM
def P(x, y): return pcbnew.VECTOR2I(mm(OX + x), mm(OY + y))

board = pcbnew.BOARD()
nets = {}
def net(name):
    if name not in nets:
        n = pcbnew.NETINFO_ITEM(board, name); board.Add(n); nets[name] = n
    return nets[name]

def ptc_footprint():
    """Littelfuse RUEF300 radial PTC: 5.08 mm lead pitch (datasheet 5.05), 0.81 mm leads, 11.4 x 3.0 mm body."""
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

LAB = {}      # ref -> (x, y, angle): explicit reference-text positions
HIDE = {"U1A", "U1B", "H1", "H2", "H3", "H4", "H5", "H6", "J2", "J3", "J4", "U9", "F2"}
LAB.update({"F1": (50.46, 53.6, 0), "U8": (62.3, 65.6, 0), "C8": (55.0, 65.6, 0), "C9": (68.6, 65.6, 0),
            "C11": (41.6, 29.2, 0)})   # C11: left of the part, clear of the via the router puts between its pads
PARTS = []    # (ref, value, footprint) for the BOM

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
    if ref[0] in "RDC" and not ref.startswith("CN") and lib is not None and len(two) == 2 and name.startswith(("R_", "D_", "C_Disc")):
        fp.Reference().SetPosition(pcbnew.VECTOR2I((two[0].x + two[1].x) // 2, (two[0].y + two[1].y) // 2))
        fp.Reference().SetTextAngleDegrees(rot % 180)
    if ref in LAB:
        lx, ly, a = LAB[ref]; fp.Reference().SetPosition(P(lx, ly)); fp.Reference().SetTextAngleDegrees(a)
    if ref in HIDE: fp.Reference().SetVisible(False)
    PARTS.append((ref, value, name))
    return fp

R = ("Resistor_THT", "R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal")
DO35 = ("Diode_THT", "D_DO-35_SOD27_P7.62mm_Horizontal")
DO41 = ("Diode_THT", "D_DO-41_SOD81_P7.62mm_Horizontal")
DO201 = ("Diode_THT", "D_DO-201AD_P12.70mm_Horizontal")
DO15 = ("Diode_THT", "D_DO-15_P10.16mm_Horizontal")
TO220 = ("Package_TO_SOT_THT", "TO-220-3_Vertical")
TO92 = ("Package_TO_SOT_THT", "TO-92_Inline_Wide")
DIP4 = ("Package_DIP", "DIP-4_W7.62mm")
CDISC = ("Capacitor_THT", "C_Disc_D5.0mm_W2.5mm_P5.00mm")
CE5 = ("Capacitor_THT", "CP_Radial_D5.0mm_P2.00mm")
TERM = ("TerminalBlock", "TerminalBlock_bornier-2_P5.08mm")
SOCK8 = ("Connector_PinSocket_2.54mm", "PinSocket_1x08_P2.54mm_Vertical")
SOCK10 = ("Connector_PinSocket_2.54mm", "PinSocket_1x10_P2.54mm_Vertical")
HOLE = ("MountingHole", "MountingHole_3.2mm_M3")
LED = ("LED_THT", "LED_D3.0mm")
OPX = 37.0 - 3.81              # opto pin-1 column: LED pins at x = 33.19 (logic), transistor pins at 40.81 (power)

# ============================ LOGIC SIDE (GNDL) ============================
# ESP32-C3 SuperMini on two 1x8 sockets, USB-C at the left board edge, chip side up
place("U1A", *SOCK8, 2.54, 24.0, 90, "SuperMini 5V..IO0", {"1": "+5V", "2": "GNDL", "3": "3V3L", "7": "FIRE1", "8": "FIRE2"})
place("U1B", *SOCK8, 2.54, 39.24, 90, "SuperMini IO5..IO21", {"1": "SCL_TX", "2": "SDA_TX", "3": "SDA_RX", "6": "ARM"})
place("J4", *TERM, 7.0, 8.5, 0, "LOGIC 5V IN", {"1": "GNDL", "2": "5V_IN"})
place("D3", *DO41, 15.0, 15.5, 180, "1N5819", {"1": "+5V", "2": "5V_IN"})
# opto rows (pin-1 y). Order along the barrier follows the power side: FIRE1, ARM, FIRE2, then the I2C link
YO = {"U2": 9.2, "U4": 21.0, "U3": 34.0, "U5": 58.0, "U6": 66.0, "U7": 76.54}
place("R1", *R, 23.4, YO["U2"], 0, "150", {"1": "FIRE1", "2": "OL1"})
place("R15", *R, 23.4, YO["U4"], 0, "150", {"1": "ARM", "2": "OL3"})
place("R2", *R, 23.4, YO["U3"], 0, "150", {"1": "FIRE2", "2": "OL2"})
place("R16", *R, 23.4, YO["U5"], 0, "220", {"1": "SCL_TX", "2": "OSCL"})
place("R17", *R, 23.4, YO["U6"], 0, "220", {"1": "SDA_TX", "2": "OSDA"})
place("R19", *R, 23.4, 80.0, 0, "6.8k", {"1": "3V3L", "2": "SDA_RX"})

# ============================ ISOLATION BARRIER ============================
# LED side (pins 1, 2) on the logic side, transistor side (pins 3, 4) on the power side.
place("U2", *DIP4, OPX, YO["U2"], 0, "PC817", {"1": "OL1", "2": "GNDL", "3": "G1", "4": "VG"})
place("U4", *DIP4, OPX, YO["U4"], 0, "PC817", {"1": "OL3", "2": "GNDL", "3": "GNDP", "4": "G3D"})
place("U3", *DIP4, OPX, YO["U3"], 0, "PC817", {"1": "OL2", "2": "GNDL", "3": "G2", "4": "VG"})
place("U5", *DIP4, OPX, YO["U5"], 0, "PC817", {"1": "OSCL", "2": "GNDL", "3": "GNDP", "4": "SCL_P"})
place("U6", *DIP4, OPX, YO["U6"], 0, "PC817", {"1": "OSDA", "2": "GNDL", "3": "GNDP", "4": "SDA_P"})
# U7 is turned round: its LED is driven from the power side, its transistor pulls the ESP input low
place("U7", *DIP4, OPX + 7.62, YO["U7"], 180, "PC817", {"1": "U7A", "2": "SDA_P", "3": "GNDL", "4": "SDA_RX"})

# ============================ POWER SIDE (GNDP) ============================
X1, X2 = 44.0, 51.62           # resistor/diode column next to the optos (pad 1, pad 2)
# --- channel 1 (top): 12 V gate rail, Q1 gate network, Q1, D1, J2
place("D5", *DO35, X1, 2.6, 0, "12V zener", {"1": "VG", "2": "GNDP"})
place("C4", *CDISC, X1, 5.4, 0, "100nF", {"1": "VG", "2": "GNDP"})
place("R9", *R, X1, 8.6, 0, "680", {"1": "VG", "2": "VSW"})
place("R3", *R, X1, 12.0, 0, "4.7k", {"1": "G1", "2": "GNDP"})
place("R7", *R, X1, 15.2, 0, "10k", {"1": "G1", "2": "LED1A"})
place("LED1", *LED, 56.54, 15.2, 180, "red 3mm", {"1": "GNDP", "2": "LED1A"})
place("Q1", *TO220, 64.0, 7.5, 0, "IRLZ44N", {"1": "G1", "2": "D1N", "3": "GNDP"})
place("D1", *DO201, 79.0, 17.0, 90, "UF5408", {"1": "VSW", "2": "D1N"})
place("J2", *TERM, 95.5, 17.0, 90, "SOL1", {"1": "VSW", "2": "D1N"})
# --- arm switch Q3 (P-MOSFET, high side) between the channels, its gate network, the self-test bleed
place("R14", *R, X1, 19.6, 0, "1k", {"1": "G3D", "2": "G3"})
place("R13", *R, X1, 22.8, 0, "4.7k", {"1": "VBAT", "2": "G3"})
place("D6", *DO35, X1, 26.0, 0, "15V zener", {"1": "VBAT", "2": "G3"})
place("C11", *CDISC, X1, 29.2, 0, "100nF", {"1": "VBAT", "2": "G3"})   # holds Q3 off when the battery is plugged in
place("Q3", *TO220, 60.0, 22.5, 0, "IRF4905", {"1": "G3", "2": "VSW", "3": "VBAT"})
place("R12", *R, 54.92, 29.0, 0, "68k 1%", {"1": "VBAT", "2": "VSW"})
# --- channel 2: Q2 gate network, Q2, D2, J3
place("R4", *R, X1, 33.2, 0, "4.7k", {"1": "G2", "2": "GNDP"})
place("R8", *R, X1, 36.4, 0, "10k", {"1": "G2", "2": "LED2A"})
place("LED2", *LED, 56.54, 36.4, 180, "red 3mm", {"1": "GNDP", "2": "LED2A"})
place("Q2", *TO220, 67.6, 35.5, 0, "IRLZ44N", {"1": "G2", "2": "D2N", "3": "GNDP"})
place("D2", *DO201, 79.0, 21.6, 270, "UF5408", {"1": "VSW", "2": "D2N"})
place("J3", *TERM, 95.5, 28.0, 90, "SOL2", {"1": "D2N", "2": "VSW"})
# --- battery input on the right edge: XT60 -> F2 5 A fast fuse -> F1 PTC -> VBAT, bulk cap, TVS
place("J1", "Connector_AMASS", "AMASS_XT60PW-M_1x02_P7.20mm_Horizontal", 83.4, 49.0, 270, "XT60PW-M", {"1": "GNDP", "2": "VBAT_IN"})
place("F2", "Fuse", "Fuseholder_Clip-5x20mm_Littelfuse_111_Inline_P20.00x5.00mm_D1.05mm_Horizontal", 78.6, 56.2, 180,
      "5A fast 5x20 ceramic", {"1": "VBAT_IN", "2": "VFUSE"})
place("F1", None, None, 53.0, 56.2, 180, "RUEF300 PTC 3A 30V", {"1": "VFUSE", "2": "VBAT"})
place("C1", "Capacitor_THT", "CP_Radial_D10.0mm_P5.00mm", 70.5, 46.0, 0, "470uF 35V", {"1": "VBAT", "2": "GNDP"})
place("D4", *DO15, X1, 44.6, 0, "P6KE22A", {"1": "VBAT", "2": "GNDP"})
# --- 3.3 V micropower rail for the ADC (pre-regulator R26 + D7 keeps the LDO under 21 V during TVS clamping)
place("R26", *R, X1, 61.0, 0, "1k", {"1": "VBAT", "2": "VPRE"})
place("D7", *DO35, X2, 64.2, 180, "20V zener", {"1": "VPRE", "2": "GNDP"})
place("C8", *CE5, 55.0, 62.0, 0, "10uF 35V", {"1": "VPRE", "2": "GNDP"})
place("U8", *TO92, 59.8, 62.0, 0, "LP2950-3.3", {"1": "3V3P", "2": "GNDP", "3": "VPRE"})
place("C9", *CE5, 68.6, 62.0, 0, "10uF 35V", {"1": "3V3P", "2": "GNDP"})
# --- I2C pull-ups and the SDA read-back LED resistor
place("R20", *R, X1, 67.4, 0, "10k", {"1": "SCL_P", "2": "3V3P"})
place("R21", *R, X1, 70.6, 0, "10k", {"1": "SDA_P", "2": "3V3P"})
place("R18", *R, X2, 76.6, 180, "1k", {"1": "3V3P", "2": "U7A"})
# --- ADS1115 module and the 1 % dividers (each 200k / 20k = 1/11) with 100 nF filters
place("U9", *SOCK10, 52.0, 85.5, 90, "ADS1115 module (GY-ADS1115)",
      {"1": "3V3P", "2": "GNDP", "3": "SCL_P", "4": "SDA_P", "5": "GNDP", "7": "SBAT", "8": "SSW", "9": "SD1", "10": "SD2"})
XR = 77.8
place("R5", *R, XR, 63.0, 0, "200k 1%", {"1": "VBAT", "2": "SBAT"})
place("R6", *R, XR, 66.2, 0, "20k 1%", {"1": "GNDP", "2": "SBAT"})
place("R10", *R, XR, 69.4, 0, "200k 1%", {"1": "VSW", "2": "SSW"})
place("R11", *R, XR, 72.6, 0, "20k 1%", {"1": "GNDP", "2": "SSW"})
place("R22", *R, XR, 75.8, 0, "200k 1%", {"1": "D1N", "2": "SD1"})
place("R23", *R, XR, 79.0, 0, "20k 1%", {"1": "GNDP", "2": "SD1"})
place("R24", *R, XR, 82.2, 0, "200k 1%", {"1": "D2N", "2": "SD2"})
place("R25", *R, XR, 85.4, 0, "20k 1%", {"1": "GNDP", "2": "SD2"})
XC = 87.6
place("C3", *CDISC, XC, 63.0, 0, "100nF", {"1": "SBAT", "2": "GNDP"})
place("C5", *CDISC, XC, 69.4, 0, "100nF", {"1": "SSW", "2": "GNDP"})
place("C6", *CDISC, XC, 75.8, 0, "100nF", {"1": "SD1", "2": "GNDP"})
place("C7", *CDISC, XC, 79.0, 0, "100nF", {"1": "SD2", "2": "GNDP"})

# ============================ MOUNTING ============================
HOLES = {"H1": (22.0, 4.0), "H2": (4.0, 84.0), "H3": (96.0, 4.0), "H4": (96.5, 84.5), "H5": (96.0, 37.5), "H6": (37.0, 84.0)}
for ref, (hx, hy) in HOLES.items():
    place(ref, *HOLE, hx, hy, 0, "M3", {})

def text(t, x, y, size=1.0, rot=0, layer=pcbnew.F_SilkS, bold=False):
    tx = pcbnew.PCB_TEXT(board); tx.SetText(t); tx.SetPosition(P(x, y)); tx.SetLayer(layer)
    tx.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size))); tx.SetTextThickness(mm(size * (0.2 if bold else 0.15)))
    tx.SetTextAngleDegrees(rot)
    if layer == pcbnew.B_SilkS: tx.SetMirrored(True)
    board.Add(tx)
def rect(x0, y0, x1, y1, layer=pcbnew.F_SilkS, w=0.15):
    r = pcbnew.PCB_SHAPE(board); r.SetShape(pcbnew.SHAPE_T_RECT); r.SetLayer(layer)
    r.SetStart(P(x0, y0)); r.SetEnd(P(x1, y1)); r.SetWidth(mm(w)); board.Add(r)
def line(x0, y0, x1, y1, layer=pcbnew.F_SilkS, w=0.15):
    s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetLayer(layer)
    s.SetStart(P(x0, y0)); s.SetEnd(P(x1, y1)); s.SetWidth(mm(w)); board.Add(s)

def silkscreen():
    # ESP32-C3 SuperMini outline and header labels
    rect(0.15, 22.3, 22.3, 40.9)
    text("ESP32-C3 SuperMini", 11.4, 30.6, 1.0, bold=True); text("chip side up", 11.4, 32.3, 0.8); text("USB-C", 1.3, 31.5, 0.9, rot=90)
    for i, lab in enumerate(["5V", "G", "3V3", "4", "3", "2", "1", "0"]):
        text(lab, 2.54 + 2.54 * i, 26.2, 0.8)
    for i, lab in enumerate(["5", "6", "7", "8", "9", "10", "20", "21"]):
        text(lab, 2.54 + 2.54 * i, 37.1, 0.8)
    text("S1", 17.78, 27.6, 0.8); text("S2", 20.32, 27.6, 0.8)
    text("SCL", 2.9, 35.6, 0.8); text("SDA", 6.4, 34.3, 0.8); text("RD", 8.9, 35.6, 0.8); text("ARM", 15.24, 35.6, 0.8)
    # logic 5 V input
    text("LOGIC 5V IN", 9.5, 3.0, 0.9, bold=True); text("GND", 7.0, 13.2, 0.8); text("+5V", 12.1, 13.2, 0.8)
    # title block on the empty logic area (logo and name are added by add_branding.py above it)
    text("TORPEDO DRIVER v4", 15.0, 50.2, 1.2, bold=True)
    text("isolated logic / power", 15.0, 52.0, 0.9)
    text("LOGIC SIDE: GNDL", 15.0, 54.0, 0.9, bold=True)
    text("POWER SIDE: GNDP", 55.5, 48.0, 0.9, bold=True)
    # isolation channel: label and dashed edges only where no opto body sits
    text("ISOLATION", 37.0, 46.0, 1.0, rot=90, bold=True)
    for y0, y1 in ((0.6, 7.4), (13.5, 19.2), (25.3, 32.2), (38.3, 41.0), (51.0, 56.2), (62.3, 64.2), (70.3, 72.2), (78.3, 81.8)):
        for x in (35.2, 38.8):
            yy = y0
            while yy < y1:
                line(x, yy, x, min(yy + 0.8, y1)); yy += 1.6
    # power connectors and fuse
    text("4S LiPo ONLY", 97.6, 71.0, 0.9, rot=90, bold=True); text("no LiHV, no 5S", 95.9, 71.0, 0.8, rot=90)
    text("SOL1", 91.0, 8.0, 0.9, bold=True); text("-", 90.3, 11.92, 1.2, bold=True); text("+", 90.3, 17.0, 1.2, bold=True)
    text("SOL2", 91.0, 32.4, 0.9, bold=True); text("+", 90.3, 22.92, 1.2, bold=True); text("-", 90.3, 28.0, 1.2, bold=True)
    text("F2 5A FAST", 68.6, 52.3, 0.8, bold=True)
    text("FIRE1", 60.5, 14.0, 0.8); text("ARM", 55.8, 22.6, 0.8); text("FIRE2", 60.0, 40.2, 0.8)
    # ADS1115 module footprint (it sits above the low parts on its socket)
    text("ADS1115 module", 63.4, 70.6, 0.9, bold=True); text("sits above on its socket", 63.4, 72.2, 0.8)
    rect(49.5, 68.5, 78.0, 87.6, layer=pcbnew.F_Fab, w=0.1)
    for i, lab in enumerate(["VDD", "GND", "SCL", "SDA", "ADR", "ALR", "A0", "A1", "A2", "A3"]):
        text(lab, 52.0 + 2.54 * i, 83.0, 0.8)
    # back side, on the empty logic area: GPIO map and the isolation rule
    text("GNDL and GNDP must stay separate", 16.0, 50.5, 0.8, layer=pcbnew.B_SilkS, bold=True)
    text("GPIO1>SOL1  GPIO0>SOL2  GPIO10=ARM", 16.0, 52.5, 0.8, layer=pcbnew.B_SilkS)
    text("GPIO5=SCL  GPIO6=SDA out  GPIO7=SDA in", 16.0, 54.2, 0.8, layer=pcbnew.B_SilkS)
    text("Torpedo driver v4", 16.0, 56.0, 0.8, layer=pcbnew.B_SilkS)

def rules():
    ds = board.GetDesignSettings()
    ds.m_MinClearance = mm(0.2); ds.m_TrackMinWidth = mm(0.25); ds.m_ViasMinSize = mm(0.6)
    ds.m_MinThroughDrill = mm(0.3); ds.m_CopperEdgeClearance = mm(0.4); ds.m_HoleClearance = mm(0.25)
    nc = ds.m_NetSettings.m_DefaultNetClass
    nc.SetClearance(mm(0.25)); nc.SetTrackWidth(mm(0.35)); nc.SetViaDiameter(mm(0.8)); nc.SetViaDrill(mm(0.4))

if __name__ == "__main__":
    s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_RECT); s.SetLayer(pcbnew.Edge_Cuts)
    s.SetStart(P(0, 0)); s.SetEnd(P(W, H)); s.SetWidth(mm(0.1)); board.Add(s)
    silkscreen(); rules()
    os.makedirs(os.path.join(OUT, "torpedo.pretty"), exist_ok=True)
    pcbnew.FootprintSave(os.path.join(OUT, "torpedo.pretty"), ptc_footprint())
    open(os.path.join(OUT, "fp-lib-table"), "w").write('(fp_lib_table\n  (lib (name "torpedo")(type "KiCad")(uri "${KIPRJMOD}/torpedo.pretty")(options "")(descr "project footprints"))\n)\n')
    board.SetFileName(PCB)
    pcbnew.SaveBoard(PCB, board)
    with open(os.path.join(OUT, "bom_v4.csv"), "w") as f:
        f.write("ref,value,footprint\n")
        for ref, val, name in sorted(PARTS, key=lambda r: (r[0].rstrip("0123456789AB"), int("".join(c for c in r[0] if c.isdigit()) or 0), r[0])):
            if not ref.startswith("H"): f.write(f'{ref},"{val}",{name}\n')
    print("saved", len(list(board.GetFootprints())), "footprints,", len(nets), "nets")
