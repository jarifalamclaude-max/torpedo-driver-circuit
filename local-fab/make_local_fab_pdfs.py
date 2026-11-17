"""1:1 print-ready PDFs of every board layer, for a local PCB maker.

Same style as the maker's example files: one layer per page, each side drawn as seen from that side
(bottom layers are mirrored, so their text reads normally), copper black on white with white drill
centre marks, solder mask white openings on black. All pages are the same size (board + MARGIN),
so the pages line up with each other. Print at 100 % ("Actual size"), never "Fit to page".

Rendered from ../gerber, so the artwork is exactly what the Gerbers (JLCPCB) contain.
Needs:  pip install gerbonara cairosvg      Run:  python3 make_local_fab_pdfs.py
"""
import os, warnings
warnings.filterwarnings("ignore", category=SyntaxWarning)   # KiCad drill files put G90 after the header
from collections import Counter
from gerbonara import GerberFile, ExcellonFile
from gerbonara.utils import MM, Tag
import cairosvg

HERE = os.path.dirname(os.path.abspath(__file__))
G = os.path.join(HERE, '..', 'gerber', 'torpedo_driver_v4-')
MARGIN = 2.0       # mm of paper around the board outline
DOT = 0.5          # drill centre mark diameter in mm (smaller if the hole itself is smaller)
LINE = 0.2         # outline / crop mark line width, mm

# board outline from the centre lines of the Edge.Cuts strokes
xs, ys = [], []
for obj in GerberFile.open(G + 'Edge_Cuts.gm1').objects:
    for p in obj.to_primitives(MM):
        xs += [p.x1, p.x2]; ys += [p.y1, p.y2]
X0, X1, Y0, Y1 = min(xs), max(xs), min(ys), max(ys)
W, H = X1 - X0, Y1 - Y0
PW, PH = W + 2 * MARGIN, H + 2 * MARGIN

holes = []   # (x1, y1, x2, y2, diameter, plated): a round hole has x1 == x2 and y1 == y2, a slot does not
for name, plated in (('PTH.drl', True), ('NPTH.drl', False)):
    for obj in ExcellonFile.open(G + name).objects:
        for p in obj.to_primitives(MM):
            if hasattr(p, 'r'):
                holes.append((p.x, p.y, p.x, p.y, round(2 * p.r, 3), plated))
            else:            # routed slot (oval hole)
                holes.append((p.x1, p.y1, p.x2, p.y2, round(p.width, 3), plated))

def view(bottom):
    """Gerber coordinates (mm, y up) -> page coordinates (mm, y down). Bottom side is seen from below."""
    if bottom:
        return f'translate({MARGIN + X1} {MARGIN + Y1}) scale(-1 -1)'
    return f'translate({MARGIN - X0} {MARGIN + Y1}) scale(1 -1)'

def outline(color):
    return (f'<rect x="{X0}" y="{Y0}" width="{W}" height="{H}" fill="none" '
            f'stroke="{color}" stroke-width="{LINE}"/>')

def crop_marks(color, gap=0.6, length=2.0):
    """L-shaped marks just outside the four board corners (cut lines and layer registration)."""
    out = []
    for cx, sx in ((X0, -1), (X1, 1)):
        for cy, sy in ((Y0, -1), (Y1, 1)):
            for (ax, ay, bx, by) in ((cx + sx * gap, cy, cx + sx * (gap + length), cy),
                                     (cx, cy + sy * gap, cx, cy + sy * (gap + length))):
                out.append(f'<line x1="{ax}" y1="{ay}" x2="{bx}" y2="{by}" stroke="{color}" '
                           f'stroke-width="{LINE}" stroke-linecap="square"/>')
    return ''.join(out)

def drill_marks():
    """White centre marks: a dot for a round hole, a short white line along the centre of a slot."""
    return ''.join(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="white" '
                   f'stroke-width="{min(DOT, d)}" stroke-linecap="round"/>'
                   for x1, y1, x2, y2, d, plated in holes if plated)

def page(filename, layer, bottom, kind):
    g = GerberFile.open(G + layer)
    if kind == 'mask':      # like the example: black = mask, white = openings, white outline
        bg, fg, extra = 'black', 'white', outline('white')
    elif kind == 'silk':    # black ink on white paper, with the board outline
        bg, fg, extra = 'white', 'black', outline('black')
    else:                   # copper: black = copper, white drill centre marks, corner marks outside the board
        bg, fg, extra = 'white', 'black', drill_marks() + crop_marks('black')
    art = ''.join(str(t) for t in g.svg_objects(svg_unit=MM, tag=Tag, fg=fg, bg=bg))
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{PW}mm" height="{PH}mm" viewBox="0 0 {PW} {PH}">'
           f'<rect x="0" y="0" width="{PW}" height="{PH}" fill="{bg}"/>'
           f'<g transform="{view(bottom)}">{art}{extra}</g></svg>')
    cairosvg.svg2pdf(bytestring=svg.encode(), write_to=os.path.join(HERE, filename))
    print(f'{filename:28s} {layer:22s} {"seen from bottom (mirrored)" if bottom else "seen from top"}')

if __name__ == '__main__':
    print(f'board {W:.2f} x {H:.2f} mm, page {PW:.2f} x {PH:.2f} mm')
    page('torpedo_top_copper.pdf', 'F_Cu.gtl', False, 'copper')
    page('torpedo_bottom_copper.pdf', 'B_Cu.gbl', True, 'copper')
    page('torpedo_top_mask.pdf', 'F_Mask.gts', False, 'mask')
    page('torpedo_bottom_mask.pdf', 'B_Mask.gbs', True, 'mask')
    page('torpedo_top_silk.pdf', 'F_Silkscreen.gto', False, 'silk')
    page('torpedo_bottom_silk.pdf', 'B_Silkscreen.gbo', True, 'silk')
    kinds = Counter((d, p, (x1, y1) != (x2, y2)) for x1, y1, x2, y2, d, p in holes)
    for (d, p, slot), n in sorted(kinds.items()):
        print(f'  drill {d:5.2f} mm  {"plated" if p else "NOT plated"}  {"slot" if slot else "round"}  x {n}')
