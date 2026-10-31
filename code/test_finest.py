"""P2b - the combined finest configuration.

P2 sweeps one parameter at a time, and the two main ones move the answer in
opposite directions: finer depth texels let more light through, denser splat
sampling blocks more. Sweeping them separately cannot say where the engine
converges, so this run takes the finest value of all three at once and compares
it with the configuration used for the published measurement, on the same query
surfaces.

    python test_finest.py --tile tile_51324376.npz --normals normals.npz \
        --out P2b_finest.json
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = {"texel": 0.5, "spm2": 2.0, "hstep": 1.0}
FINEST = {"texel": 0.25, "spm2": 8.0, "hstep": 0.5}


def run(a, qfile, work, cfg, tag):
    out = os.path.join(work, tag + ".npz")
    cmd = [sys.executable, "neuro3d_irradiance.py", "--tile", a.tile,
           "--out", out, "--only-index", qfile,
           "--lat", str(a.lat), "--lon", str(a.lon), "--device", a.device,
           "--texel", str(cfg["texel"]), "--samples-per-m2", str(cfg["spm2"]),
           "--hour-step", str(cfg["hstep"])]
    if a.normals:
        cmd += ["--normals", a.normals]
    print("+", " ".join(cmd), flush=True)
    r = subprocess.run(cmd, cwd=HERE)
    if r.returncode != 0:
        sys.exit(r.returncode)
    meta = json.load(open(out + ".meta.json", encoding="utf-8"))
    idx = np.load(qfile)["index"]
    per = np.load(out)["per_tri"]
    tot = per[idx, 0] + per[idx, 1]
    os.remove(out)
    return meta, tot


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tile", required=True)
    ap.add_argument("--normals", default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--workdir", default="finest_runs")
    ap.add_argument("--queries", type=int, default=1500)
    ap.add_argument("--lat", type=float, default=34.39298186)
    ap.add_argument("--lon", type=float, default=132.46132208)
    ap.add_argument("--device", default="cpu")
    a = ap.parse_args()

    work = os.path.join(HERE, a.workdir)
    os.makedirs(work, exist_ok=True)
    # Same deterministic query set as test_convergence.py.
    d = np.load(a.tile)
    pool = np.arange(len(d["tri"]))
    if a.normals:
        nz = np.load(a.normals)
        ok = np.isfinite(nz["normals"]).all(1)
        if "buried" in nz:
            ok &= ~nz["buried"]
        pool = pool[ok]
    sel = np.sort(np.random.default_rng(0).choice(
        pool, size=min(a.queries, len(pool)), replace=False))
    qfile = os.path.join(work, "queries.npz")
    np.savez_compressed(qfile, index=sel)

    mb, tb = run(a, qfile, work, BASE, "base")
    mf, tf = run(a, qfile, work, FINEST, "finest")
    dev = np.abs(tb - tf) / np.maximum(tf, 1.0)
    res = {
        "test": "P2b combined finest configuration",
        "queries": int(len(sel)),
        "base": {"config": BASE, "mean_kwh": float(tb.mean()),
                 "median_kwh": float(np.median(tb)),
                 "seconds": mb["light_transport_seconds"],
                 "splat_points": mb["splat_points"],
                 "directions": mb["directions"]},
        "finest": {"config": FINEST, "mean_kwh": float(tf.mean()),
                   "median_kwh": float(np.median(tf)),
                   "seconds": mf["light_transport_seconds"],
                   "splat_points": mf["splat_points"],
                   "directions": mf["directions"]},
        "mean_shift_base_vs_finest": float((tb.mean() - tf.mean()) / tf.mean()),
        "median_abs_deviation": float(np.median(dev)),
        "p95_abs_deviation": float(np.percentile(dev, 95)),
        "cost_ratio_finest_over_base": (mf["light_transport_seconds"]
                                        / max(1e-9, mb["light_transport_seconds"])),
    }
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
