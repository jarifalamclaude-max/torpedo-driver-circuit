# Torpedo Driver v4

Two-channel solenoid driver for a 4S LiPo, controlled by an ESP32-C3 SuperMini.
The logic side (ESP32, `GNDL`) and the battery side (`GNDP`) are galvanically isolated: every signal crosses a 6.2 mm copper-free channel through a PC817 optocoupler, and the voltages are measured on the battery side by an ADS1115 that the ESP32 reads over opto-isolated I²C.

**Not yet built or tested on hardware.** Everything below is checked by DRC and by ngspice simulation only.

| Folder / file | Contents |
|---|---|
| `kicad/` | KiCad 7 PCB (`torpedo_driver_v4.kicad_pcb`), the scripts that build it (`build_v4.py`), route it (`route_v4.py` + `gridroute.py`) and brand it (`add_branding.py`), BOM (`bom_v4.csv`), DRC report (0 violations, 0 unconnected) |
| `kicad/simulation/` | ngspice simulation of the whole board taken from the PCB netlist: `run_all.py` (25 scenarios: normal, low battery, hot-plug, surges, shorts, open coils, wet board, boot), `i2c_timing.py` (opto I²C), `models.lib` (MOSFETs fitted to the datasheets, electromechanical solenoid) |
| `kicad-sim/` | Simulation-ready KiCad schematic for KiCad's built-in simulator |
| `firmware/` | ESP32-C3 Arduino sketch, and a PC test that runs it against a simulated ADS1115 |
| `gerber/` | Gerber and drill files for JLCPCB (2 layers, 100 × 88 mm) |
| `pcb-3d/` | 3D view of the board with the current paths and every part explained (`index.html`; serve the folder over http so the textures load) |
| `veroboard/` | Veroboard wiring plan generated from the PCB netlist, with a slider to spread the parts out, and the schematic (`torpedo_driver_v4_schematic.svg`) |
| `torpedo_driver_v4_*.zip` | The gerbers (ready for JLCPCB), the KiCad project, the simulation schematic and the firmware |

## What changed from v3

1. **Real isolation.** v3 joined the ESP32 ground to the battery minus, so the optos isolated nothing. v4 has two ground planes (`GNDL`, `GNDP`), a copper keep-out between them, and sensing moved to an ADS1115 on the battery side.
2. **Fuse that can break a LiPo short.** A 5 A fast ceramic 5×20 fuse (F2) in series with the RUEF300 PTC, whose interrupt rating is only 40 A.
3. **Q3 gate.** R14 1 kΩ (V<sub>gs</sub> −13.8 V at 16.8 V, −10.8 V at 13.2 V), D6 15 V clamp for surges, C11 100 nF so Q3 cannot turn on when the battery is plugged in.
4. **Opto drive.** 150 Ω LED resistors (11 mA), about 2× margin at the minimum PC817 CTR.
5. **Gate rail.** R9 680 Ω so Q1/Q2 still get 10.9 V at 13.2 V.
6. **Flyback diodes.** UF5408 instead of 1N5819: Schottky leakage made an open coil look connected.
7. **TVS.** P6KE22A instead of P6KE20A (standoff 18.8 V, above a full pack).
8. **Self-test.** R12 68 kΩ and four 200k/20k dividers: the firmware can tell healthy (VSW/VBAT 0.51), one coil open (0.60), fire MOSFET short (0.0002) and arm MOSFET short (1.00), and checks each coil separately.
9. **Firmware.** Fire pulses ended by a hardware timer (hard cap 500 ms), task watchdog, arm window, self-test before every arm, minimum battery voltage from the solenoid simulation.

## MOSFETs at the simulated operating point (16.8 V, 1.11 A per coil)

| Part | V<sub>gs</sub> | Datasheet R<sub>ds(on)</sub> max | Simulated drop | Power |
|---|---|---|---|---|
| Q1, Q2 IRLZ44N | 11.9 V (10.8 V at 13.2 V) | 22 mΩ at 10 V | 23.5 mV | 26 mW |
| Q3 IRF4905 | −13.8 V (−10.8 V at 13.2 V) | 20 mΩ at −10 V | 19.8 mV | 22 mW, 87 mW with both coils |

## Rules for using it

- **4S LiPo only** (no LiHV, no 5S). The firmware refuses to arm above 17.6 V.
- **Never join `GNDL` and `GNDP`.** The logic 5 V (J4 or USB) must not share a ground with the battery. If the Jetson runs from the same battery, feed the ESP32 through an isolated DC-DC.
- Unplug the battery when the AUV is stored.
- **Measure your solenoids** (resistance, inductance, stroke, plunger mass, spring force) and run `kicad/simulation/run_all.py` with your values. The defaults (vmin 14.4 V, 200 ms pulse) come from representative values, not from your coils.
- Run `CAL <volts>` once with a multimeter reading of the battery.

## GPIO map

GPIO1 fires SOL1, GPIO0 fires SOL2, GPIO10 arms, GPIO5 = I²C SCL out, GPIO6 = SDA out, GPIO7 = SDA read-back (all through optocouplers). GPIO8 (on-board LED) is on while armed.

## Rebuilding

With KiCad 7 and its Python (`KICAD7_FOOTPRINT_DIR` set to the KiCad footprint library):

```bash
cd kicad && python3 build_v4.py && python3 route_v4.py && python3 add_branding.py
```

Then `python3 simulation/run_all.py`, `python3 ../veroboard/make_vero_data.py` and `python3 ../pcb-3d/make_3d_data.py` refresh the simulation, the veroboard plan and the 3D view.
