# Simulating the v4 driver in KiCad

`torpedo_driver_v4_sim.kicad_sch` is a simulation-only schematic of the v4 board. It needs nothing else, because the SPICE models are written on the sheet (the column on the right). They are the same models as `../kicad/simulation/models.lib`:
- **MOSFETs**: IRLZ44N and IRF4905 fitted to the IR datasheets. Rds(on) is set to the datasheet maximum, and Crss follows datasheet Fig. 5.
- **PC817**: timing checked against the datasheet test point.
- **Diodes**: UF5408, zeners, P6KE22A.
- **LP2950-3.3** regulator.
- **Solenoid**: an electromechanical plunger model.

The logic side has its own ground net `GNDL`. It reaches `GND` only through R45 (1 GΩ) and C12 (10 pF), which is what the isolation barrier looks like electrically.

## Run it

1. Open `torpedo_driver_v4_sim.kicad_pro` in KiCad 7 or later, then open the schematic.
2. `Inspect > Simulator`.
3. If it asks for an analysis, choose Transient, step `20u`, end `400m` (the sheet already carries `.tran 20u 400m`).
4. Press Run and add signals to the plot.

The netlist this sheet exports has been run through ngspice 42. It gives the same numbers as the board simulation in `../kicad/simulation`.

## What to plot

| Signal | Expected |
|---|---|
| `V(/VSW)` | 8.6 V disarmed (self-test bleed through R12), 16.8 V after ARM at 20 ms, back to 8.6 V after 330 ms |
| `V(/G3)` | Battery voltage when disarmed, about 3.0 V when armed (Vgs −13.8 V; D6 keeps it within −15 V) |
| `V(/G1)` | 0 V, then 11.9 V while firing (30–230 ms) |
| `V(/D1N)` | Equals VSW when idle (solenoid present), 23 mV while firing, 17.7 V flyback peak at turn-off |
| `I(SOL1)` | Rises to 1.11 A. A small dip appears when the plunger moves (back-EMF) |
| `V(xsol1.x)` | Plunger travel: 0 to 8 mm, closed at about 72 ms |
| `V(/SBAT)`, `V(/SSW)`, `V(/SD1)` | ADS1115 inputs, all 1/11 of their node (1.53 V for a full pack) |
| `V(/3V3P)` | 3.3 V, the ADC supply on the battery side |

## What stands in for the real parts

| In the schematic | Real part |
|---|---|
| V1, R30, L3 | 4S LiPo, its internal resistance, lead inductance |
| R31, R32 | F2 (5 A fast fuse), F1 (RUEF300 PTC) |
| R33 | C1 ESR |
| SOL1, SOL2 | Solenoids. Default parameters `R=15 LO=25m LC=75m S=8m M=30m K=200 F0=0.8 C=2` are representative, not measured |
| V2, V3, V4 with R40–R42 | ESP32 GPIO10 (ARM), GPIO1 (FIRE1), GPIO0 (FIRE2), referenced to GNDL |
| V5, D3, R44 | Logic 5 V input and the ESP32 load |
| R46 | ADS1115 module and I²C pull-up load on 3V3P |

## Change the solenoid

Edit the SOL1/SOL2 `Sim.Params`, for example: `model="SOLENOID R=12 LO=22m LC=70m S=6m M=25m K=150 F0=0.6 C=1.5"`. The parameters are:

| Parameter | Meaning | How to measure |
|---|---|---|
| R | Coil resistance | Multimeter |
| LO, LC | Inductance, plunger out / in | LCR meter |
| S | Stroke | Calipers |
| M | Moving mass | Scale |
| K, F0 | Spring rate and preload / latch force | Spring scale at start and end of the stroke |
| C | Damping | Estimate |

To change timing, edit the `PWL(...)` text of V2 and V3. To fire channel 2, give V4 a PWL like V3.

`make_sim_schematic.py` regenerates the sheet (it reads `../kicad/simulation/models.lib`). The opto-isolated I²C link timing is simulated separately in `../kicad/simulation/i2c_timing.py`.
