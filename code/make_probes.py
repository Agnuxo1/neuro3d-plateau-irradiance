"""Choose the probe surfaces on which the Cycles control is evaluated.

The own engine computes every triangle of the district; the path-traced control
is far too slow for that, so it is evaluated on a stratified sample of
triangles. Stratification is by semantic class (roof, wall, ground) and by
height, so the sample is not dominated by the many small wall facets near the
ground.
"""

from __future__ import annotations

import argparse

import numpy as np


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tile", required=True)
    ap.add_argument("--neuro3d", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--n", type=int, default=900)
    ap.add_argument("--min-area", type=float, default=4.0)
    ap.add_argument("--offset", type=float, default=0.30)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    n3 = np.load(a.neuro3d)
    per = n3["per_tri"]
    nrm = n3["normals"]
    cen = n3["centroid"]
    sem = n3["sem"]
    keep = n3["keep"]
    area = per[:, 5]

    # Downward faces (building bottom slabs, LOD1 prism bottoms) receive
    # nothing by construction and are not a target for solar potential, so they
    # are not part of the validation set.
    ok = keep & (area >= a.min_area) & (nrm[:, 2] > -0.5) & (sem != 0)
    # A probe quad of 1 m side must fit inside its triangle's neighbourhood and
    # must not be a near-vertical sliver, so very thin triangles are dropped.
    idx_all = np.nonzero(ok)[0]
    rng = np.random.default_rng(a.seed)

    z = cen[:, 2]
    strata = []
    for s in (1, 2, 3):
        sel = idx_all[sem[idx_all] == s]
        if len(sel) == 0:
            continue
        # Three height bands inside each semantic class.
        qs = np.quantile(z[sel], [0.0, 1 / 3, 2 / 3, 1.0])
        for lo, hi in zip(qs[:-1], qs[1:]):
            band = sel[(z[sel] >= lo) & (z[sel] <= hi)]
            if len(band):
                strata.append(band)

    per_stratum = max(1, a.n // max(1, len(strata)))
    chosen: list[int] = []
    for band in strata:
        take = min(per_stratum, len(band))
        chosen.extend(rng.choice(band, size=take, replace=False).tolist())
    chosen = np.unique(np.asarray(chosen, np.int64))
    if len(chosen) > a.n:
        chosen = rng.choice(chosen, size=a.n, replace=False)
    chosen.sort()

    centres = cen[chosen] + nrm[chosen] * a.offset
    np.savez_compressed(a.out, index=chosen, centres=centres.astype(np.float32),
                        normals=nrm[chosen].astype(np.float32),
                        sem=sem[chosen], area=area[chosen])
    import collections
    print(f"probes={len(chosen)} by class={dict(collections.Counter(sem[chosen].tolist()))} "
          f"z={centres[:,2].min():.1f}..{centres[:,2].max():.1f} m")


if __name__ == "__main__":
    main()
