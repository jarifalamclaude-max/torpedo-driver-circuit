# Torpedo Driver v3

Two-channel solenoid driver for a 4S LiPo, controlled by an ESP32-C3 SuperMini.
Opto-driven MOSFET gates, a high-side arm switch, and battery / armed-rail sensing.

| Folder | Contents |
|---|---|
| `kicad/` | KiCad PCB, the scripts that build and route it, DRC report, SPICE simulation. `add_branding.py` puts the BRACU Duburi logo and designer name on the silkscreen |
| `kicad-sim/` | Simulation-ready KiCad schematic for the built-in simulator, with instructions |
| `gerber/` | Gerber and drill files for JLCPCB (2-layer). `torpedo_driver_v3_gerber_JLCPCB.zip` in the repo root is the same set, ready to upload |
| `pcb-3d/` | 3D view of the PCB (`index.html`, open in a browser; needs internet for three.js) |
| `veroboard/` | Veroboard wiring layout (`index.html`, open in a browser) and schematic (`torpedo_driver_v3_schematic.svg`) |

GPIO map: GPIO1 fires SOL1, GPIO0 fires SOL2, GPIO10 arms, GPIO3 reads VBAT/11, GPIO4 reads VSW/11.

The veroboard layout has not been built and tested yet. Check the wire list against the schematic before soldering.
