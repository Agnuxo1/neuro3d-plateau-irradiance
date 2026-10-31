"""The four new measurements, as one job on the shared CPU lane.

P1  scaling      - light-transport time versus occluder count, queries fixed
P2  convergence  - numerical error bar of the discretisation
P3  transfer     - the whole comparison on a city never used while tuning
P4  detector     - three-dimensional sealed-face detection, and the contract
                   re-evaluated with it

Everything writes into --outdir. Each test is independent: if one fails the
others still produce their file, and the failure is recorded.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))

HIRO = {"tile": "tile_51324376.npz", "normals": "normals_51324376.npz",
        "lat": 34.39298186, "lon": 132.46132208}
# Transfer tile, chosen before anything was measured on it: another city
# (Nagoya), same vintage (2022) and same CityGML version (v3), and the mesh had
# to carry LOD2 semantic surfaces because the published measurement was made on
# LOD2 geometry. Among the Nagoya building meshes that do, the largest one,
# that is the densest central district. No second look, no tuning.
NAGO = {"tile": "tile_52366700.npz", "lat": 35.16686725, "lon": 136.88672513}


def sh(cmd, log):
    line = "+ " + " ".join(str(c) for c in cmd)
    print(line, flush=True)
    t0 = time.time()
    r = subprocess.run(cmd, cwd=HERE)
    dt = time.time() - t0
    print(f"  -> exit {r.returncode} in {dt:.1f} s", flush=True)
    log.append({"cmd": line, "exit": r.returncode, "seconds": round(dt, 1)})
    if r.returncode != 0:
        raise RuntimeError(line)
    return dt


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default="pruebas")
    ap.add_argument("--control", default="resultados/control_cycles.npz")
    ap.add_argument("--probes", default="resultados/probes.npz")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--cycles-samples", type=int, default=512)
    ap.add_argument("--only", default="", help="comma-separated subset: p1,p2,p3,p4")
    a = ap.parse_args()

    out = os.path.join(HERE, a.outdir)
    os.makedirs(out, exist_ok=True)
    only = [s.strip() for s in a.only.split(",") if s.strip()]         or ["p1", "p2", "p3", "p4"]
    status = {}

    def attempt(name, fn):
        if name not in only:
            return
        log: list = []
        t0 = time.time()
        try:
            fn(log)
            status[name] = {"ok": True, "seconds": round(time.time() - t0, 1),
                            "steps": log}
        except Exception as exc:  # recorded, never hidden
            status[name] = {"ok": False, "error": repr(exc),
                            "seconds": round(time.time() - t0, 1), "steps": log}
            print(f"!! {name} failed: {exc!r}", flush=True)
        with open(os.path.join(out, "STATUS.json"), "w", encoding="utf-8") as f:
            json.dump(status, f, indent=2)

    def p1(log):
        sh([sys.executable, "test_scaling.py", "--tile", HIRO["tile"],
            "--normals", HIRO["normals"], "--device", a.device,
            "--lat", str(HIRO["lat"]), "--lon", str(HIRO["lon"]),
            "--workdir", os.path.join(a.outdir, "scaling_runs"),
            "--out", os.path.join(out, "P1_scaling.json")], log)

    def p2(log):
        sh([sys.executable, "test_convergence.py", "--tile", HIRO["tile"],
            "--normals", HIRO["normals"], "--device", a.device,
            "--lat", str(HIRO["lat"]), "--lon", str(HIRO["lon"]),
            "--workdir", os.path.join(a.outdir, "convergence_runs"),
            "--out", os.path.join(out, "P2_convergence.json")], log)

    def p2b(log):
        sh([sys.executable, "test_finest.py", "--tile", HIRO["tile"],
            "--normals", HIRO["normals"], "--device", a.device,
            "--lat", str(HIRO["lat"]), "--lon", str(HIRO["lon"]),
            "--workdir", os.path.join(a.outdir, "finest_runs"),
            "--out", os.path.join(out, "P2b_finest.json")], log)

    def p4(log):
        sh([sys.executable, "test_detector.py", "--tile", HIRO["tile"],
            "--control", a.control, "--probes", a.probes, "--device", a.device,
            "--lat", str(HIRO["lat"]), "--lon", str(HIRO["lon"]),
            "--workdir", os.path.join(a.outdir, "detector_runs"),
            "--out", os.path.join(out, "P4_detector.json")], log)

    def p3(log):
        nrm = os.path.join(a.outdir, "normals_nagoya.npz")
        sh([sys.executable, "orient_normals.py", "--tile", NAGO["tile"],
            "--out", nrm, "--enclosure", "vertical"], log)
        res = os.path.join(a.outdir, "nagoya")
        sh([sys.executable, "run_pilot.py", "--tile", NAGO["tile"],
            "--normals", nrm, "--outdir", res,
            "--lat", str(NAGO["lat"]), "--lon", str(NAGO["lon"]),
            "--device", a.device, "--samples", str(a.cycles_samples)], log)
        with open(os.path.join(HERE, res, "CONTRATO-001.json"),
                  encoding="utf-8") as f:
            transfer = json.load(f)
        transfer.pop("engines", None)

        # Same city, same control, with the three-dimensional detector: shows
        # whether the improvement carries over to geometry it never saw.
        nrm3 = os.path.join(a.outdir, "normals_nagoya_m3d.npz")
        sh([sys.executable, "orient_normals.py", "--tile", NAGO["tile"],
            "--out", nrm3, "--enclosure", "majority3d"], log)
        n3 = os.path.join(a.outdir, "nagoya_m3d.npz")
        sh([sys.executable, "neuro3d_irradiance.py", "--tile", NAGO["tile"],
            "--out", n3, "--normals", nrm3, "--device", a.device,
            "--lat", str(NAGO["lat"]), "--lon", str(NAGO["lon"]),
            "--texel", "0.5", "--samples-per-m2", "2.0"], log)
        c3 = os.path.join(a.outdir, "CONTRATO-001_nagoya_m3d.json")
        sh([sys.executable, "compare.py", "--neuro3d", n3,
            "--control", os.path.join(res, "control_cycles.npz"),
            "--probes", os.path.join(res, "probes.npz"), "--out", c3], log)
        with open(os.path.join(HERE, c3), encoding="utf-8") as f:
            transfer_m3d = json.load(f)
        transfer_m3d.pop("engines", None)

        payload = {
            "test": "P3 transfer to a city never used while tuning",
            "tile": NAGO,
            "selection_rule": (
                "another city (Nagoya), same vintage 2022, CityGML v3; the "
                "mesh had to carry LOD2 semantic surfaces because the "
                "published measurement was made on LOD2 geometry; among those, "
                "the largest file, that is the densest central district. Fixed "
                "before measuring, no second look."),
            "published_configuration": transfer,
            "with_3d_detector": transfer_m3d,
        }
        with open(os.path.join(out, "P3_transfer.json"), "w",
                  encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    attempt("p1", p1)
    attempt("p2", p2)
    attempt("p2b", p2b)
    attempt("p4", p4)
    attempt("p3", p3)
    print(json.dumps({k: {"ok": v["ok"], "seconds": v["seconds"]}
                      for k, v in status.items()}, indent=2))


if __name__ == "__main__":
    main()
