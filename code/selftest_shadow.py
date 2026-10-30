"""Analytic self-tests of the shadow-map core, independent of PLATEAU data.

T1  An unobstructed horizontal surface has sky view factor 1.
T2  A horizontal surface at the foot of a tall opaque wall has sky view factor
    0.5 within tolerance: an infinite wall blocks half the hemisphere.
T3  A ground point in the shadow of a closed box sees no sun; points beside it,
    south of it and on its roof are lit.
T4  Sky view factor at the centre of a square courtyard of side 2h and wall
    height h, against the analytic value for that configuration.

Run: python selftest_shadow.py
"""

from __future__ import annotations

import numpy as np
import torch

import solar
from neuro3d_irradiance import DirectionalShadow, sample_points, slope_bias

TEX = 0.5
BIAS = 0.05
FAILS: list[str] = []


def check(name: str, got: float, expect: float, tol: float) -> None:
    ok = abs(got - expect) <= tol
    print(f"{'PASS' if ok else 'FAIL'} {name}: got {got:.4f}, expected "
          f"{expect:.4f} +- {tol}")
    if not ok:
        FAILS.append(name)


def quad(p0, p1, p2, p3):
    return np.array([[p0, p1, p2], [p0, p2, p3]], np.float32)


def normals_of(tri):
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    return n / np.linalg.norm(n, axis=1, keepdims=True)


def build(tri, outward_from=None, per_m2=6.0):
    """Splat a scene; normals are flipped to point away from `outward_from`."""
    n = normals_of(tri)
    if outward_from is not None:
        c = tri.mean(axis=1)
        v = c - np.asarray(outward_from, np.float32)
        v[:, 2] = 0.0
        flip = (n * v).sum(1) < 0
        n[flip] *= -1.0
    pts, idx = sample_points(tri, per_m2, with_index=True)
    return DirectionalShadow(torch.from_numpy(pts), TEX,
                             torch.from_numpy(n[idx].astype(np.float32)))


def svf(shadow, q, n, dirs, omega):
    q_t = torch.from_numpy(q.astype(np.float32))
    n_t = torch.from_numpy(n.astype(np.float32))
    num = torch.zeros(len(q))
    den = torch.zeros(len(q))
    for j in range(len(dirs)):
        d = torch.tensor(dirs[j], dtype=torch.float32)
        cosi = (n_t @ d).clamp(min=0.0)
        if float(cosi.max()) <= 0:
            continue
        vis = shadow.visible(d, q_t, BIAS,
                             front_bias=slope_bias(cosi, TEX, BIAS))
        num += cosi * float(omega[j]) * vis
        den += cosi * float(omega[j])
    return (num / den.clamp(min=1e-9)).numpy()


def main() -> None:
    dirs, omega = solar.tregenza_patches()
    ground = quad([-150, -150, 0], [150, -150, 0], [150, 150, 0], [-150, 150, 0])
    up = np.array([[0.0, 0.0, 1.0]], np.float32)

    sh = build(ground, per_m2=2.0)
    q = np.array([[0.0, 0.0, 0.05], [30.0, -20.0, 0.05]], np.float32)
    check("T1 bare ground", float(svf(sh, q, np.repeat(up, 2, 0), dirs, omega).mean()),
          1.0, 0.02)

    # T2: a 100 m tall wall of 300 m length at x = 0, modelled with both faces
    # so that it is a closed obstacle.
    w1 = quad([0, -150, 0], [0, 150, 0], [0, 150, 100], [0, -150, 100])
    w2 = quad([0, 150, 0], [0, -150, 0], [0, -150, 100], [0, 150, 100])
    scene = np.concatenate([ground, w1, w2])
    n = normals_of(scene)
    n[2:4] = [1.0, 0.0, 0.0]
    n[4:6] = [-1.0, 0.0, 0.0]
    pts, idx = sample_points(scene, 6.0, with_index=True)
    sh = DirectionalShadow(torch.from_numpy(pts), TEX,
                           torch.from_numpy(n[idx].astype(np.float32)))
    q = np.array([[1.0, 0.0, 0.05], [2.0, 10.0, 0.05], [1.5, -10.0, 0.05]], np.float32)
    check("T2 foot of a tall wall",
          float(svf(sh, q, np.repeat(up, 3, 0), dirs, omega).mean()), 0.5, 0.06)

    # T3: a closed 20 x 20 x 40 m box on the ground, sun 30 degrees in the south.
    box = []
    corners = [(-10, -10), (10, -10), (10, 10), (-10, 10)]
    for a, b in zip(corners, corners[1:] + corners[:1]):
        box.append(quad([a[0], a[1], 0], [b[0], b[1], 0],
                        [b[0], b[1], 40], [a[0], a[1], 40]))
    box.append(quad([-10, -10, 40], [10, -10, 40], [10, 10, 40], [-10, 10, 40]))
    scene = np.concatenate([ground] + box)
    sh = build(scene, outward_from=[0.0, 0.0, 0.0], per_m2=6.0)
    alt = np.radians(30.0)
    d = torch.tensor([0.0, -np.cos(alt), np.sin(alt)], dtype=torch.float32)
    q = np.array([[0.0, 30.0, 0.05],    # inside the shadow (reaches ~69 m)
                  [0.0, 95.0, 0.05],    # beyond the shadow
                  [0.0, -30.0, 0.05],   # south of the box
                  [0.0, 0.0, 40.05]],   # the roof
                 np.float32)
    q_t = torch.from_numpy(q)
    cosd = torch.from_numpy(np.repeat(up, 4, 0)) @ d
    vis = sh.visible(d, q_t, BIAS,
                     front_bias=slope_bias(cosd, TEX, BIAS)).numpy().astype(float)
    check("T3 shadow north of the box", vis[0], 0.0, 0.0)
    check("T3 lit beyond the shadow", vis[1], 1.0, 0.0)
    check("T3 lit south of the box", vis[2], 1.0, 0.0)
    check("T3 lit roof", vis[3], 1.0, 0.0)

    # T4: square courtyard, walls of height h, courtyard side 2h. At the centre
    # of the floor the sky is visible above the elevation theta0(phi) given by
    # tan(theta0) = max(|cos phi|, |sin phi|), so the cosine-weighted sky view
    # factor is the mean of cos^2(theta0) = 1/(1+tan^2 theta0) over phi. Using
    # the eight-fold symmetry, that mean is
    #     (4/pi) * integral_0^{pi/4} dphi / (1 + cos^2 phi)
    #   = (4/pi) * (1/sqrt 2) * arctan(1/sqrt 2) = 0.5536.
    h = 20.0
    cy = []
    cc = [(-h, -h), (h, -h), (h, h), (-h, h)]
    for a, b in zip(cc, cc[1:] + cc[:1]):
        cy.append(quad([a[0], a[1], 0], [b[0], b[1], 0],
                       [b[0], b[1], h], [a[0], a[1], h]))
    scene = np.concatenate([ground] + cy)
    n = normals_of(scene)
    c = scene.mean(axis=1)
    v = c.copy(); v[:, 2] = 0.0
    flip = (n * (-v)).sum(1) < 0           # courtyard walls face inwards
    n[2:][flip[2:]] *= -1.0
    pts, idx = sample_points(scene, 6.0, with_index=True)
    sh = DirectionalShadow(torch.from_numpy(pts), TEX,
                           torch.from_numpy(n[idx].astype(np.float32)))
    q = np.array([[0.0, 0.0, 0.05]], np.float32)
    check("T4 centre of a square courtyard", float(svf(sh, q, up, dirs, omega)[0]),
          0.5536, 0.05)

    print("\nFAILURES:", FAILS if FAILS else "none")
    raise SystemExit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
