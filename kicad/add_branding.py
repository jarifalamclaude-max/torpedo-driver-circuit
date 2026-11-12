"""Add the BRACU Duburi logo and designer name to the silkscreen of torpedo_driver_v4.kicad_pcb, then re-run DRC
so drc.rpt matches the final board. Blue parts of the logo become silkscreen ink.
Run after route_v4.py, with KiCad 7's python:  python3 add_branding.py"""
import os, pcbnew
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, "torpedo_driver_v4.kicad_pcb")
OX, OY = 100.0, 100.0
mm = pcbnew.FromMM
NAME = "Md. Jarif Alam 13"
FRONT = (8.3, 42.6, 13.4)         # x, y of top-left corner (board mm), width: empty logic-side area
BACK = (1.5, 27.6, 20.0)          # between the ESP32 header rows, as seen from the top; drawn mirrored
NAME_AT = (13.0, 56.0)

def logo_runs(width_mm, px_per_mm):
    im = Image.open(os.path.join(HERE, "duburi_logo.png")).convert("RGB")
    w = int(round(width_mm * px_per_mm)); h = int(round(w * im.height / im.width))
    im = im.resize((w, h), Image.LANCZOS); px = im.load()
    ink = [[(px[x, y][2] - px[x, y][0]) > 60 for x in range(w)] for y in range(h)]
    rects, open_runs = [], {}
    for y in range(h + 1):
        runs = set()
        if y < h:
            x = 0
            while x < w:
                if ink[y][x]:
                    x0 = x
                    while x < w and ink[y][x]: x += 1
                    runs.add((x0, x))
                else: x += 1
        for r in list(open_runs):
            if r not in runs: rects.append((r[0], open_runs.pop(r), r[1], y))
        for r in runs: open_runs.setdefault(r, y)
    return rects, 1.0 / px_per_mm, h / px_per_mm

def add_logo(board, layer, x, y, width, mirror):
    rects, s, height = logo_runs(width, 25)
    ps = pcbnew.SHAPE_POLY_SET()
    for x0, y0, x1, y1 in rects:
        ax, bx = (x + width - x1 * s, x + width - x0 * s) if mirror else (x + x0 * s, x + x1 * s)
        ps.NewOutline()
        for px_, py_ in ((ax, y + y0 * s), (bx, y + y0 * s), (bx, y + y1 * s), (ax, y + y1 * s)):
            ps.Append(mm(OX + px_), mm(OY + py_))
    ps.Simplify(pcbnew.SHAPE_POLY_SET.PM_FAST); ps.Fracture(pcbnew.SHAPE_POLY_SET.PM_FAST)
    for i in range(ps.OutlineCount()):          # a gr_poly holds one outline, so one shape per island
        one = pcbnew.SHAPE_POLY_SET(); one.AddOutline(ps.Outline(i))
        sh = pcbnew.PCB_SHAPE(board); sh.SetShape(pcbnew.SHAPE_T_POLY); sh.SetLayer(layer)
        sh.SetPolyShape(one); sh.SetFilled(True); sh.SetWidth(0); board.Add(sh)
    return height

board = pcbnew.LoadBoard(PCB)
h1 = add_logo(board, pcbnew.F_SilkS, *FRONT, mirror=False)
h2 = add_logo(board, pcbnew.B_SilkS, *BACK, mirror=True)
t = pcbnew.PCB_TEXT(board); t.SetText(NAME); t.SetLayer(pcbnew.F_SilkS)
t.SetPosition(pcbnew.VECTOR2I(mm(OX + NAME_AT[0]), mm(OY + NAME_AT[1])))
t.SetTextSize(pcbnew.VECTOR2I(mm(1.0), mm(1.0))); t.SetTextThickness(mm(0.15)); board.Add(t)
bb = t.GetBoundingBox()
print("name box mm:", [round(pcbnew.ToMM(v) - 100, 2) for v in (bb.GetX(), bb.GetY(), bb.GetX() + bb.GetWidth(), bb.GetY() + bb.GetHeight())])
print("logo heights mm:", round(h1, 2), round(h2, 2))
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(PCB, board)
board = pcbnew.LoadBoard(PCB)
print("DRC written:", pcbnew.WriteDRCReport(board, os.path.join(HERE, "drc.rpt"), pcbnew.EDA_UNITS_MILLIMETRES, True))
