"""Routing for torpedo driver v4.

1. Hand-routes the high-current paths on F.Cu (2 mm, locked): battery in, fuse, VBAT, switched rail VSW,
   solenoid low sides D1N / D2N.
2. Puts a no-copper rule area on the isolation channel.
3. Routes everything else with gridroute.py, a small A* grid router (ground nets are left to the planes).
4. Pours separate ground planes: GNDL under the logic side, GNDP under the power side, both layers.
5. Fills zones, saves, writes drc.rpt.

Run with KiCad 7's python from this folder:  python3 route_v4.py   (needs numpy)
"""
import os, sys
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, "torpedo_driver_v4.kicad_pcb")
OX, OY, W, H = 100.0, 100.0, 100.0, 88.0
BX0, BX1 = 33.9, 40.1          # isolation channel kept free of copper (opto pads sit just outside it)
mm = pcbnew.FromMM
def P(x, y): return pcbnew.VECTOR2I(mm(OX + x), mm(OY + y))

b = pcbnew.LoadBoard(PCB)

def pad_xy(ref, num, i=0):
    ps = [p for p in b.FindFootprintByReference(ref).Pads() if p.GetNumber() == num]
    p = ps[i].GetPosition(); return (pcbnew.ToMM(p.x) - OX, pcbnew.ToMM(p.y) - OY)

def route(net, width, *pts, layer=pcbnew.F_Cu, lock=True):
    n = b.FindNet(net); assert n is not None, net
    pts = [pad_xy(*p) if isinstance(p[0], str) else p for p in pts]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(b); t.SetStart(P(x0, y0)); t.SetEnd(P(x1, y1))
        t.SetWidth(mm(width)); t.SetLayer(layer); t.SetNet(n); t.SetLocked(lock); b.Add(t)

def heavy_routes():
    HW = 2.0
    # battery + -> fuse clips -> PTC -> VBAT
    route("VBAT_IN", HW, ("J1", "2"), ("F2", "1", 0), ("F2", "1", 1))
    route("VFUSE", HW, ("F2", "2", 0), ("F2", "2", 1), ("F1", "1"))
    # VBAT: PTC -> up to y 50 -> east -> up the x = 65.08 trunk to the Q3 source; branches to TVS and bulk cap
    route("VBAT", HW, ("F1", "2"), (47.92, 50.0), (65.08, 50.0), ("Q3", "3"))
    route("VBAT", 1.5, (47.92, 50.0), (44.0, 50.0), ("D4", "1"))
    route("VBAT", HW, (65.08, 46.0), ("C1", "1"))
    # VSW: Q3 drain -> north -> east rail between the channels -> D1/D2 cathodes -> SOL1+/SOL2+
    route("VSW", HW, ("Q3", "2"), (62.54, 18.6), (79.0, 18.6), ("D1", "1"))
    route("VSW", HW, (79.0, 18.6), ("D2", "1"))
    route("VSW", HW, ("D1", "1"), ("J2", "1"))
    route("VSW", HW, ("D2", "1"), (87.0, 21.6), (88.32, 22.92), ("J3", "2"))
    # D1N: Q1 drain -> north -> D1 anode -> SOL1-
    route("D1N", HW, ("Q1", "2"), (66.54, 4.3), ("D1", "2"), (88.5, 4.3), (88.5, 11.92), ("J2", "2"))
    # D2N: Q2 drain -> south -> east -> D2 anode -> SOL2-
    route("D2N", HW, ("Q2", "2"), (70.14, 38.6), (79.0, 38.6), ("D2", "2"), (88.5, 34.3), (88.5, 28.0), ("J3", "1"))

def barrier_keepout():
    z = pcbnew.ZONE(b); z.SetIsRuleArea(True); z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(True)
    z.SetDoNotAllowCopperPour(True); z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
    ls = pcbnew.LSET(); ls.AddLayer(pcbnew.F_Cu); ls.AddLayer(pcbnew.B_Cu); z.SetLayerSet(ls)
    o = z.Outline(); o.NewOutline()
    for x, y in ((BX0, -1.0), (BX1, -1.0), (BX1, H + 1.0), (BX0, H + 1.0)): o.Append(mm(OX + x), mm(OY + y))
    z.SetZoneName("isolation_channel"); b.Add(z)

def autoroute():
    """Route every net except the ground nets (they join through the planes) with gridroute.GridRouter."""
    sys.path.insert(0, HERE)
    from gridroute import GridRouter
    skip = {"GNDL", "GNDP", ""}
    nets = {}
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() in skip: continue
            nets.setdefault(p.GetNetCode(), []).append(pcbnew.ToMM(p.GetPosition().x) + 1j * pcbnew.ToMM(p.GetPosition().y))
    def hpwl(c):
        xs = [z.real for z in nets[c]]; ys = [z.imag for z in nets[c]]; return (max(xs) - min(xs)) + (max(ys) - min(ys))
    order = sorted([c for c in nets if len(nets[c]) > 1], key=hpwl)
    fixed = list(b.GetTracks())
    for attempt in range(8):
        r = GridRouter(b, OX, OY, W, H, keepouts=[(BX0, -1.0, BX1, H + 1.0)])
        failed = []
        for c in order:
            ok, _ = r.route_net(c)
            if not ok: failed.append(c)
        name = lambda c: b.GetNetInfo().GetNetItem(c).GetNetname()
        print(f"attempt {attempt}: failed {[name(c) for c in failed]}")
        if not failed: return
        for t in list(b.GetTracks()):
            if t not in fixed: b.Remove(t)
        order = failed + [c for c in order if c not in failed]
    raise SystemExit("routing failed for " + ", ".join(name(c) for c in failed))

def ground_planes():
    for name, x0, x1 in (("GNDL", 0.3, BX0 - 0.3), ("GNDP", BX1 + 0.3, W - 0.3)):
        for layer in (pcbnew.B_Cu, pcbnew.F_Cu):
            z = pcbnew.ZONE(b); z.SetLayer(layer); z.SetNet(b.FindNet(name))
            o = z.Outline(); o.NewOutline()
            for x, y in ((x0, 0.3), (x1, 0.3), (x1, H - 0.3), (x0, H - 0.3)): o.Append(mm(OX + x), mm(OY + y))
            z.SetLocalClearance(mm(0.4)); z.SetMinThickness(mm(0.3))
            z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL); z.SetThermalReliefGap(mm(0.4)); z.SetThermalReliefSpokeWidth(mm(0.8))
            z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
            z.SetAssignedPriority(1 if layer == pcbnew.B_Cu else 0)
            z.SetZoneName(f"{name}_{'bot' if layer == pcbnew.B_Cu else 'top'}"); b.Add(z)

if __name__ == "__main__":
    for z in [b.GetArea(i) for i in range(b.GetAreaCount())]: b.Remove(z)
    for t in list(b.GetTracks()): b.Remove(t)
    heavy_routes()
    barrier_keepout()
    autoroute()
    ground_planes()
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(PCB, b)
    ok = pcbnew.WriteDRCReport(b, os.path.join(HERE, "drc.rpt"), pcbnew.EDA_UNITS_MILLIMETRES, True)
    print("saved; tracks:", len(list(b.GetTracks())), "zones:", b.GetAreaCount(), "DRC written:", ok)
