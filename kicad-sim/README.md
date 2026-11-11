# Simulating the torpedo driver in KiCad

`torpedo_driver_v3_sim.kicad_sch` is a simulation-only schematic of the driver. It needs nothing else: the SPICE models are written on the sheet itself.

## Run it

1. Open `torpedo_driver_v3_sim.kicad_pro` in KiCad, then open the schematic.
2. `Inspect > Simulator`.
3. If the simulator asks for an analysis, choose Transient with time step `20u` and final time `400m`. The sheet already carries `.tran 20u 400m`, so it may be picked up automatically.
4. Press Run, then add signals to the plot.

## What to plot

| Signal | What you should see |
|---|---|
| `V(/VSW)` | About 10.4 V disarmed, 16.8 V after ARM at 20 ms, back down after 310 ms |
| `I(L1)` | Solenoid 1 current: 0 until 30 ms, rises to about 1.1 A, falls after 280 ms |
| `V(/D1N)` | Drops near 0 V while firing, small spike to about 17 V at turn-off (flyback diode clamps it) |
| `V(/G1)` | Q1 gate: 0 V, then about 11.9 V while firing |
| `V(/G3)` | Q3 gate: at battery voltage when disarmed, about 5.4 V when armed |
| `V(/SWSENSE)`, `V(/VSENSE)` | What the ESP32 ADC pins see (about 1.5 V) |

## What stands in for the real parts

| In the schematic | Real thing |
|---|---|
| V1, R20, L3 | 4S LiPo, its internal resistance, lead inductance |
| R19 | Fuse F1 |
| L1 + R31, L2 + R32 | Solenoid 1 and 2 (30 mH, 15 ohm assumed; measure yours and change these) |
| V2, V3, V4 with R23, R21, R22 | ESP32 GPIO10 (ARM), GPIO1 (FIRE1), GPIO0 (FIRE2) |
| V5, R41, R40 | Buck converter 5 V, its output resistance, ESP32 load |

To change the timing, edit the `PWL(...)` text in the Sim.Params field of V2 and V3. To fire solenoid 2, give V4 a PWL like V3.

The models are simplified, so use the results for behaviour and rough numbers, not exact values. `make_sim_schematic.py` regenerates the schematic.
