"""Run every v4 simulation scenario on the netlist generated from the PCB and write results.json.

Solenoid parameters default to a representative push-type solenoid (see SOL_DEFAULT in board2spice.py).
Replace them with your measured values, for example:
    python3 run_all.py --R 12 --LO 22m --LC 70m --S 6m --M 25m --K 150 --F0 0.6 --C 1.5
R = coil resistance (ohm), LO/LC = inductance with the plunger out/in, S = stroke, M = moving mass,
K = return spring rate (N/m), F0 = spring preload + latch force (N), C = damping, water + friction (N*s/m).
"""
import argparse, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from board2spice import run, OUTDIR

ARM = "PWL(0 0 20m 0 20.001m 3.3 330m 3.3 330.001m 0)"          # ARM 20 ms .. 330 ms
FIRE = "PWL(0 0 30m 0 30.001m 3.3 230m 3.3 230.001m 0)"         # FIRE 30 ms .. 230 ms (200 ms pulse, firmware default)
LETS = [("isol1", "abs(i(vsens1))"), ("x1", "v(xsol1.x)"), ("vds3", "v(vbat)-v(vsw)"),
        ("led1_ma", "(v(g1)-v(led1a))/10"), ("iopto1_ma", "-i(vgpio1)*1000"), ("d1n_vsw", "v(d1n)/v(vsw)"), ("d2n_vsw", "v(d2n)/v(vsw)")]
LETS2 = LETS + [("isol2", "abs(i(vsens2))"), ("x2", "v(xsol2.x)"), ("ibat", "abs(i(vbat))")]
def at(t): return f"find X at={t}"

IDLE = [("ratio_idle", "ratio", at("15m")), ("vsw_idle", "v(vsw)", at("15m")), ("d1n_idle", "v(d1n)", at("15m")),
        ("d2n_idle", "v(d2n)", at("15m")), ("adc_bat_idle", "v(sbat)", at("15m")), ("adc_sw_idle", "v(ssw)", at("15m")),
        ("adc_d1_idle", "v(sd1)", at("15m")), ("adc_d2_idle", "v(sd2)", at("15m")), ("vg_idle", "v(vg)", at("15m")),
        ("g1_idle", "v(g1)", at("15m")), ("vgs3_idle", "vgs3", at("15m")), ("v3v3p", "v(n3v3p)", at("15m"))]
FIRE_MEAS = IDLE + [
    ("ratio_armed", "ratio", at("28m")), ("vgs3_on", "vgs3", at("28m")), ("vg_armed", "v(vg)", at("28m")),
    ("g1_arm_max", "v(g1)", "max X from=20m to=29m"), ("g2_arm_max", "v(g2)", "max X from=20m to=29m"),
    ("isol1_arm_max", "isol1", "max X from=20m to=29m"),
    ("ipeak1", "isol1", "max X from=30m to=230m"), ("i1_end", "isol1", at("229m")),
    ("t_pullin", "x1", "when X=7.6m rise=1"), ("x1_max", "x1", "max X from=30m to=230m"),
    ("vgs1_on", "v(g1)", at("150m")), ("vds1_on", "v(d1n)", at("150m")), ("vds3_on", "vds3", at("150m")),
    ("vgs3_fire", "vgs3", at("150m")), ("vg_fire", "v(vg)", at("150m")), ("vsw_fire", "v(vsw)", at("150m")),
    ("adc_d1_fire", "v(sd1)", at("150m")), ("adc_sw_fire", "v(ssw)", at("150m")), ("adc_bat_fire", "v(sbat)", at("150m")),
    ("led1_ma", "led1_ma", at("150m")), ("iopto1_ma", "iopto1_ma", at("150m")),
    ("vd1n_flyback", "v(d1n)", "max X from=229m to=260m"), ("t_release", "x1", "when X=0.5m fall=1"),
    ("vbat_min", "v(vbat)", "min X from=0 to=399m"), ("vsw_max", "v(vsw)", "max X from=0 to=399m"),
    ("vg_max", "v(vg)", "max X from=0 to=399m"), ("g1_max", "v(g1)", "max X from=0 to=399m"),
    ("ratio_after", "ratio", at("395m"))]
BOTH_MEAS = FIRE_MEAS + [("ipeak2", "isol2", "max X from=30m to=230m"), ("vgs2_on", "v(g2)", at("150m")),
                         ("vds2_on", "v(d2n)", at("150m")), ("t_pullin2", "x2", "when X=7.6m rise=1")]
ARM_MEAS = IDLE + [("ratio_armed", "ratio", at("28m")), ("vgs3_on", "vgs3", at("28m")),
                   ("g1_arm_max", "v(g1)", "max X from=20m to=40m"), ("g2_arm_max", "v(g2)", "max X from=20m to=40m"),
                   ("isol1_arm_max", "isol1", "max X from=20m to=60m"), ("isol2_arm_max", "isol2", "max X from=20m to=60m")]
FAULT_MEAS = IDLE + [("isol1max", "isol1", "max X from=1m to=19m"), ("d1n_over_vsw", "d1n_vsw", at("15m")),
                     ("d2n_over_vsw", "d2n_vsw", at("15m"))]
SURGE = "PWL(0 {VB} 5m {VB} 5.05m 36 6m 36 6.05m {VB})"         # 36 V for 1 ms behind the battery: TVS must clamp
SURGE_MEAS = [("vbat_clamp", "v(vbat)", "max X from=4m to=8m"), ("vgs3_min", "vgs3", "min X from=4m to=8m"),
              ("vg_max", "v(vg)", "max X from=4m to=8m"), ("vpre_max", "v(vpre)", "max X from=4m to=8m"),
              ("v3v3p_max", "v(n3v3p)", "max X from=4m to=8m"), ("adc_bat_max", "v(sbat)", "max X from=4m to=8m"),
              ("isol1_max", "isol1", "max X from=4m to=8m"), ("g1_max", "v(g1)", "max X from=4m to=8m")]
HOTPLUG_MEAS = [("vgs3_min", "vgs3", "min X from=0 to=10m"), ("vsw_max", "v(vsw)", "max X from=0 to=10m"),
                ("g1_max", "v(g1)", "max X from=0 to=10m"), ("isol1_max", "isol1", "max X from=0 to=10m"),
                ("vbat_max", "v(vbat)", "max X from=0 to=10m"), ("i_inrush", "ibat", "max X from=0 to=10m")]

def scenarios(sol):
    s = float(str(sol["S"]).rstrip("m")) * (1e-3 if str(sol["S"]).endswith("m") else 1)
    thr = f"{0.95 * s:.6g}"
    for lst in (FIRE_MEAS, BOTH_MEAS):
        for i, (lab, e, k) in enumerate(lst):
            if lab.startswith("t_pullin"): lst[i] = (lab, e, f"when X={thr} rise=1")
    S = lambda **k: dict(sol=sol, **k)
    idle = lambda name, **k: S(name=name, lets=LETS2, meas=FAULT_MEAS, tstop="20m", **k)
    return [
        S(name="normal", VB=16.8, gpio={10: ARM, 1: FIRE}, lets=LETS2, meas=FIRE_MEAS,
          wr=("normal.dat", ["isol1", "x1", "v(vsw)", "v(d1n)", "v(g1)", "v(g3)", "v(vbat)", "v(vg)", "v(sd1)", "v(ssw)"])),
        S(name="both_ch", VB=16.8, gpio={10: ARM, 1: FIRE, 0: FIRE}, lets=LETS2, meas=BOTH_MEAS),
        S(name="bat14v8", VB=14.8, gpio={10: ARM, 1: FIRE}, lets=LETS2, meas=FIRE_MEAS),
        S(name="bat13v2", VB=13.2, gpio={10: ARM, 1: FIRE}, lets=LETS2, meas=FIRE_MEAS),
        S(name="bat12v0", VB=12.0, gpio={10: ARM, 1: FIRE}, lets=LETS2, meas=FIRE_MEAS),
        S(name="worst_drive", VB=12.0, CTR=0.5, VTO_N=2.0, VTO_P=-4.0, CJC="75p", gpio={10: ARM, 1: FIRE, 0: FIRE}, lets=LETS2, meas=BOTH_MEAS),
        S(name="miller_vth_min", VB=16.8, VTO_N=1.0, gpio={10: ARM}, lets=LETS2, meas=ARM_MEAS, tstop="80m"),
        S(name="miller_fast_arm", VB=16.8, VTO_N=1.0, CTR_U4=3.0, gpio={10: ARM}, lets=LETS2, meas=ARM_MEAS, tstop="80m"),
        S(name="hotplug", VB=16.8, c1_ic=0, vbat_src="PWL(0 0 1m 0 1.0005m {VB})", lets=LETS2, meas=HOTPLUG_MEAS, tstop="10m", tstep="1u", tmax="2u"),
        S(name="surge_disarmed", VB=16.8, vbat_src=SURGE, lets=LETS2, meas=SURGE_MEAS, tstop="10m", tstep="2u", tmax="5u"),
        S(name="surge_armed", VB=16.8, vbat_src=SURGE, gpio={10: "DC 3.3"}, lets=LETS2, meas=SURGE_MEAS, tstop="10m", tstep="2u", tmax="5u"),
        idle("idle_ok"),
        idle("idle_12v0", VB=12.0),
        idle("F_ls_short", extra=["Rfault d1n 0 0.01"]),
        idle("F_hs_short", extra=["Rfault vbat vsw 0.01"]),
        idle("F_open_coil1", nosol=1),
        idle("F_open_coil1_70C", nosol=1, extra=[".temp 70"]),
        idle("F_open_coil1_schottky", nosol=1, flyback="D1N5822"),
        idle("F_opto1_short", extra=["Rfault vg g1 1"]),
        idle("F_fire_stuck", gpio={1: "DC 3.3"}),
        idle("F_arm_stuck", gpio={10: "DC 3.3"}),
        idle("boot_float", gpio={0: "float", 1: "float", 10: "float", 5: "float", 6: "float"}),
        idle("wet47k_gate", extra=["Rw1 vbat g1 47k", "Rw2 vbat g2 47k"]),
        idle("wet47k_all", extra=["Rw1 vbat g1 47k", "Rw2 vbat g2 47k", "Rw3 g3 0 47k", "Rw4 vsw 0 47k", "Rw5 vbat vsw 47k", "Rw6 vg g1 47k"]),
        idle("wet10k_both", extra=["Rw1 vbat g1 10k", "Rw3 g3 0 10k"]),
    ]

def pullin_threshold(sol, lo=11.0, hi=16.8, steps=9):
    """Lowest battery voltage at which the plunger still reaches 95 % of the stroke inside the fire pulse."""
    sc0 = [s for s in scenarios(sol) if s["name"] == "normal"][0]
    meas = [m for m in FIRE_MEAS if m[0] in ("x1_max", "t_pullin")]
    s = float(str(sol["S"]).rstrip("m")) * (1e-3 if str(sol["S"]).endswith("m") else 1)
    def ok(vb):
        sc = dict(sc0, name="pullin_search", VB=vb, meas=meas); sc.pop("wr", None)
        r, _ = run(sc); return r.get("x1_max", 0) >= 0.95 * s, r.get("t_pullin")
    if not ok(hi)[0]: return None, None
    for _ in range(steps):
        mid = (lo + hi) / 2
        if ok(mid)[0]: hi = mid
        else: lo = mid
    return round(hi, 2), ok(hi)[1]

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    for k, v in dict(R="15", LO="25m", LC="75m", S="8m", M="30m", K="200", F0="0.8", C="2").items():
        ap.add_argument("--" + k, default=v)
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    sol = {k: getattr(a, k) for k in ("R", "LO", "LC", "S", "M", "K", "F0", "C")}
    allres = {}
    for sc in scenarios(sol):
        if a.only and sc["name"] not in a.only.split(","): continue
        res, errs = run(sc); allres[sc["name"]] = res
        print(f"== {sc['name']}" + (f"   ERR {errs[:2]}" if errs else ""))
        print("   " + "  ".join(f"{k}={v:.4g}" for k, v in res.items()))
    allres["_solenoid"] = sol
    if not a.only:
        vmin, tp = pullin_threshold(sol)
        allres["_pullin"] = {"min_vbat": vmin, "t_pullin_at_min": tp}
        print(f"== pull-in threshold: plunger closes down to VBAT = {vmin} V (fire at 30 ms, closed at {tp})")
    if not a.only:
        json.dump(allres, open(os.path.join(HERE, "results.json"), "w"), indent=1)
