"""One self-contained pilot run: own engine, Cycles control, comparison.

Written to run as a single job on the shared CPU lane, where nothing persists
between jobs, so it fetches its own Blender build if it is not already there.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tarfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER_URL = "https://download.blender.org/release/Blender4.5/blender-4.5.9-linux-x64.tar.xz"


def sh(cmd: list[str], **kw) -> None:
    print("+", " ".join(str(c) for c in cmd), flush=True)
    t0 = time.time()
    r = subprocess.run(cmd, cwd=HERE, **kw)
    print(f"  -> exit {r.returncode} in {time.time()-t0:.1f} s", flush=True)
    if r.returncode != 0:
        sys.exit(r.returncode)


def ensure_blender(root: str) -> str:
    exe = os.environ.get("BLENDER_EXE")
    if exe and os.path.exists(exe):
        return exe
    exe = os.path.join(root, "blender-4.5.9-linux-x64", "blender")
    if not os.path.exists(exe):
        os.makedirs(root, exist_ok=True)
        tarpath = os.path.join(root, "blender.tar.xz")
        print("downloading Blender", flush=True)
        urllib.request.urlretrieve(BLENDER_URL, tarpath)
        with tarfile.open(tarpath) as t:
            t.extractall(root)
        os.remove(tarpath)
    return exe


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tile", default="tile_51324376.npz")
    ap.add_argument("--normals", default="normals_51324376.npz")
    ap.add_argument("--outdir", default="resultados")
    ap.add_argument("--lat", type=float, default=34.3955)
    ap.add_argument("--lon", type=float, default=132.4535)
    ap.add_argument("--hour-step", type=float, default=1.0)
    ap.add_argument("--probes", type=int, default=900)
    ap.add_argument("--samples", type=int, default=512)
    ap.add_argument("--max-steps", type=int, default=0)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--cycles-device", default="CPU")
    ap.add_argument("--texel", type=float, default=0.5)
    ap.add_argument("--samples-per-m2", type=float, default=2.0)
    a = ap.parse_args()

    out = os.path.join(HERE, a.outdir)
    os.makedirs(out, exist_ok=True)
    blender = ensure_blender(os.path.join(HERE, "..", "blender"))
    print("blender:", blender, flush=True)

    n3 = os.path.join(out, "neuro3d.npz")
    normals = os.path.join(HERE, a.normals) if a.normals else ""
    sh([sys.executable, "neuro3d_irradiance.py", "--tile", a.tile, "--out", n3,
        *(["--normals", normals] if normals else []),
        "--lat", str(a.lat), "--lon", str(a.lon), "--hour-step", str(a.hour_step),
        "--device", a.device, "--texel", str(a.texel),
        "--samples-per-m2", str(a.samples_per_m2)])

    probes = os.path.join(out, "probes.npz")
    sh([sys.executable, "make_probes.py", "--tile", a.tile, "--neuro3d", n3,
        "--out", probes, "--n", str(a.probes)])

    ctl = os.path.join(out, "control_cycles.npz")
    cmd = [blender, "-b", "--factory-startup", "-P", "control_cycles.py", "--",
           "--tile", a.tile, "--probes", probes, "--out", ctl,
           "--lat", str(a.lat), "--lon", str(a.lon),
           "--hour-step", str(a.hour_step), "--samples", str(a.samples),
           "--device", a.cycles_device]
    if a.max_steps:
        cmd += ["--max-steps", str(a.max_steps)]
    sh(cmd)

    # Equal-load run: same scene, same directions, only the probe surfaces.
    eq = os.path.join(out, "neuro3d_equal_load.npz")
    sh([sys.executable, "neuro3d_irradiance.py", "--tile", a.tile, "--out", eq,
        *(["--normals", normals] if normals else []),
        "--only-index", probes,
        "--lat", str(a.lat), "--lon", str(a.lon), "--hour-step", str(a.hour_step),
        "--device", a.device, "--texel", str(a.texel),
        "--samples-per-m2", str(a.samples_per_m2)])
    import json as _json
    with open(n3 + ".meta.json", encoding="utf-8") as f:
        m = _json.load(f)
    with open(eq + ".meta.json", encoding="utf-8") as f:
        m["equal_load_seconds"] = _json.load(f)["light_transport_seconds"]
    with open(n3 + ".meta.json", "w", encoding="utf-8") as f:
        _json.dump(m, f, indent=2)

    sh([sys.executable, "compare.py", "--neuro3d", n3, "--control", ctl,
        "--probes", probes, "--out", os.path.join(out, "CONTRATO-001.json")])
    print("pilot done", flush=True)


if __name__ == "__main__":
    main()
