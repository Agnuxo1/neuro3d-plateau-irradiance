"""Rooftop solar ranking: the engine's output turned into a municipal shortlist.

A planning office does not want a field of numbers, it wants the list of roofs
worth surveying first. This takes the per-surface annual irradiance and
aggregates it per building over the roof surfaces that a panel could actually
use, then estimates the annual generation under assumptions that are printed
with the result and are easy to change.

    annual generation [kWh/yr] = area * irradiance * module efficiency
                                 * performance ratio

Nothing here is a measurement of a real installation: it is the engine's
irradiance multiplied by two stated constants. The CSV keeps both the raw
irradiance and the estimate so a reader can apply their own constants.

    python rooftop_report.py --tile tile.npz --neuro3d neuro3d.npz \
        --out results/rooftop_top.csv --json web/rooftop.json
"""

from __future__ import annotations

import argparse
import csv
import json
import os

import numpy as np

EFFICIENCY = 0.20      # module efficiency, typical crystalline silicon
PERF_RATIO = 0.80      # performance ratio: wiring, inverter, temperature, soiling
MIN_TILT_COS = 0.70    # a roof facet flatter than about 45 degrees
MIN_AREA = 20.0        # a building needs this much usable roof to be worth listing


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tile", required=True)
    ap.add_argument("--neuro3d", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--json", default="")
    ap.add_argument("--top", type=int, default=100)
    ap.add_argument("--efficiency", type=float, default=EFFICIENCY)
    ap.add_argument("--performance-ratio", type=float, default=PERF_RATIO)
    a = ap.parse_args()

    d = np.load(a.tile)
    n3 = np.load(a.neuro3d)
    per, keep, nrm, cen = n3["per_tri"], n3["keep"], n3["normals"], n3["centroid"]
    sem, bldg = n3["sem"], d["tri_bldg"]
    ids = d["bldg_id"]
    area = per[:, 5]
    annual = per[:, 0] + per[:, 1]

    usable = keep & (sem == 2) & (nrm[:, 2] >= MIN_TILT_COS) & (area > 0)
    print(f"roof facets usable for panels: {int(usable.sum()):,} "
          f"of {int((keep & (sem == 2)).sum()):,} roof facets")

    rows = []
    for b in np.unique(bldg[usable]):
        m = usable & (bldg == b)
        ar = float(area[m].sum())
        if ar < MIN_AREA:
            continue
        irr = float((annual[m] * area[m]).sum() / ar)   # area-weighted
        rows.append({
            "building_id": str(ids[b]) if b < len(ids) else str(b),
            "usable_roof_area_m2": round(ar, 1),
            "mean_annual_irradiance_kwh_m2": round(irr, 1),
            "estimated_annual_kwh": round(ar * irr * a.efficiency
                                          * a.performance_ratio, 0),
            "roof_facets": int(m.sum()),
            "east_m": round(float(cen[m][:, 0].mean()), 1),
            "north_m": round(float(cen[m][:, 1].mean()), 1),
            "height_m": round(float(cen[m][:, 2].max()), 1),
        })
    rows.sort(key=lambda r: -r["estimated_annual_kwh"])
    top = rows[:a.top]

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(top[0].keys()))
        w.writeheader()
        w.writerows(top)

    total = sum(r["estimated_annual_kwh"] for r in rows)
    summary = {
        "assumptions": {
            "module_efficiency": a.efficiency,
            "performance_ratio": a.performance_ratio,
            "min_roof_tilt_cos": MIN_TILT_COS,
            "min_usable_area_m2": MIN_AREA,
            "note": "clear-sky irradiance from the engine, not measured "
                    "weather and not a site survey",
        },
        "buildings_listed": len(rows),
        "usable_roof_area_m2": round(sum(r["usable_roof_area_m2"]
                                         for r in rows), 0),
        "district_estimated_annual_kwh": round(total, 0),
        "district_estimated_annual_mwh": round(total / 1000.0, 1),
        "top": top[:20],
    }
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)), exist_ok=True)
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=1)
    print(json.dumps({k: v for k, v in summary.items() if k != "top"},
                     indent=2))
    print(f"wrote {a.out} ({len(top)} rows)")


if __name__ == "__main__":
    main()
