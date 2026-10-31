"""P2 - Numerical convergence: how much of the answer is the discretisation?

The published measurement used one configuration: 0.5 m depth texels, 2 splat
points per square metre and one solar step per hour. Nothing said how much the
answer would move with a finer or coarser setting, so a reader could not tell
whether the agreement with the path tracer was robust or lucky.

This test sweeps one parameter at a time around that configuration and reports
the deviation of the annual irradiance and of the sky view factor against the
finest setting of each sweep, on a fixed set of query surfaces. It gives the
numerical error bar of the engine, separate from any comparison with a control.

Run:
    python test_convergence.py --tile tile_51324376.npz \
        --normals normals_51324376.npz --out convergence.json
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))

# Each sweep is ordered from the finest setting to the coarsest; the finest is
# the reference against which the others are reported.
SWEEPS = {
    "texel_m": [0.25, 0.5, 1.0, 2.0],
    "samples_per_m2": [8.0, 4.0, 2.0, 0.5],
    "hour_step_h": [0.25, 0.5, 1.0, 2.0],
}
BASE = {"texel_m": 0.5, "samples_per_m2": 2.0, "hour_step_h": 1.0}


def run_one(a, qfile, work, cfg, tag):
    out = os.path.join(work, f"{tag}.npz")
    cmd = [sys.executable, "neuro3d_irradiance.py",
           "--tile", a.tile, "--out", out, "--only-index", qfile,
           "--lat", str(a.lat), "--lon", str(a.lon),
           "--texel", str(cfg["texel_m"]),
           "--samples-per-m2", str(cfg["samples_per_m2"]),
           "--hour-step", str(cfg["hour_step_h"]),
           "--device", a.device]
    if a.normals:
        cmd += ["--normals", a.normals]
    r = subprocess.run(cmd, cwd=HERE)
    if r.returncode != 0:
        sys.exit(r.returncode)
    meta = json.load(open(out + ".meta.json", encoding="utf-8"))
    z = np.load(out)
    idx = np.load(qfile)["index"]
    per = z["per_tri"]
    tot = per[idx, 0] + per[idx, 1]
    svf = per[idx, 4]
    os.remove(out)
    return {
        "config": dict(cfg),
        "splat_points": meta["splat_points"],
        "directions": meta["directions"],
        "light_transport_seconds": meta["light_transport_seconds"],
        "annual_kwh_mean": float(tot.mean()),
        "annual_kwh_median": float(np.median(tot)),
        "svf_mean": float(svf.mean()),
        "_tot": tot,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tile", required=True)
    ap.add_argument("--normals", default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--workdir", default="convergence_runs")
    ap.add_argument("--queries", type=int, default=1500)
    ap.add_argument("--lat", type=float, default=34.3955)
    ap.add_argument("--lon", type=float, default=132.4535)
    ap.add_argument("--device", default="cpu")
    a = ap.parse_args()

    work = os.path.join(HERE, a.workdir)
    os.makedirs(work, exist_ok=True)

    d = np.load(a.tile)
    pool = np.arange(len(d["tri"]))
    if a.normals:
        nz = np.load(a.normals)
        ok = np.isfinite(nz["normals"]).all(1)
        if "buried" in nz:
            ok &= ~nz["buried"]
        pool = pool[ok]
    rng = np.random.default_rng(0)
    sel = np.sort(rng.choice(pool, size=min(a.queries, len(pool)), replace=False))
    qfile = os.path.join(work, "queries.npz")
    np.savez_compressed(qfile, index=sel)
    print(f"fixed query set: {len(sel)} surfaces", flush=True)

    res = {"test": "P2 numerical convergence, one parameter at a time",
           "fixed_queries": int(len(sel)), "base_config": BASE, "sweeps": {}}
    for name, values in SWEEPS.items():
        runs = []
        for v in values:
            cfg = dict(BASE)
            cfg[name] = v
            tag = f"{name}_{str(v).replace('.', 'p')}"
            runs.append(run_one(a, qfile, work, cfg, tag))
            print(f"{name}={v}: mean={runs[-1]['annual_kwh_mean']:.2f} "
                  f"kWh/m2/yr  svf={runs[-1]['svf_mean']:.4f}  "
                  f"{runs[-1]['light_transport_seconds']:.1f} s", flush=True)
        finest = runs[0]
        rows = []
        for r in runs:
            dev = np.abs(r["_tot"] - finest["_tot"]) / np.maximum(finest["_tot"], 1.0)
            rows.append({
                k: v for k, v in r.items() if k != "_tot"
            } | {
                "mean_shift_vs_finest": float(
                    (r["annual_kwh_mean"] - finest["annual_kwh_mean"])
                    / finest["annual_kwh_mean"]),
                "median_abs_deviation_vs_finest": float(np.median(dev)),
                "p95_abs_deviation_vs_finest": float(np.percentile(dev, 95)),
            })
        res["sweeps"][name] = {
            "values_finest_first": values,
            "runs": rows,
            "base_vs_finest_mean_shift": next(
                r["mean_shift_vs_finest"] for r in rows
                if r["config"][name] == BASE[name]),
        }

    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    print(json.dumps({k: (v if k != "sweeps" else {
        n: s["base_vs_finest_mean_shift"] for n, s in v.items()})
        for k, v in res.items()}, indent=2))


if __name__ == "__main__":
    main()
