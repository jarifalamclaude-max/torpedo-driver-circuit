"""Hand routing for torpedo driver v3: every signal/power net on F.Cu, solid GND plane on B.Cu.
Idempotent (clears tracks/zones first). Then zone fill, save, DRC report."""
import pcbnew

OUT = "/home/claude/torpedo/pcb3"
PCB = OUT + "/torpedo_driver_v3.kicad_pcb"
b = pcbnew.LoadBoard(PCB)
mm = pcbnew.FromMM
OX, OY, W, H = 100.0, 100.0, 83.0, 52.0
def P(x, y): return pcbnew.VECTOR2I(mm(OX + x), mm(OY + y))
for t in list(b.GetTracks()): b.Remove(t)
for z in [b.GetArea(i) for i in range(b.GetAreaCount())]: b.Remove(z)

def route(net, width, *pts, layer=pcbnew.F_Cu):
    n = b.FindNet(net); assert n is not None, net
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(b); t.SetStart(P(x0, y0)); t.SetEnd(P(x1, y1))
        t.SetWidth(mm(width)); t.SetLayer(layer); t.SetNet(n); b.Add(t)

IN, PW, SW = 2.0, 1.2, 0.5      # battery input / solenoid power / signal widths (mm)
# ---- battery + -> PTC -> bulk cap, TVS, battery-sense divider
route("VBAT_IN", IN, (16.6, 5.65), (18.35, 3.9), (22.4, 3.9))
route("VBAT", IN, (22.4, 8.98), (25.12, 8.98), (27.5, 6.6))
route("VBAT", 1.5, (22.4, 8.98), (22.4, 12.4), (24.6, 14.6))            # TVS cathode
route("VBAT", SW, (24.6, 14.6), (25.0, 15.0), (25.0, 18.3))             # R5 (VBAT divider top)
# ---- +BAT to the high-side switch Q3 (source) and its gate resistor
route("VBAT", 1.5, (27.5, 6.6), (27.5, 1.9), (40.0, 1.9))
route("VBAT", PW, (43.0, 6.2), (43.0, 4.3), (40.6, 1.9), (40.0, 1.9))
route("VBAT", SW, (43.0, 6.2), (41.0, 8.2), (41.0, 11.4))               # R13 (gate-source)
# ---- switched rail VSW: Q3 drain -> top bus -> right edge -> bottom bus
route("VSW", PW, (45.54, 6.2), (45.54, 3.98), (47.62, 1.9))
route("VSW", PW, (47.62, 1.9), (80.2, 1.9), (81.7, 3.4), (81.7, 39.3), (80.2, 40.8), (52.0, 40.8), (52.0, 45.0))
route("VSW", SW, (53.8, 1.9), (53.8, 3.6))                              # R9 (gate supply)
route("VSW", SW, (56.5, 1.9), (56.5, 3.6))                              # R7 (LED1)
route("VSW", PW, (78.8, 1.9), (78.8, 3.4))                              # J2 +
route("VSW", PW, (78.8, 40.8), (78.8, 38.6))                            # J3 +
route("VSW", PW, (72.0, 40.8), (72.0, 40.1))                            # D2 cathode
route("VSW", SW, (56.5, 40.8), (56.5, 38.4))                            # R8 (LED2)
# ---- high-side gate: Q3 gate - R13 - R14 - opto U4
route("G3", SW, (48.08, 6.2), (48.08, 9.86), (48.62, 10.4), (48.62, 14.6))
route("G3D", SW, (41.0, 14.6), (42.4, 16.0), (44.4, 16.0), (44.4, 37.0), (48.62, 37.0))
# ---- 12 V gate rail
route("VG", SW, (53.8, 11.22), (53.8, 14.2), (54.4, 14.8), (54.4, 15.4))
route("VG", SW, (54.4, 15.4), (52.0, 17.8), (51.4, 17.8), (48.62, 17.8))
route("VG", SW, (48.62, 17.8), (46.7, 17.8), (46.7, 27.4), (48.62, 27.4))
# ---- channel 1
route("G1", SW, (48.62, 20.34), (48.62, 23.5), (56.6, 23.5), (59.0, 21.1), (59.0, 15.6))
route("D1N", PW, (61.54, 15.6), (61.54, 12.06), (76.0, 12.06), (76.0, 8.48), (78.8, 8.48))
route("D1N", SW, (68.0, 9.34), (68.0, 12.06))
route("LED1A", SW, (66.66, 3.6), (68.0, 4.94), (68.0, 6.8))
# ---- channel 2
route("G2", SW, (48.62, 29.94), (48.62, 33.1), (52.3, 33.1), (59.0, 26.4))
route("D2N", PW, (61.54, 26.4), (61.54, 29.94), (76.0, 29.94), (76.0, 33.52), (78.8, 33.52))
route("D2N", SW, (68.0, 32.66), (68.0, 29.94))
route("LED2A", SW, (66.66, 38.4), (68.0, 37.06), (68.0, 35.2))
# ---- ESP32-C3 signals
route("VSENSE", SW, (35.16, 18.3), (35.16, 24.7))
route("VSENSE", SW, (12.7, 21.0), (12.7, 17.4), (23.6, 17.4), (23.6, 23.1), (35.16, 23.1))
route("FIRE1", SW, (17.78, 21.0), (17.78, 18.4), (22.6, 18.4), (22.6, 27.9), (25.0, 27.9))
route("FIRE2", SW, (20.32, 21.0), (20.32, 19.4), (21.7, 19.4), (21.7, 31.1), (25.0, 31.1))
route("SWSENSE", SW, (10.16, 21.0), (10.16, 34.3), (25.0, 34.3), (25.0, 37.5))
route("SWSENSE", SW, (41.84, 45.0), (32.0, 45.0), (32.0, 35.9), (25.0, 35.9))
route("ARM", SW, (15.24, 36.24), (15.24, 38.9), (23.2, 38.9), (25.0, 40.7))
route("OL1", SW, (35.16, 27.9), (37.6, 27.9), (37.6, 17.8), (41.0, 17.8))
route("OL2", SW, (35.16, 31.1), (38.6, 31.1), (38.6, 27.4), (41.0, 27.4))
route("OL3", SW, (35.16, 40.7), (37.0, 40.7), (37.0, 37.0), (41.0, 37.0))
# ---- buck 5 V -> D3 -> ESP 5V pin
route("5V_IN", 0.8, (14.0, 47.3), (13.66, 45.0), (13.66, 41.0))
route("+5V", 0.8, (3.5, 41.0), (0.95, 41.0), (0.95, 21.0), (2.54, 21.0))

# ---- GND plane on B.Cu (whole board)
z = pcbnew.ZONE(b); z.SetLayer(pcbnew.B_Cu); z.SetNet(b.FindNet("GND"))
o = z.Outline(); o.NewOutline()
for x, y in ((0.3, 0.3), (W - 0.3, 0.3), (W - 0.3, H - 0.3), (0.3, H - 0.3)): o.Append(mm(OX + x), mm(OY + y))
z.SetLocalClearance(mm(0.5)); z.SetMinThickness(mm(0.3))
z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL); z.SetThermalReliefGap(mm(0.4)); z.SetThermalReliefSpokeWidth(mm(0.8))
z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS); z.SetZoneName("GND_plane")
b.Add(z)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(PCB, b)
ok = pcbnew.WriteDRCReport(b, OUT + "/drc.rpt", pcbnew.EDA_UNITS_MILLIMETRES, True)
print("saved; tracks:", len(list(b.GetTracks())), "zones:", b.GetAreaCount(), "DRC written:", ok)
