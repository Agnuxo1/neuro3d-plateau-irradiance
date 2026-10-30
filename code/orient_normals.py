"""Geometry preprocessing: outward normals for a tile, written once.

Separated from the light-transport engine so that the timed part of the run
contains only light transport, and so that the engine does not need extra
dependencies on the machine where it runs.

Method: ray parity against the building's own triangles. A ray leaving a face
along its normal crosses the rest of that building an even number of times if
the normal already points outwards, and an odd number of times if it points
into the solid. This is correct for concave plans, inner courtyards and
overhangs, where a footprint test is not. Buildings that are not closed can
still come out wrong, so the semantic classes are used as a prior (roofs point
up, ground slabs point down) and the count of faces flipped is reported.
"""

from __future__ import annotations

import argparse
import time

import numpy as np

from neuro3d_irradiance import triangle_frames


def ray_triangle_count(orig: np.ndarray, dirs: np.ndarray, tri: np.ndarray,
                       skip: np.ndarray, eps: float = 1e-7) -> np.ndarray:
    """Count forward intersections of each ray with every triangle in `tri`.

    Möller-Trumbore, fully vectorised over (rays, triangles). `skip[i, j]` is
    True where ray i must ignore triangle j (its own face).
    """
    v0, v1, v2 = tri[:, 0], tri[:, 1], tri[:, 2]
    e1 = (v1 - v0)[None, :, :]
    e2 = (v2 - v0)[None, :, :]
    d = dirs[:, None, :]
    pv = np.cross(d, e2)
    det = (e1 * pv).sum(-1)
    ok = np.abs(det) > eps
    inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
    tvec = orig[:, None, :] - v0[None, :, :]
    u = (tvec * pv).sum(-1) * inv
    qv = np.cross(tvec, e1)
    v = (d * qv).sum(-1) * inv
    t = (e2 * qv).sum(-1) * inv
    hit = ok & (u >= -1e-6) & (v >= -1e-6) & (u + v <= 1 + 1e-6) & (t > 1e-4)
    hit &= ~skip
    return hit.sum(1)


def orient_outward_parity(tri: np.ndarray, n: np.ndarray, sem: np.ndarray,
                          bldg: np.ndarray, max_faces: int = 4000):
    n = n.copy()
    n[(sem == 2) & (n[:, 2] < 0)] *= -1.0
    n[(sem == 0) & (n[:, 2] > 0)] *= -1.0
    c = tri.mean(axis=1)
    flipped = 0
    skipped_big = 0
    for b in np.unique(bldg):
        m = np.nonzero(bldg == b)[0]
        if len(m) > max_faces:
            skipped_big += 1
            continue
        sub = tri[m]
        # Only the faces whose orientation is not fixed by semantics.
        q = np.nonzero(np.isin(sem[m], (1, 3)))[0]
        if not len(q):
            continue
        orig = c[m][q] + n[m][q] * 1e-3
        skip = np.zeros((len(q), len(m)), bool)
        skip[np.arange(len(q)), q] = True
        cnt = ray_triangle_count(orig, n[m][q], sub, skip)
        bad = (cnt % 2) == 1
        if bad.any():
            n[m[q[bad]]] *= -1.0
            flipped += int(bad.sum())
    return n, flipped, skipped_big


def buried_faces(tri: np.ndarray, n: np.ndarray, bldg: np.ndarray,
                 offset: float = 0.30, radius: float = 60.0):
    """Faces whose outward side lies inside another building's solid.

    Real CityGML tiles contain overlapping and nested volumes: a facet of one
    building can sit inside the volume of its neighbour, or inside the
    `lod1Solid` of the same block. Such a facet receives no light, and a path
    tracer reports zero there. A shadow map with front-face culling cannot see
    it, because the enclosing faces are lit faces. Those surfaces are therefore
    detected here, once, and excluded.

    Detection is ray parity along the outward normal against the triangles of
    the neighbouring buildings only (their bounding box within `radius`), which
    keeps the test local and cheap.
    """
    c = tri.mean(axis=1) + n * offset
    ids = np.unique(bldg)
    boxes = {}
    for b in ids:
        m = bldg == b
        v = tri[m].reshape(-1, 3)
        boxes[b] = (v.min(0), v.max(0), np.nonzero(m)[0])
    buried = np.zeros(len(tri), bool)
    centres = np.array([(boxes[b][0] + boxes[b][1]) / 2 for b in ids])
    up = np.tile(np.array([0.0, 0.0, 1.0]), (1, 1))
    for b in ids:
        lo, hi, faces = boxes[b]
        near = ids[(np.abs(centres[:, 0] - (lo[0] + hi[0]) / 2) < radius)
                   & (np.abs(centres[:, 1] - (lo[1] + hi[1]) / 2) < radius)
                   & (ids != b)]
        if not len(near):
            continue
        other = np.concatenate([boxes[o][2] for o in near])
        sub = tri[other]
        q = c[faces]
        dirs = np.tile(up, (len(q), 1))
        skip = np.zeros((len(q), len(sub)), bool)
        cnt = ray_triangle_count(q, dirs, sub, skip)
        down = ray_triangle_count(q, -dirs, sub, skip)
        buried[faces] = ((cnt % 2) == 1) & ((down % 2) == 1)
    return buried


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tile", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    d = np.load(a.tile)
    tri = d["tri"].astype(np.float64)
    t0 = time.time()
    _, n, _ = triangle_frames(tri)
    n, flipped, big = orient_outward_parity(tri, n, d["tri_sem"], d["tri_bldg"])
    t1 = time.time()
    buried = buried_faces(tri, n, d["tri_bldg"])
    np.savez_compressed(a.out, normals=n.astype(np.float32),
                        buried=buried,
                        fallback_buildings=np.int32(big),
                        flipped_faces=np.int32(flipped))
    print(f"normals={len(n)} flipped={flipped} buildings_skipped={big} "
          f"buried={int(buried.sum())} ({time.time()-t0:.1f} s, "
          f"buried test {time.time()-t1:.1f} s)")


if __name__ == "__main__":
    main()
