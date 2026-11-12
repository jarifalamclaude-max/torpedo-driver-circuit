"""Make the 3D view's data from the v4 PCB: the board textures tex_top.jpg / tex_bot.jpg, and the part list
(reference, value, footprint, position, pads) that index.html draws the parts from.

The textures use the same gerber-viewer style as before:
green solder mask, lighter green over copper, silver pads, white silkscreen, black drill holes.
Both textures are drawn as seen from the top (the back silkscreen therefore reads mirrored), which is what
index.html expects. Each layer is exported as a black-and-white SVG with kicad-cli, rasterised with
rsvg-convert, cropped to the board outline and composited with PIL. Drill holes come from the pad data.

Run with KiCad 7's python:  python3 make_3d_data.py   (rewrites both textures and the PARTS line in index.html)
"""
import json, os, re, subprocess, tempfile
import numpy as np
from PIL import Image, ImageDraw
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, "..", "kicad", "torpedo_driver_v4.kicad_pcb")
HTML = os.path.join(HERE, "index.html")
W, H, PX = 100.0, 88.0, 27.5                   # board size (mm), pixels per mm
OX = OY = 100.0
MASK, MASK_CU, SILK, PAD, FR4, HOLE = (29, 91, 50), (40, 112, 62), (236, 238, 238), (214, 216, 218), (196, 170, 110), (13, 13, 13)

def render(layer, tmp):
    svg, png = os.path.join(tmp, layer + ".svg"), os.path.join(tmp, layer + ".png")
    subprocess.run(["kicad-cli", "pcb", "export", "svg", "--layers", layer, "--black-and-white", "--exclude-drawing-sheet",
                    "--page-size-mode", "2", "--drill-shape-opt", "0", "-o", svg, PCB], check=True, capture_output=True)
    head = open(svg).read(1000)
    wmm = float(head.split('width="')[1].split("mm")[0])
    subprocess.run(["rsvg-convert", "-w", str(int(round(wmm * PX))), "-b", "white", svg, "-o", png], check=True)
    return np.asarray(Image.open(png).convert("L")) < 128                 # True where the layer has ink

def main():
    with tempfile.TemporaryDirectory() as tmp:
        edge = render("Edge.Cuts", tmp)
        ys, xs = np.nonzero(edge)
        x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()          # outer edge of the outline line
        lw = max(1, int(round(0.1 * PX)))
        box = (x0 + lw // 2, y0 + lw // 2, x1 - lw // 2, y1 - lw // 2)
        size = (int(round(W * PX)), int(round(H * PX)))
        def crop(a): return np.asarray(Image.fromarray(a.astype(np.uint8) * 255).crop(box).resize(size, Image.NEAREST)) > 127
        b = pcbnew.LoadBoard(PCB)
        holes = []
        for fp in b.GetFootprints():
            for p in fp.Pads():
                d = p.GetDrillSize()
                if d.x > 0: holes.append((pcbnew.ToMM(p.GetPosition().x) - OX, pcbnew.ToMM(p.GetPosition().y) - OY, pcbnew.ToMM(d.x) / 2, pcbnew.ToMM(d.y) / 2))
        for t in b.GetTracks():
            if t.GetClass() == "PCB_VIA":
                r = pcbnew.ToMM(t.GetDrillValue()) / 2
                holes.append((pcbnew.ToMM(t.GetPosition().x) - OX, pcbnew.ToMM(t.GetPosition().y) - OY, r, r))
        for side, (cu, mk, sk) in (("top", ("F.Cu", "F.Mask", "F.Silkscreen")), ("bot", ("B.Cu", "B.Mask", "B.Silkscreen"))):
            copper, opening, silk = crop(render(cu, tmp)), crop(render(mk, tmp)), crop(render(sk, tmp))
            img = np.zeros(copper.shape + (3,), dtype=np.uint8); img[:] = MASK
            img[copper] = MASK_CU
            img[opening & copper] = PAD; img[opening & ~copper] = FR4
            img[silk & ~opening] = SILK
            im = Image.fromarray(img); dr = ImageDraw.Draw(im)
            for x, y, rx, ry in holes:
                dr.ellipse([(x - rx) * PX, (y - ry) * PX, (x + rx) * PX, (y + ry) * PX], fill=HOLE)
            im.save(os.path.join(HERE, f"tex_{side}.jpg"), quality=90)
            print(f"tex_{side}.jpg", im.size)

def parts():
    """One entry per footprint: ref, value, footprint name, position, rotation and pads [number, x, y, drill]."""
    b = pcbnew.LoadBoard(PCB); out = []
    for fp in sorted(b.GetFootprints(), key=lambda f: f.GetReference()):
        pads = []
        for p in fp.Pads():
            q = p.GetPosition()
            pads.append([p.GetNumber(), round(pcbnew.ToMM(q.x) - OX, 3), round(pcbnew.ToMM(q.y) - OY, 3), round(pcbnew.ToMM(p.GetDrillSize().x), 2)])
        pos = fp.GetPosition()
        out.append({"ref": fp.GetReference(), "val": fp.GetValue(), "fp": fp.GetFPID().GetLibItemName().wx_str(),
                    "x": round(pcbnew.ToMM(pos.x) - OX, 3), "y": round(pcbnew.ToMM(pos.y) - OY, 3),
                    "rot": round(fp.GetOrientationDegrees(), 1), "pads": pads})
    return out

def write_parts():
    t = open(HTML).read()
    line = "const PARTS = " + json.dumps(parts(), ensure_ascii=False) + ";"
    t, n = re.subn(r"^const PARTS = .*;$", lambda m: line, t, count=1, flags=re.M)
    if n != 1: raise SystemExit("PARTS line not found in index.html")
    t, n = re.subn(r"^const BW = [0-9.]+, BH = [0-9.]+,", f"const BW = {W:g}, BH = {H:g},", t, count=1, flags=re.M)
    if n != 1: raise SystemExit("BW/BH line not found in index.html")
    open(HTML, "w").write(t)
    print("PARTS written to index.html")

if __name__ == "__main__":
    main()
    write_parts()
