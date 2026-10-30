"""Independent ray-level diagnostic of a disagreement between the engines.

Run with Blender, which supplies a BVH over the same triangles:

    blender -b --factory-startup -P diag_rays.py -- --tile ... --probes ...
            --control ... --neuro3d ...

For every probe where the two engines disagree, it reports how many sky
directions are actually blocked by the tile geometry, so the blame can be
assigned to one engine instead of guessed.
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import solar  # noqa: E402

import mathutils  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tile", required=True)
    ap.add_argument("--probes", required=True)
    ap.add_argument("--control", required=True)
    ap.add_argument("--neuro3d", required=True)
    ap.add_argument("--max", type=int, default=20)
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])

    tile = np.load(a.tile)
    tri = tile["tri"].astype(np.float64)
    verts = [mathutils.Vector(v) for v in tri.reshape(-1, 3)]
    faces = [(i, i + 1, i + 2) for i in range(0, len(verts), 3)]
    bvh = BVHTree.FromPolygons(verts, faces, all_triangles=True)

    pr = np.load(a.probes)
    ctl = np.load(a.control)
    n3 = np.load(a.neuro3d)
    per = n3["per_tri"]
    idx = pr["index"]
    ref = ctl["kwh"]
    own = per[idx, 0] + per[idx, 1]
    dirs, omega = solar.tregenza_patches()

    rel = np.abs(own - ref) / np.maximum(ref, 1.0)
    order = np.argsort(-rel)[: a.max]
    print(f"{'tri':>7} {'sem':>3} {'own':>8} {'control':>8} {'svf_own':>7} "
          f"{'blocked':>9} {'svf_rays':>8}")
    for i in order:
        c = pr["centres"][i].astype(float)
        nn = pr["normals"][i].astype(float)
        sel = dirs[dirs @ nn > 1e-3]
        om = omega[dirs @ nn > 1e-3]
        cos = sel @ nn
        blocked = np.zeros(len(sel), bool)
        for k, d in enumerate(sel):
            hit = bvh.ray_cast(mathutils.Vector(c + d * 0.02),
                               mathutils.Vector(d), 2000.0)
            blocked[k] = hit[0] is not None
        svf_rays = float((cos * om * ~blocked).sum() / (cos * om).sum())
        print(f"{idx[i]:7d} {pr['sem'][i]:3d} {own[i]:8.1f} {ref[i]:8.1f} "
              f"{per[idx[i], 4]:7.2f} {blocked.sum():4d}/{len(sel):<4d} "
              f"{svf_rays:8.2f}")


if __name__ == "__main__":
    main()
