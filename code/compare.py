"""Evaluate CONTRATO-001: own engine against the Cycles control on the probes."""

from __future__ import annotations

import argparse
import json

import numpy as np


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--neuro3d", required=True)
    ap.add_argument("--control", required=True)
    ap.add_argument("--probes", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    n3 = np.load(a.neuro3d)
    ctl = np.load(a.control)
    pr = np.load(a.probes)
    meta_n3 = json.load(open(a.neuro3d + ".meta.json", encoding="utf-8"))
    meta_ct = json.load(open(a.control + ".meta.json", encoding="utf-8"))["summary"]

    idx = pr["index"]
    assert np.array_equal(idx, ctl["probe_index"]), "probe sets differ"
    per = n3["per_tri"]
    own = per[idx, 0] + per[idx, 1]
    ref = ctl["kwh"]
    sem = pr["sem"]

    good = np.isfinite(own) & np.isfinite(ref) & (ref > 1.0)
    o, r = own[good], ref[good]
    resid = o - r
    ss_res = float((resid**2).sum())
    ss_tot = float(((r - r.mean()) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    rel = np.abs(resid) / r
    bias = float(resid.mean())

    # Speed, per surface actually computed, on the same machine.
    s_own = meta_n3["light_transport_seconds"] / meta_n3["triangles_used"]
    s_ctl = meta_ct["seconds_total"] / meta_ct["probes"]

    tot_all = per[n3["keep"], 0] + per[n3["keep"], 1]
    open_all = per[n3["keep"], 2] + per[n3["keep"], 3]
    svf = per[n3["keep"], 4]

    cal_err = meta_ct["calibration_rel_error"]
    res = {
        "probes_compared": int(good.sum()),
        "probes_total": int(len(idx)),
        "C1_calibration_rel_error": cal_err,
        "C1_pass": bool(cal_err <= 0.03),
        "H1": {
            "r2": r2,
            "mean_bias_kwh": bias,
            "mean_bias_fraction": float(bias / r.mean()),
            "median_rel_error": float(np.median(rel)),
            "p95_rel_error": float(np.percentile(rel, 95)),
            "control_mean_kwh": float(r.mean()),
            "own_mean_kwh": float(o.mean()),
            "pass": bool(r2 >= 0.90 and abs(bias / r.mean()) <= 0.10
                         and np.median(rel) <= 0.15
                         and np.percentile(rel, 95) <= 0.40),
        },
        "H2": {
            "own_seconds_total": meta_n3["light_transport_seconds"],
            "own_surfaces": meta_n3["triangles_used"],
            "own_seconds_per_surface": s_own,
            "control_seconds_total": meta_ct["seconds_total"],
            "control_surfaces": meta_ct["probes"],
            "control_seconds_per_surface": s_ctl,
            "speedup_per_surface": s_ctl / s_own if s_own > 0 else float("inf"),
            "pass": bool(s_ctl / max(s_own, 1e-12) >= 20.0),
        },
        "H3": {
            "shading_loss_fraction": float(1 - tot_all.sum() / open_all.sum()),
            "svf_p05": float(np.percentile(svf, 5)),
            "svf_p95": float(np.percentile(svf, 95)),
            "pass": bool((1 - tot_all.sum() / open_all.sum()) >= 0.10
                         and np.percentile(svf, 5) <= 0.2
                         and np.percentile(svf, 95) >= 0.9),
        },
        "by_class": {},
        "engines": {"own": meta_n3, "control": meta_ct},
    }
    names = {0: "ground", 1: "wall", 2: "roof", 3: "lod1_or_other"}
    for s, nm in names.items():
        m = good & (sem == s)
        if m.sum() >= 5:
            oo, rr = own[m], ref[m]
            res["by_class"][nm] = {
                "n": int(m.sum()),
                "median_rel_error": float(np.median(np.abs(oo - rr) / rr)),
                "mean_bias_fraction": float((oo - rr).mean() / rr.mean()),
                "control_mean_kwh": float(rr.mean()),
            }

    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    np.savez_compressed(a.out + ".pairs.npz", index=idx, own=own, control=ref, sem=sem)
    print(json.dumps({k: v for k, v in res.items() if k != "engines"}, indent=2))


if __name__ == "__main__":
    main()
