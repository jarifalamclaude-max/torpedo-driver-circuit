# Files for a local PCB maker

One PDF per layer, at 1:1 scale. Each page is 104 × 92 mm: the 100 × 88 mm board plus a 2 mm border, so all pages line up.
**Print at 100 % ("Actual size"), never "Fit to page".**

Same style as the maker's example files: top layers are drawn as seen from the top, bottom layers as seen from the bottom (mirrored), so the text on each side reads normally.

| File | Layer | Black / white |
|---|---|---|
| `torpedo_top_copper.pdf` | Top copper | black = copper, white dots = drill centres, corner marks = board corners |
| `torpedo_bottom_copper.pdf` | Bottom copper, mirrored | same as top copper |
| `torpedo_top_mask.pdf` | Top solder mask | black = mask, white = openings over the pads |
| `torpedo_bottom_mask.pdf` | Bottom solder mask, mirrored | same as top mask |
| `torpedo_top_silk.pdf` | Top silkscreen | black = ink |
| `torpedo_bottom_silk.pdf` | Bottom silkscreen, mirrored | black = ink |

**The board needs copper on both sides and plated through-holes (PTH).**
- 118 pads have a track on the top side. These include the ESP32 and ADS1115 sockets, the XT60, the terminal blocks, the fuse clips and C1, which can't be soldered from the top.
- 14 vias join the two sides.
- A single-sided or unplated board will not work.

## Drill sizes

| Drill (mm) | Count | Used by |
|---|---|---|
| 0.4 | 14 | vias |
| 0.6 × 1.7 slot | 2 | XT60 (J1) side pegs |
| 0.8 | 101 | resistors, small capacitors, optocouplers, zeners D5–D7, U8 |
| 0.9 | 4 | LED1, LED2 |
| 1.0 | 28 | ESP32 sockets (U1A, U1B), ADS1115 socket (U9), C1 |
| 1.05 | 4 | fuse clips (F2) |
| 1.1 | 13 | Q1–Q3, D3, F1 |
| 1.2 | 2 | D4 |
| 1.52 | 6 | terminal blocks J2, J3, J4 |
| 1.6 | 4 | D1, D2 |
| 2.7 | 2 | XT60 (J1) main pins |
| 3.2, not plated | 6 | M3 mounting holes |

A maker with a CNC drill can use the Excellon files in `../gerber` instead (`*-PTH.drl`, `*-NPTH.drl`).

## Rebuilding

`python3 make_local_fab_pdfs.py` (needs `pip install gerbonara cairosvg`) renders the Gerbers in `../gerber`, so the PDFs always match them.
