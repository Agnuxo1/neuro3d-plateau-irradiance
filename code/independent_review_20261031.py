"""Independent, CPU-only scientific checks for Neuro3D PLATEAU.

These checks are NEW analyses on published numerical artifacts, not a
reproduction of Cycles, not an independent held-out-city validation, and not
a replacement for the pre-registered accuracy verdict. The raw JSON and
script form an inspectable audit trail.

Tests
-----
A: Physical constraints / numerical integrity on all district faces.
B: Triangle-weighted versus surface-area-weighted exposure, for sensitivity
   to CityGML tessellation.
C: Stratified bootstrap uncertainty for the full 900-probe Cycles comparison.

Example:
    python code/independent_review_20261031.py \
        --engine ../results_v2/neuro3d.npz \
        --pairs ../results_v2/CONTRATO-001.json.pairs.npz \
        --output results/independent_review_20261031.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def sha256(path: Path) -> str:
    """Hash each numerical input to bind findings to immutable bytes."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def safe_float(value: float) -> float | None:
    """Return a JSON-safe finite scalar without hiding invalid arithmetic."""
    f = float(value)
    return f if np.isfinite(f) else None


def weighted_percentile(values: np.ndarray, weights: np.ndarray, q: float) -> float:
    """Return a finite-area-weighted percentile with deterministic sorting."""
    order = np.argsort(values, kind="stable")
    cumulative = np.cumsum(weights[order])
    return float(values[order][np.searchsorted(cumulative, q * cumulative[-1])])


def agreement(own: np.ndarray, control: np.ndarray) -> dict:
    """Evaluate the complete, original probe set with a 1 kWh ratio floor."""
    residual = own - control
    denominator = float(np.sum((control - control.mean()) ** 2))
    relative = np.abs(residual) / np.maximum(control, 1.0)
    return {
        "n": int(len(own)),
        "r2": safe_float(1.0 - float(np.sum(residual**2)) / denominator)
        if denominator > 0 else None,
        "mean_bias_fraction": safe_float(float(np.mean(residual) / np.mean(control)))
        if np.mean(control) != 0 else None,
        "median_absolute_error_kwh_m2_year": safe_float(np.median(np.abs(residual))),
        "median_relative_error": safe_float(np.median(relative)),
        "p95_relative_error": safe_float(np.percentile(relative, 95)),
    }


def analyse(engine_path: Path, pairs_path: Path, bootstrap: int, seed: int) -> dict:
    """Run three independent analytical probes without network or GPU access."""
    engine = np.load(engine_path)
    pairs = np.load(pairs_path)

    keep = np.asarray(engine["keep"], dtype=bool)
    per = np.asarray(engine["per_tri"], dtype=np.float64)
    direct, diffuse, open_direct, open_diffuse, svf, area = (
        per[:, 0], per[:, 1], per[:, 2], per[:, 3], per[:, 4], per[:, 5]
    )
    selected = np.flatnonzero(keep)
    valid = keep & np.isfinite(per[:, :6]).all(axis=1) & (area > 0)
    total = direct + diffuse

    # A — physically admissible and numerically stable outputs. Count every
    # violation; do not silently exclude nonfinite or zero-area kept faces.
    v = {
        "nonfinite_kept": int(np.sum(keep & ~np.isfinite(per[:, :6]).all(axis=1))),
        "nonpositive_area_kept": int(np.sum(keep & ~(area > 0))),
        "negative_direct_kept": int(np.sum(keep & (direct < -1e-6))),
        "negative_diffuse_kept": int(np.sum(keep & (diffuse < -1e-6))),
        "svf_outside_unit_kept": int(np.sum(keep & ((svf < -1e-6) | (svf > 1 + 1e-6)))),
        "irradiance_exceeds_unshaded_kept": int(np.sum(
            keep & (total > open_direct + open_diffuse + 1e-3)
        )),
    }
    physical = {
        "name": "A: Physical consistency on district triangles",
        "n_total_triangles": int(per.shape[0]),
        "n_kept_triangles": int(len(selected)),
        "n_finite_positive_area_triangles": int(np.sum(valid)),
        "violations": v,
        "pass": all(count == 0 for count in v.values()),
        "notes": "The comparison is internal to the clear-sky model. It does not establish agreement with measured weather.",
    }

    # B — the difference between triangle and m2 weighting is scientifically
    # material: triangle counts are not a substitute for a real surface area.
    y = total[valid]
    a = area[valid]
    sk = svf[valid]
    weights = a / np.sum(a)
    area_test = {
        "name": "B: Tessellation-weighting sensitivity",
        "n": int(len(y)),
        "computed_surface_area_m2": safe_float(np.sum(a)),
        "annual_irradiance_triangle_mean_kwh_m2": safe_float(np.mean(y)),
        "annual_irradiance_area_weighted_mean_kwh_m2": safe_float(np.dot(y, weights)),
        "annual_irradiance_area_weighted_median_kwh_m2": safe_float(
            weighted_percentile(y, a, .5)
        ),
        "sky_view_triangle_mean": safe_float(np.mean(sk)),
        "sky_view_area_weighted_mean": safe_float(np.dot(sk, weights)),
        "positive_irradiance_area_fraction": safe_float(
            np.sum(a[y > 1.0]) / np.sum(a)
        ),
        "interpretation": "Sensitivity check only: a change reflects uneven triangle areas, not a change in the engine's predictions.",
    }
    area_test["mean_weighting_shift_fraction"] = safe_float(
        area_test["annual_irradiance_area_weighted_mean_kwh_m2"] /
        area_test["annual_irradiance_triangle_mean_kwh_m2"] - 1
    ) if area_test["annual_irradiance_triangle_mean_kwh_m2"] else None

    # C — resampling preserves the observed semantic class proportions of
    # the 900 preselected probes. It is not a new random spatial test set.
    own = np.asarray(pairs["own"], dtype=np.float64)
    ctl = np.asarray(pairs["control"], dtype=np.float64)
    sem = np.asarray(pairs["sem"], dtype=np.int32)
    if len(own) != 900 or len(ctl) != len(own) or not np.isfinite(own).all() or not np.isfinite(ctl).all():
        raise ValueError("The expected finite 900-probe data are unavailable.")
    observed = agreement(own, ctl)
    rng = np.random.default_rng(seed)
    strata = [np.flatnonzero(sem == s) for s in np.unique(sem)]
    rows = []
    for _ in range(bootstrap):
        indices = np.concatenate([rng.choice(ix, size=len(ix), replace=True) for ix in strata])
        rows.append(agreement(own[indices], ctl[indices]))
    uncertainty = {
        "name": "C: Stratified bootstrap on original 900 Cycles probes",
        "seed": seed,
        "replicates": bootstrap,
        "probes": len(own),
        "strata_sizes": {str(int(s)): int(np.sum(sem == s)) for s in np.unique(sem)},
        "observed": observed,
        "ci95_percentile": {},
        "notes": "This estimates sample variability conditional on the existing stratified probes; it does NOT repair spatial dependence, systematic model bias or missing independent-city validation. The registered all-probes H1 verdict remains unchanged.",
    }
    for key in ("r2", "mean_bias_fraction", "median_absolute_error_kwh_m2_year",
                "median_relative_error", "p95_relative_error"):
        values = np.array([item[key] for item in rows], dtype=float)
        uncertainty["ci95_percentile"][key] = [
            safe_float(np.percentile(values, 2.5)),
            safe_float(np.percentile(values, 97.5)),
        ]

    return {
        "audit": "Independent analytical checks, 2026-10-31",
        "scope": "CPU-only post-hoc audit on previously generated results",
        "inputs": {
            str(engine_path): sha256(engine_path),
            str(pairs_path): sha256(pairs_path),
        },
        "tests": [physical, area_test, uncertainty],
        "preregistered_H1_verdict": "NOT MET on all 900 probes; this script does not alter the pre-registered protocol.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", required=True, type=Path)
    parser.add_argument("--pairs", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--bootstrap", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20261031)
    args = parser.parse_args()
    if args.bootstrap < 100:
        raise ValueError("At least 100 bootstrap replicates are required.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = analyse(args.engine, args.pairs, args.bootstrap, args.seed)
    with args.output.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
