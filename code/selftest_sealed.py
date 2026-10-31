"""Analytic self-tests for the sealed-face detectors. No data needed.

Real CityGML tiles contain volumes inside other volumes, and a face sealed
inside one receives no light. Two detectors answer that question:

    buried_faces      vertical parity, upwards and downwards
    sealed_faces_3d   parity along six axis directions plus the face normal,
                      sealed when at least five of the seven are odd

The three cases below have a known answer, so they pin the behaviour of both,
including the case that motivated the second one: an enclosing volume whose
roof is missing, which is common in CityGML and which the vertical test cannot
resolve.

    python selftest_sealed.py
"""

from __future__ import annotations

import sys

import numpy as np

from orient_normals import buried_faces, sealed_faces_3d


def box(lo, hi, with_top=True):
    """Axis-aligned box as triangles wound counter-clockwise from outside."""
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    v = {
        "-x": [(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)],
        "+x": [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)],
        "-y": [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)],
        "+y": [(x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0)],
        "-z": [(x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0)],
        "+z": [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)],
    }
    if not with_top:
        del v["+z"]
    tri = []
    for quad in v.values():
        a, b, c, d = (np.asarray(p, float) for p in quad)
        tri += [[a, b, c], [a, c, d]]
    return np.asarray(tri, float)


def normals(tri):
    e1 = tri[:, 1] - tri[:, 0]
    e2 = tri[:, 2] - tri[:, 0]
    n = np.cross(e1, e2)
    return n / np.linalg.norm(n, axis=1, keepdims=True)


def scene(outer_kwargs, inner_lo, inner_hi, outer_lo=(-20, -20, 0),
          outer_hi=(20, 20, 20)):
    a = box(outer_lo, outer_hi, **outer_kwargs)
    b = box(inner_lo, inner_hi)
    tri = np.concatenate([a, b])
    bldg = np.concatenate([np.zeros(len(a), np.int32),
                           np.ones(len(b), np.int32)])
    return tri, normals(tri), bldg, len(a)


def check(name, got, want, report):
    ok = got == want
    report.append((name, got, want, ok))
    print(f"  {'ok ' if ok else 'FAIL'}  {name}: got {got}, expected {want}")
    return ok


def main() -> int:
    report: list = []
    good = True

    print("T1  a closed box inside a closed box")
    tri, n, bldg, na = scene({}, (-5, -5, 2), (5, 5, 12))
    nb = len(tri) - na
    v = buried_faces(tri, n, bldg)
    s = sealed_faces_3d(tri, n, bldg)
    good &= check("vertical finds every inner face", int(v[na:].sum()), nb, report)
    good &= check("3-D finds every inner face", int(s[na:].sum()), nb, report)
    good &= check("3-D flags no outer face", int(s[:na].sum()), 0, report)

    print("T2  the same, with the enclosing box's roof missing")
    tri, n, bldg, na = scene({"with_top": False}, (-5, -5, 2), (5, 5, 12))
    nb = len(tri) - na
    v = buried_faces(tri, n, bldg)
    s = sealed_faces_3d(tri, n, bldg)
    good &= check("vertical finds none, because upward parity is even",
                  int(v[na:].sum()), 0, report)
    good &= check("3-D still finds every inner face",
                  int(s[na:].sum()), nb, report)
    good &= check("3-D flags no outer face", int(s[:na].sum()), 0, report)

    print("T3  a box sealed inside the SAME building's own volume")
    a = box((-20, -20, 0), (20, 20, 20))
    b = box((-5, -5, 2), (5, 5, 12))
    tri = np.concatenate([a, b])
    n = normals(tri)
    bldg = np.zeros(len(tri), np.int32)      # one single building
    good &= check("vertical sees nothing, it skips the own building",
                  int(buried_faces(tri, n, bldg).sum()), 0, report)
    good &= check("3-D finds the inner 12 faces",
                  int(sealed_faces_3d(tri, n, bldg)[len(a):].sum()), 12, report)
    good &= check("3-D flags no outer face",
                  int(sealed_faces_3d(tri, n, bldg)[:len(a)].sum()), 0, report)

    print("T4  two boxes far apart: nothing is sealed")
    a = box((-20, -20, 0), (20, 20, 20))
    b = box((200, 200, 0), (210, 210, 10))
    tri = np.concatenate([a, b])
    n = normals(tri)
    bldg = np.concatenate([np.zeros(len(a), np.int32),
                           np.ones(len(b), np.int32)])
    good &= check("vertical flags nothing",
                  int(buried_faces(tri, n, bldg).sum()), 0, report)
    good &= check("3-D flags nothing",
                  int(sealed_faces_3d(tri, n, bldg).sum()), 0, report)

    print("\nVERIFIED" if good else "\nFAILED")
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
