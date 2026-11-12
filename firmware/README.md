# Torpedo driver v4 firmware (ESP32-C3 SuperMini)

`torpedo_driver_v4/torpedo_driver_v4.ino` is an Arduino sketch. It is the part of the safety design that hardware cannot do on its own.

## Build and flash

1. Arduino IDE with the **esp32 by Espressif** boards package (2.x or 3.x).
2. Board: **ESP32C3 Dev Module**. Set **USB CDC On Boot: Enabled**, so the serial commands work over the SuperMini's USB-C.
3. Open the sketch, upload, and open the serial monitor at 115200 baud with line ending "Newline".

The logic side needs 5 V, either from USB-C or from the LOGIC 5V IN terminal. The battery side is separate.

## What it enforces

| Rule | How |
|---|---|
| Fire pulse always ends | A one-shot hardware timer turns FIRE off, never the main loop. The hard cap is 500 ms (`MAX_PULSE_MS`), and serial commands can't raise it |
| A hang can't leave a solenoid on | Task watchdog, 2 s. On a stall the chip panics and reboots, and every output goes low |
| No arming with a fault | The self-test runs before every ARM (table below) |
| Arm window | The board disarms itself after `arm_ms` (default 10 s) |
| Minimum gap between pulses | 300 ms |
| No firing into an open channel | A channel fires only if its solenoid was detected at the last self-test |
| Fire confirmation | During the pulse it reads the low side. If it stays high, it reports that the MOSFET or opto is not switching |
| Armed indicator | The SuperMini's blue LED (GPIO8) is on while armed |

## Self-test (disarmed)

| Reading | Means | Action |
|---|---|---|
| ADS1115 doesn't answer | Logic 5 V, U5–U7 or the module | Can't arm |
| VBAT > 17.6 V | Wrong battery | Can't arm |
| VBAT < vmin (14.4 V default) | Too low for reliable pull-in | Can't arm |
| VSW/VBAT > 0.85 | Q3 or U4 shorted | Can't arm |
| VSW/VBAT < 0.30 | Q1/Q2 shorted, stuck opto, or SOL output shorted | Can't arm |
| D1N/VSW > 0.85 | Solenoid 1 connected | Channel 1 allowed |
| D1N/VSW < 0.20 | Solenoid 1 disconnected | Channel 1 blocked |
| D1N/VSW in between | Leakage or a damaged Q1/D1 | Can't arm |

Simulated values on the v4 board:
- **Healthy, both coils**: VSW/VBAT = 0.51.
- **One coil open**: 0.60, and that coil's D/VSW reads 0.0001 (0.0024 at 70 °C).
- **Low-side short**: 0.0002.
- **High-side short**: 1.0.

## Serial commands

```
STATUS              readings, arm state, settings, last fault
TEST                run the self-test (disarmed)
ARM                 self-test, close the arm switch, check VSW reached VBAT
DISARM
FIRE 1 [ms]         fire channel 1 (default pulse if ms is left out)
FIRE 2 [ms]
CAL 16.42           battery voltage measured with a multimeter; stores a gain correction
SET VMIN 14.4       lowest battery voltage allowed to arm
SET PULSE 200       default pulse, 10..500 ms
SET ARMTIME 10000   arm window, 1000..60000 ms
```

## Calibrate once

With the battery connected and the board disarmed, measure the battery at the XT60 with a multimeter and send `CAL <volts>`. With 1 % divider resistors the correction is under 2 %. The command refuses anything more than 10 % off, because that points to a wrong resistor.

## Choosing vmin and the pulse length

The solenoid's mechanics decide both. Measure it and run the board simulation with your values (see `kicad/simulation/run_all.py --help`). It prints the lowest battery voltage at which the plunger still closes, and how long that takes.

With the representative values used in the repo:
- The plunger closes in 42 ms at 16.8 V and in 76 ms at 14.8 V.
- It doesn't close at all below 13.8 V.

That's why the defaults are vmin 14.4 V and a 200 ms pulse.

## Testing without hardware

`test/run_test.sh` compiles the sketch on a PC with stub Arduino headers. It runs the bit-banged I²C against a behavioural ADS1115 and checks the self-test cases, arming and the firing limits. It needs only `g++`. It has not been run on a real board yet.
