"""Opto-isolated I2C link timing (U5 SCL, U6 SDA out, U7 SDA read-back) across PC817 corners.

The ESP32 bit-bangs I2C through optocouplers. Output pins drive the opto LEDs (high = line pulled LOW on the
power side); GPIO7 reads the SDA line back through U7 (low = SDA low). PC817s are slow, so the firmware's
half-bit time must be longer than the worst edge delay found here.

Writes the worst delays to results_i2c.json and prints a table. Run:  python3 i2c_timing.py
"""
import json, os, re, subprocess, itertools
HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.join(HERE, "models.lib")

def netlist(ctr, cjc, r18=1.0e3, r19=6.8e3, rpu_module=10e3):
    return f"""* opto I2C timing, CTR={ctr} CJC={cjc}
.include {MODELS}
Riso gndl 0 1G
* power side: 3.3 V rail, pull-ups R20/R21 (10k) and the module's own 10k
V3p v3p 0 3.3
R20 scl_p v3p 10k
R21 sda_p v3p 10k
Rm1 scl_p v3p {rpu_module:g}
Rm2 sda_p v3p {rpu_module:g}
Cscl scl_p 0 30p
Csda sda_p 0 30p
* ADS1115 SDA open drain: pulls low 1.0 .. 1.5 ms (like an ACK / data 0)
Sads sda_p 0 ackc 0 SWADS
.model SWADS SW(Ron=100 Roff=100meg Vt=0.5 Vh=0.1)
Vack ackc 0 PWL(0 0 1.0m 0 1.0001m 1 1.5m 1 1.5001m 0)
* U7 LED from 3V3P through R18 (1.5k) into SDA_P
R18 v3p u7a {r18:g}
XU7 u7a sda_p sda_rx gndl PC817 CTR={ctr} CJC={cjc}
* logic side: GPIO5 (SCL) pulse 0.2 .. 0.7 ms, GPIO6 (SDA) pulse 1.8 .. 2.3 ms, through 220 ohm into U5/U6
V3l v3l gndl 3.3
Vg5 g5 gndl PWL(0 0 0.2m 0 0.2001m 3.3 0.7m 3.3 0.7001m 0)
Vg6 g6 gndl PWL(0 0 1.8m 0 1.8001m 3.3 2.3m 3.3 2.3001m 0)
R16 g5 o5 260
R17 g6 o6 260
XU5 o5 gndl scl_p 0 PC817 CTR={ctr} CJC={cjc}
XU6 o6 gndl sda_p 0 PC817 CTR={ctr} CJC={cjc}
R19 sda_rx v3l {r19:g}
Cin sda_rx gndl 10p
.tran 0.2u 3m
.control
run
let rx = v(sda_rx)-v(gndl)
meas tran scl_fall trig v(g5) val=1.65 rise=1 targ v(scl_p) val=0.99 fall=1
meas tran scl_rise trig v(g5) val=1.65 fall=1 targ v(scl_p) val=2.31 rise=1
meas tran sda_fall trig v(g6) val=1.65 rise=1 targ v(sda_p) val=0.99 fall=1 td=1.7m
meas tran sda_rise trig v(g6) val=1.65 fall=1 targ v(sda_p) val=2.31 rise=1 td=2.2m
meas tran rx_fall trig v(ackc) val=0.5 rise=1 targ rx val=0.825 fall=1
meas tran rx_rise trig v(ackc) val=0.5 fall=1 targ rx val=2.475 rise=1
meas tran sda_low_level max v(sda_p) from=1.2m to=1.4m
meas tran i_sink max i(v3p) from=1.2m to=1.4m
meas tran rx_low_level min rx from=1.2m to=1.4m
.endc
.end
"""

def run(ctr, cjc, **kw):
    out = subprocess.run(["ngspice", "-b"], input=netlist(ctr, cjc, **kw), capture_output=True, text=True)
    res = {}
    for line in out.stdout.splitlines():
        m = re.match(r"^(\w+)\s+=\s+([-+\d.eE]+)", line.strip())
        if m: res[m.group(1)] = float(m.group(2))
    return res

if __name__ == "__main__":
    rows, worst = [], {}
    for ctr, cjc in itertools.product((0.5, 1.0, 3.0), ("15p", "75p")):
        r = run(ctr, cjc); rows.append((ctr, cjc, r))
        for k, v in r.items():
            if k.endswith("level"): worst[k] = max(worst.get(k, 0), v)
            else: worst[k] = max(worst.get(k, 0), v)
        print(f"CTR {ctr:3}  CJC {cjc:>3}:  " + "  ".join(f"{k}={v*1e6:6.1f}us" if not k.endswith("level") else f"{k}={v:.3f}V" for k, v in r.items()))
    delays = [v for k, v in worst.items() if not k.endswith("level")]
    half = max(delays)
    print(f"worst edge delay {half*1e6:.1f} us -> firmware half-bit time >= {2*half*1e6:.0f} us (used: 500 us)")
    json.dump({"corners": [{"ctr": c, "cjc": j, **r} for c, j, r in rows], "worst": worst,
               "recommended_half_bit_us": round(2 * half * 1e6)}, open(os.path.join(HERE, "results_i2c.json"), "w"), indent=1)
