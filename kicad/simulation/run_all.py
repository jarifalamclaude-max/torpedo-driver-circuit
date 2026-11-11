import json, sys
from board2spice import run
ARM = "PWL(0 0 20m 0 20.001m 3.3 310m 3.3 310.001m 0)"
FIRE = "PWL(0 0 30m 0 30.001m 3.3 280m 3.3 280.001m 0)"
LETS = ["let isol1 = abs(i(lsol1))", "let isol2 = abs(i(lsol2))"]   # a solenoid has no polarity
def at(t): return f"find X at={t}"
COMMON = [("ratio_idle", "ratio", at("15m")), ("isol1_idle_uA", "isol1", at("15m")), ("vsense_idle", "v(vsense)", at("15m")),
          ("swsense_idle", "v(swsense)", at("15m")), ("vg1_idle", "v(g1)", at("15m")), ("vgs3_idle", "vgs3", at("15m"))]
FIRE_MEAS = COMMON + [
    ("ratio_armed", "ratio", at("28m")), ("vgs3_on", "vgs3", at("28m")), ("vg_armed", "v(vg)", at("28m")), ("isol1_armed", "isol1", at("29m")),
    ("ipeak1", "isol1", "max X from=30m to=285m"), ("ipeak2", "isol2", "max X from=0 to=399m"),
    ("vgs1_on", "v(g1)", at("200m")), ("vgs2_on", "v(g2)", at("200m")), ("vds1_on", "v(d1n)", at("200m")), ("vg_on", "v(vg)", at("200m")),
    ("swsense_on", "v(swsense)", at("200m")), ("vsense_on", "v(vsense)", at("200m")), ("vdmax", "v(d1n)", "max X from=279m to=295m"),
    ("vswmax", "v(vsw)", "max X from=0 to=399m"), ("vbat_min", "v(vbat)", "min X from=0 to=399m"),
    ("vg1max", "v(g1)", "max X from=0 to=399m"), ("vgs3min", "vgs3", "min X from=0 to=399m"),
    ("isol1_300", "isol1", at("300m")), ("ratio_after", "ratio", at("395m")), ("t_ton_1mA", "isol1", "when X=0.5 rise=1"),
    ("t_i50mA", "isol1", "when X=0.05 fall=1"), ("vg2max", "v(g2)", "max X from=0 to=399m"),
    ("t_vg1max", "v(g1)", "max_at X from=0 to=399m"), ("t_vg2max", "v(g2)", "max_at X from=0 to=399m")]
IDLE = COMMON + [("vsw", "v(vsw)", at("15m")), ("isol1max", "isol1", "max X from=1m to=19m"), ("isol2max", "isol2", "max X from=1m to=19m"), ("isol1_end", "isol1", at("19m"))]
def idle(name, extra=[], gpio={}, VB=16.8, **kw):
    return dict(name=name, VB=VB, gpio=gpio, extra=extra, lets=LETS, meas=IDLE, tstop="20m", **kw)
SC = [
 dict(name="normal", VB=16.8, gpio={10: ARM, 1: FIRE}, lets=LETS, meas=FIRE_MEAS,
      wr=("/home/claude/torpedo/sim3/normal.dat", ["isol1", "v(vsw)", "v(d1n)", "v(g1)", "v(g3)", "v(vbat)", "v(swsense)", "v(vg)", "isol2"])),
 dict(name="low13v2", VB=13.2, gpio={10: ARM, 1: FIRE}, lets=LETS, meas=FIRE_MEAS),
 dict(name="both_ch", VB=16.8, gpio={10: ARM, 1: FIRE, 0: FIRE}, lets=LETS, meas=FIRE_MEAS),
 dict(name="ctr50_13v2", VB=13.2, CTR=0.5, gpio={10: ARM, 1: FIRE, 0: FIRE}, lets=LETS, meas=FIRE_MEAS),
 dict(name="ch2_only", VB=16.8, gpio={10: ARM, 0: FIRE}, lets=LETS, meas=FIRE_MEAS),
 dict(name="arm_only", VB=16.8, gpio={10: ARM}, lets=LETS, meas=FIRE_MEAS,
      wr=("/home/claude/torpedo/sim3/arm_only.dat", ["v(g1)", "v(vsw)", "v(vg)", "v(d1n)", "isol1"])),
 idle("idle_ok"),
 idle("idle_13v2", VB=13.2),
 idle("F_ls_short", ["Rfault d1n 0 0.01"]),
 idle("F_hs_short", ["Rfault vbat vsw 0.01"]),
 idle("F_fire_stuck", gpio={1: "DC 3.3"}),
 idle("F_arm_stuck", gpio={10: "DC 3.3"}),
 idle("boot_float", gpio={0: "float", 1: "float", 10: "float"}),
 idle("wet47k_gate", ["Rw1 vbat g1 47k", "Rw2 vbat g2 47k"]),
 idle("wet47k_g3", ["Rw3 g3 0 47k"]),
 idle("wet47k_all", ["Rw1 vbat g1 47k", "Rw2 vbat g2 47k", "Rw3 g3 0 47k", "Rw4 vsw 0 47k", "Rw5 vbat vsw 47k", "Rw6 vg g1 47k"]),
 idle("wet10k_gate", ["Rw1 vbat g1 10k"]),
 idle("wet10k_g3", ["Rw3 g3 0 10k"]),
 idle("wet10k_both", ["Rw1 vbat g1 10k", "Rw3 g3 0 10k"]),
 idle("lstest", gpio={1: "PWL(0 0 5m 0 5.001m 3.3)"}),
 dict(name="lstest_nosol", VB=16.8, gpio={1: "PWL(0 0 5m 0 5.001m 3.3)"}, nosol=1, lets=["let isol1 = abs(i(vdummy1))", "let isol2 = abs(i(lsol2))"], meas=IDLE, tstop="20m"),
]
if __name__ == "__main__":
    allres = {}
    for sc in SC:
        res, errs = run(sc); allres[sc["name"]] = res
        print(f"== {sc['name']}" + (f"   ERR {errs[:2]}" if errs else ""))
        print("   " + "  ".join(f"{k}={v:.4g}" for k, v in res.items()))
    json.dump(allres, open("/home/claude/torpedo/sim3/results.json", "w"), indent=1)
