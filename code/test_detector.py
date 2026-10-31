"""P4 - Sealed-face detection in three dimensions, and what it does to the
pre-registered accuracy contract.

Real CityGML tiles contain overlapping and nested volumes, so a facet of one
building can sit inside the solid of its neighbour. Such a facet receives no
light: the path tracer returns almost zero there, and a depth-buffer engine
with front-face culling cannot see the enclosure, because the enclosing faces
are lit faces. The published run detected those faces with a vertical parity
test, which is incomplete by construction: it asks for odd parity upwards and
downwards, and therefore misses a surface sealed inside a volume whose roof or
floor is not watertight.

This test replaces that criterion with a three-dimensional enclosure test
(`sealed_faces_3d` in orient_normals.py: parity along six axis directions plus
the face normal, majority of five) and measures three things that were not
measured before:

  1. how many faces each criterion finds, and how much it costs;
  2. detection quality against the path-traced control, which is independent of
     the engine: precision and recall for the probe surfaces the control itself
     reports as dark;
  3. the pre-registered contract re-evaluated with the better detector, as a
     dated addendum. The originally registered verdict is not touched.

The path-traced control is reused unchanged: the detector decides which
surfaces the engine reports, not what the control computes.

Run:
    python test_detector.py --tile tile_51324376.npz \
        --control resultados/control_cycles.npz \
        --probes resultados/probes.npz --out detector.json
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
DARK_KWH = 1.0  # the control's own threshold for "this surface gets no light"


def sh(cmd):
    print("+", " ".join(str(c) for c in cmd), flush=True)
    t0 = time.time()
    r = subprocess.run(cmd, cwd=HERE)
    print(f"  -> exit {r.returncode} in {time.time()-t0:.1f} s", flush=True)
    if r.returncode != 0:
        sys.exit(r.returncode)
    return time.time() - t0


def quality(pred: np.ndarray, truth: np.ndarray) -> dict:
    tp = int((pred & truth).sum())
    fp = int((pred & ~truth).sum())
    fn = int((~pred & truth).sum())
    tn = int((~pred & ~truth).sum())
    prec = tp / (tp + fp) if tp + fp else float("nan")
    rec = tp / (tp + fn) if tp + fn else float("nan")
    f1 = 2 * prec * rec / (prec + rec) if tp and (prec + rec) > 0 else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": prec, "recall": rec, "f1": f1}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tile", required=True)
    ap.add_argument("--control", required=True)
    ap.add_argument("--probes", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workdir", default="detector_runs")
    ap.add_argument("--lat", type=float, default=34.3955)
    ap.add_argument("--lon", type=float, default=132.4535)
    ap.add_argument("--hour-step", type=float, default=1.0)
    ap.add_argument("--texel", type=float, default=0.5)
    ap.add_argument("--samples-per-m2", type=float, default=2.0)
    ap.add_argument("--device", default="cpu")
    a = ap.parse_args()

    work = os.path.join(HERE, a.workdir)
    os.makedirs(work, exist_ok=True)

    nrm = os.path.join(work, "normals_majority3d.npz")
    t_pre = sh([sys.executable, "orient_normals.py", "--tile", a.tile,
                "--out", nrm, "--enclosure", "majority3d"])

    nz = np.load(nrm)
    vertical = nz["buried_vertical"]
    sealed3d = nz["sealed_majority3d"]
    union = vertical | sealed3d

    n3 = os.path.join(work, "neuro3d_majority3d.npz")
    sh([sys.executable, "neuro3d_irradiance.py", "--tile", a.tile, "--out", n3,
        "--normals", nrm, "--lat", str(a.lat), "--lon", str(a.lon),
        "--hour-step", str(a.hour_step), "--texel", str(a.texel),
        "--samples-per-m2", str(a.samples_per_m2), "--device", a.device])

    # Equal-load figure for the addendum, so the cost claim stays like for like.
    eq = os.path.join(work, "neuro3d_majority3d_equal_load.npz")
    sh([sys.executable, "neuro3d_irradiance.py", "--tile", a.tile, "--out", eq,
        "--normals", nrm, "--only-index", a.probes,
        "--lat", str(a.lat), "--lon", str(a.lon),
        "--hour-step", str(a.hour_step), "--texel", str(a.texel),
        "--samples-per-m2", str(a.samples_per_m2), "--device", a.device])
    with open(n3 + ".meta.json", encoding="utf-8") as f:
        meta = json.load(f)
    with open(eq + ".meta.json", encoding="utf-8") as f:
        meta["equal_load_seconds"] = json.load(f)["light_transport_seconds"]
    with open(n3 + ".meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    contract = os.path.join(work, "CONTRATO-001_majority3d.json")
    sh([sys.executable, "compare.py", "--neuro3d", n3, "--control", a.control,
        "--probes", a.probes, "--out", contract])

    ctl = np.load(a.control)
    pr = np.load(a.probes)
    idx = pr["index"]
    dark = ctl["kwh"] < DARK_KWH

    res = {
        "test": "P4 three-dimensional sealed-face detection",
        "criterion": "parity along the six axis directions plus the face "
                     "normal; sealed when at least five of the seven are odd. "
                     "Fixed before measuring.",
        "faces_total": int(len(vertical)),
        "found": {
            "vertical_only": int(vertical.sum()),
            "majority3d_only": int(sealed3d.sum()),
            "union_used": int(union.sum()),
            "new_faces_found_by_3d": int((sealed3d & ~vertical).sum()),
        },
        "preprocessing_seconds": round(t_pre, 1),
        "detection_quality_on_probes": {
            "truth": f"the path-traced control reports under {DARK_KWH} "
                     f"kWh/m2/yr on the probe surface",
            "dark_probes": int(dark.sum()),
            "probes": int(len(idx)),
            "vertical": quality(vertical[idx], dark),
            "majority3d_union": quality(union[idx], dark),
        },
        "contract_with_better_detector": json.load(open(contract, encoding="utf-8")),
    }
    # Drop the bulky engine metadata from the embedded contract.
    res["contract_with_better_detector"].pop("engines", None)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    print(json.dumps({k: v for k, v in res.items()
                      if k != "contract_with_better_detector"}, indent=2))
    h1 = res["contract_with_better_detector"]["H1_all_probes_preregistered"]
    print(f"H1 over every probe with the 3-D detector: R2={h1['r2']:.3f} "
          f"bias={h1['mean_bias_fraction']*100:+.1f} % "
          f"median={h1['median_rel_error']*100:.1f} % "
          f"p95={h1['p95_rel_error']*100:.1f} % -> "
          f"{'PASS' if h1['pass'] else 'FAIL'}")


if __name__ == "__main__":
    main()
