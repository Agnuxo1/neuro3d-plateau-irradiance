"""P1 - Scaling: does the cost of a light direction depend on how many
buildings block it?

The engine claims that a light direction costs one scatter write plus one
gather, independent of the number of occluders. That claim was asserted in the
first delivery and never measured. Here the queried surfaces are held fixed and
only the scene changes: a pseudo-random subset of the district's buildings is
splatted into the depth buffers, from 5 per cent to 100 per cent of them, and
the light-transport time is measured for each.

A per-direction cost independent of the occluder count shows up as a time that
grows far more slowly than the number of occluders, with the residual growth
explained by the splat write itself, which is linear in the number of points
and is the only part that must touch every occluder.

Run:
    python test_scaling.py --tile tile_51324376.npz \
        --normals normals_51324376.npz --out scaling.json
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FRACTIONS = (0.05, 0.10, 0.25, 0.50, 1.00)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tile", required=True)
    ap.add_argument("--normals", default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--workdir", default="scaling_runs")
    ap.add_argument("--queries", type=int, default=2000)
    ap.add_argument("--lat", type=float, default=34.3955)
    ap.add_argument("--lon", type=float, default=132.4535)
    ap.add_argument("--hour-step", type=float, default=3.0)
    ap.add_argument("--texel", type=float, default=0.5)
    ap.add_argument("--samples-per-m2", type=float, default=2.0)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--repeats", type=int, default=2)
    a = ap.parse_args()

    work = os.path.join(HERE, a.workdir)
    os.makedirs(work, exist_ok=True)

    # The query set is fixed once, from the faces that survive preprocessing,
    # and reused for every scene size. Seed 0, no stratification: this test is
    # about cost, not accuracy.
    d = np.load(a.tile)
    ntri = len(d["tri"])
    rng = np.random.default_rng(0)
    pool = np.arange(ntri)
    if a.normals:
        nz = np.load(a.normals)
        ok = np.isfinite(nz["normals"]).all(1)
        if "buried" in nz:
            ok &= ~nz["buried"]
        pool = pool[ok]
    sel = np.sort(rng.choice(pool, size=min(a.queries, len(pool)), replace=False))
    qfile = os.path.join(work, "queries.npz")
    np.savez_compressed(qfile, index=sel)
    print(f"fixed query set: {len(sel)} surfaces of {ntri}", flush=True)

    rows = []
    for frac in FRACTIONS:
        for rep in range(a.repeats):
            out = os.path.join(work, f"scene_{int(frac*100):03d}_{rep}.npz")
            cmd = [sys.executable, "neuro3d_irradiance.py",
                   "--tile", a.tile, "--out", out,
                   "--only-index", qfile,
                   "--scene-bldg-frac", str(frac),
                   "--lat", str(a.lat), "--lon", str(a.lon),
                   "--hour-step", str(a.hour_step),
                   "--texel", str(a.texel),
                   "--samples-per-m2", str(a.samples_per_m2),
                   "--device", a.device]
            if a.normals:
                cmd += ["--normals", a.normals]
            t0 = time.time()
            r = subprocess.run(cmd, cwd=HERE)
            if r.returncode != 0:
                sys.exit(r.returncode)
            meta = json.load(open(out + ".meta.json", encoding="utf-8"))
            rows.append({
                "scene_bldg_frac": frac,
                "repeat": rep,
                "scene_buildings": meta["scene_buildings"],
                "scene_triangles": meta["scene_triangles"],
                "splat_points": meta["splat_points"],
                "queries": meta["triangles_used"],
                "directions": meta["directions"],
                "light_transport_seconds": meta["light_transport_seconds"],
                "seconds_per_direction": meta["light_transport_seconds"] / meta["directions"],
                "wall_seconds_process": round(time.time() - t0, 2),
            })
            print(json.dumps(rows[-1]), flush=True)
            os.remove(out)

    # Best of the repeats per scene size: the shared lane is not isolated, so
    # the minimum is the least noisy estimator of the cost.
    best = {}
    for r in rows:
        k = r["scene_bldg_frac"]
        if k not in best or r["light_transport_seconds"] < best[k]["light_transport_seconds"]:
            best[k] = r
    curve = [best[f] for f in FRACTIONS]
    ref, top = curve[0], curve[-1]
    occl_growth = top["splat_points"] / max(1, ref["splat_points"])
    time_growth = top["light_transport_seconds"] / max(1e-9, ref["light_transport_seconds"])
    res = {
        "test": "P1 scaling: light-transport time versus occluder count, "
                "queried surfaces held fixed",
        "fixed_queries": int(len(sel)),
        "runs": rows,
        "curve": curve,
        "occluder_growth_5pc_to_100pc": occl_growth,
        "time_growth_5pc_to_100pc": time_growth,
        "exponent_log_log": float(np.log(time_growth) / np.log(occl_growth)),
        "verdict": ("sub-linear in the occluder count"
                    if time_growth < occl_growth else
                    "not sub-linear in the occluder count"),
    }
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    print(json.dumps({k: v for k, v in res.items() if k != "runs"}, indent=2))


if __name__ == "__main__":
    main()
