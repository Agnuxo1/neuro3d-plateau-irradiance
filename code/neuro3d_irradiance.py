"""Neuro3D urban irradiance: the GPU computes the light, the city is the scene.

The Neuro3D principle in this project is that the expensive part of the physics
is evaluated the way a 3D engine evaluates light: as a rasterisation pass over
the whole scene at once, in parallel on the GPU, rather than as per-ray queries
on the CPU.

Here that principle is applied to urban solar irradiance on PLATEAU LOD2
geometry. For every light direction (the sun at each time step, and each patch
of a 145-patch Tregenza sky dome) the scene is splatted into one orthographic
depth buffer aligned with that direction, and the whole set of query points is
tested against the buffer in a single vectorised comparison. One direction
costs one scatter-reduce plus one gather, independent of how many surfaces are
occluding.

Outputs per triangle: annual clear-sky irradiation (kWh/m2/yr), separated into
beam and diffuse, plus the unobstructed value and the sky view factor, so the
effect of the surrounding city is explicit.
"""

from __future__ import annotations

import argparse
import json
import os
import time

import numpy as np
import torch

import solar


def triangle_frames(tri: np.ndarray):
    v0, v1, v2 = tri[:, 0], tri[:, 1], tri[:, 2]
    n = np.cross(v1 - v0, v2 - v0)
    area = 0.5 * np.linalg.norm(n, axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        n = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    c = tri.mean(axis=1)
    return c, n, area


def orient_outward(tri: np.ndarray, n: np.ndarray, sem: np.ndarray,
                   bldg: np.ndarray, eps: float = 0.5) -> tuple[np.ndarray, int]:
    """Point every normal towards the outside of its building.

    CityGML rings are counter-clockwise seen from outside, but real tiles
    contain inverted rings, and a wall whose normal points into the solid
    receives no light at all, which would silently bias the whole map.

    Roofs and ground slabs are fixed by their semantic class. Every other
    surface is fixed geometrically: the centroid is displaced by `eps` along
    the normal and tested against the footprint of its own building. If the
    displaced point falls inside the footprint, the normal pointed inwards and
    is flipped. Buildings whose footprint cannot be built (no usable ground or
    roof ring) fall back to pointing away from the building's centroid; their
    count is returned so the report can state it.
    """
    import shapely
    from shapely.geometry import MultiPoint, Polygon
    from shapely.ops import unary_union

    n = n.copy()
    n[(sem == 2) & (n[:, 2] < 0)] *= -1.0
    n[(sem == 0) & (n[:, 2] > 0)] *= -1.0

    c = tri.mean(axis=1)
    fallback = 0
    side = np.isin(sem, (1, 3))
    for b in np.unique(bldg[side]):
        mask_b = bldg == b
        base = mask_b & np.isin(sem, (0, 2))
        polys = []
        if base.any():
            for t in tri[base]:
                p = Polygon(t[:, :2])
                if p.is_valid and p.area > 1e-6:
                    polys.append(p)
        shape = unary_union(polys).buffer(0.05) if polys else None
        if shape is None or shape.is_empty:
            pts = tri[mask_b].reshape(-1, 3)[:, :2]
            shape = MultiPoint(pts).convex_hull.buffer(0.05)
            fallback += 1
        idx = np.nonzero(mask_b & side & (np.abs(n[:, 2]) < 0.8))[0]
        if not len(idx):
            continue
        q = c[idx] + n[idx] * eps
        inside = shapely.contains_xy(shape, q[:, 0], q[:, 1])
        n[idx[inside]] *= -1.0
    return n, fallback


def sample_points(tri: np.ndarray, per_m2: float, seed: int = 0,
                  with_index: bool = False):
    """Area-proportional barycentric samples of every triangle."""
    rng = np.random.default_rng(seed)
    v0, v1, v2 = tri[:, 0], tri[:, 1], tri[:, 2]
    area = 0.5 * np.linalg.norm(np.cross(v1 - v0, v2 - v0), axis=1)
    k = np.maximum(1, np.round(area * per_m2).astype(np.int64))
    idx = np.repeat(np.arange(len(tri)), k)
    u = rng.random(len(idx))
    v = rng.random(len(idx))
    flip = u + v > 1.0
    u[flip], v[flip] = 1.0 - u[flip], 1.0 - v[flip]
    p = (v0[idx] + (v1[idx] - v0[idx]) * u[:, None] + (v2[idx] - v0[idx]) * v[:, None])
    if with_index:
        return p.astype(np.float32), idx
    return p.astype(np.float32)


def slope_bias(cos_i: torch.Tensor, texel: float, base: float, k: float = 2.5):
    """Per-point depth bias for a surface seen at incidence cos_i."""
    c = cos_i.clamp(min=0.05)
    return base + k * texel * torch.sqrt((1.0 - c * c).clamp(min=0.0)) / c


class DirectionalShadow:
    """Two orthographic depth buffers of a point-splatted scene, on the GPU.

    The scene is splatted twice per light direction, separated by facing:

    * the **back** buffer holds the faces turned away from the light. A ray that
      leaves a lit surface towards the light and hits a closed solid always
      *enters* through such a face, and a lit query surface is never in this
      buffer, so it can be tested with an exact, tiny bias and never shadows
      itself. This is what resolves ordinary urban shadowing.
    * the **front** buffer holds the lit faces. It is what reveals a surface
      sealed inside a volume — overlapping or nested CityGML solids, an inner
      shaft — because the face through which the ray would *leave* that volume
      is a lit face. A query surface does appear in this buffer, so it is
      tested with a slope-scaled bias large enough to cover the depth spread of
      its own plane inside one texel. Enclosure at a distance is caught;
      occlusion closer than that bias, in near-grazing directions, is not.
    """

    def __init__(self, pts: torch.Tensor, texel: float,
                 pt_normals: torch.Tensor | None = None):
        self.pts = pts
        self.nrm = pt_normals
        self.texel = texel
        self.lo = pts.min(0).values - 2.0 * texel
        self.hi = pts.max(0).values + 2.0 * texel
        self.diag = float(torch.linalg.norm(self.hi - self.lo))

    def _basis(self, d: torch.Tensor):
        up = torch.tensor([0.0, 0.0, 1.0], device=d.device, dtype=d.dtype)
        if abs(float(d[2])) > 0.9:
            up = torch.tensor([0.0, 1.0, 0.0], device=d.device, dtype=d.dtype)
        u = torch.cross(up, d, dim=0)
        u = u / torch.linalg.norm(u)
        v = torch.cross(d, u, dim=0)
        return u, v

    def visible(self, d: torch.Tensor, q: torch.Tensor, bias, neigh: int = 0,
                cull: bool = True, front_bias=None):
        """Binary visibility of query points q along direction d.

        `bias` applies to the back buffer and may be a scalar or a per-point
        tensor. `front_bias`, when given, enables the front-buffer test for
        enclosure with its own (larger) per-point bias. `cull=False` falls back
        to one single-buffer test over all faces, used only for diagnostics.
        """
        u, v = self._basis(d)
        pu = self.pts @ u
        pv = self.pts @ v
        pd = self.pts @ d
        lo_u, lo_v = pu.min(), pv.min()
        nu = int(torch.ceil((pu.max() - lo_u) / self.texel).item()) + 1
        nv = int(torch.ceil((pv.max() - lo_v) / self.texel).item()) + 1
        iu = ((pu - lo_u) / self.texel).long().clamp_(0, nu - 1)
        iv = ((pv - lo_v) / self.texel).long().clamp_(0, nv - 1)
        flat = iu * nv + iv
        facing = (self.nrm @ d) if self.nrm is not None else None
        ninf = torch.full_like(pd, -1e30)

        def buffer(depths: torch.Tensor) -> torch.Tensor:
            buf = torch.full((nu * nv,), -1e30, device=d.device,
                             dtype=self.pts.dtype)
            buf.scatter_reduce_(0, flat, depths, reduce="amax", include_self=True)
            return buf

        back = buffer(torch.where(facing < -1e-4, pd, ninf)
                      if (facing is not None and cull) else pd)
        front = (buffer(torch.where(facing > 1e-4, pd, ninf))
                 if (facing is not None and cull and front_bias is not None)
                 else None)

        qu = ((q @ u - lo_u) / self.texel).long().clamp_(0, nu - 1)
        qv = ((q @ v - lo_v) / self.texel).long().clamp_(0, nv - 1)
        qd = q @ d
        # `neigh` sets the lookup radius in texels. Zero is the honest default:
        # a wider lookup dilates every shadow by that many texels, which on a
        # dense LOD2 city removes real sunlight. Holes in the buffer are
        # controlled with the splat density instead.
        occl = torch.zeros_like(qd, dtype=torch.bool)
        rng = range(-neigh, neigh + 1)
        for du in rng:
            for dv in rng:
                f = (qu + du).clamp(0, nu - 1) * nv + (qv + dv).clamp(0, nv - 1)
                occl |= back[f] > qd + bias
                if front is not None:
                    occl |= front[f] > qd + front_bias
        return ~occl


def run(args) -> dict:
    dev = torch.device(args.device)
    data = np.load(args.tile)
    tri = data["tri"].astype(np.float32)
    sem = data["tri_sem"]
    c, n, area = triangle_frames(tri)
    buried = np.zeros(len(tri), bool)
    t_or = time.time()
    if args.normals:
        nz = np.load(args.normals)
        n = nz["normals"].astype(np.float64)
        fallback = int(nz["fallback_buildings"])
        if "buried" in nz:
            buried = nz["buried"]
    else:
        n, fallback = orient_outward(tri, n, sem, data["tri_bldg"])
    valid = np.isfinite(n).all(1) & (area > 1e-6)
    scene_mask = valid.copy()
    if args.scene_bldg_frac < 1.0:
        # Scaling measurement: the queried surfaces stay exactly the same and
        # only the number of occluders in the scene changes, so the measured
        # time isolates the cost of the occluders.
        ids = np.unique(data["tri_bldg"])
        k = max(1, int(round(len(ids) * args.scene_bldg_frac)))
        sub = np.random.default_rng(args.scene_seed).permutation(ids)[:k]
        scene_mask &= np.isin(data["tri_bldg"], sub)
    keep = valid & ~buried
    if args.only_index:
        # Equal-load measurement: the scene stays complete, but only the
        # listed surfaces are queried, so the cost can be compared with a
        # control that evaluates exactly those surfaces.
        sel = np.zeros(len(tri), bool)
        sel[np.load(args.only_index)["index"]] = True
        keep &= sel
    print(f"triangles={len(tri)} usable={keep.sum()} "
          f"orientation_fallback_buildings={fallback} ({time.time()-t_or:.1f} s)")

    t0 = time.time()
    pts, pidx = sample_points(tri[scene_mask], args.samples_per_m2,
                              seed=args.seed, with_index=True)
    pnrm = n[scene_mask][pidx].astype(np.float32)
    print(f"scene splat points={len(pts):,} ({time.time()-t0:.1f} s)")

    pts_t = torch.from_numpy(pts).to(dev)
    pnrm_t = torch.from_numpy(pnrm).to(dev)
    q = torch.from_numpy((c + n * args.offset)[keep].astype(np.float32)).to(dev)
    nq = torch.from_numpy(n[keep].astype(np.float32)).to(dev)
    shadow = DirectionalShadow(pts_t, args.texel, pnrm_t)

    times, weights = solar.timesteps(args.year, args.tz, args.hour_step)
    alt, az = solar.solar_position(times, args.lat, args.lon)
    dni, dhi = solar.clear_sky(alt)
    sv = solar.sun_vector(alt, az)
    day = alt > np.radians(args.min_alt)
    print(f"time steps={len(times)} daylight={int(day.sum())}")

    torch.cuda.synchronize() if dev.type == "cuda" else None
    t_light = time.time()

    beam = torch.zeros(len(q), device=dev)
    beam_open = torch.zeros(len(q), device=dev)
    for i in np.nonzero(day)[0]:
        d = torch.tensor(sv[i], device=dev, dtype=torch.float32)
        cosi = (nq @ d).clamp(min=0.0)
        if float(cosi.max()) <= 0:
            continue
        e = float(dni[i]) * float(weights[i])  # Wh/m2 perpendicular
        vis = shadow.visible(d, q, args.bias, args.neigh,
                             front_bias=slope_bias(cosi, args.texel, args.bias))
        beam += cosi * e * vis
        beam_open += cosi * e

    # Diffuse sky: same machinery over the Tregenza dome, weighted by the
    # daylight-weighted mean diffuse horizontal irradiance of the year.
    pdirs, pomega = solar.tregenza_patches()
    dhi_total = float((dhi[day] * weights[day]).sum())  # Wh/m2 horizontal
    svf_num = torch.zeros(len(q), device=dev)
    svf_den = torch.zeros(len(q), device=dev)
    for j in range(len(pdirs)):
        d = torch.tensor(pdirs[j], device=dev, dtype=torch.float32)
        cosi = (nq @ d).clamp(min=0.0)
        if float(cosi.max()) <= 0:
            continue
        vis = shadow.visible(d, q, args.bias, args.neigh,
                             front_bias=slope_bias(cosi, args.texel, args.bias))
        svf_num += cosi * float(pomega[j]) * vis
        svf_den += cosi * float(pomega[j])

    # The sky dome is used as a *ratio* (the visible fraction of the
    # cos-weighted hemisphere), and the absolute diffuse irradiation comes from
    # the exact isotropic value DHI*(1+cos beta)/2. That way the 145-patch
    # discretisation cancels in the unobstructed limit, where it would
    # otherwise bias tilted surfaces by of the order of ten per cent.
    svf = svf_num / svf_den.clamp(min=1e-9)

    tilt_factor = (1.0 + nq[:, 2].clamp(-1.0, 1.0)) / 2.0
    diff_open = dhi_total * tilt_factor
    diff = diff_open * svf
    svf_open = torch.ones_like(svf)

    torch.cuda.synchronize() if dev.type == "cuda" else None
    light_s = time.time() - t_light

    out = np.zeros((len(tri), 6), np.float32)
    idx = np.nonzero(keep)[0]
    out[idx, 0] = (beam / 1000.0).cpu().numpy()        # kWh/m2/yr beam, shadowed
    out[idx, 1] = (diff / 1000.0).cpu().numpy()        # kWh/m2/yr diffuse, shadowed
    out[idx, 2] = (beam_open / 1000.0).cpu().numpy()   # kWh/m2/yr beam, unobstructed
    out[idx, 3] = (diff_open / 1000.0).cpu().numpy()   # kWh/m2/yr diffuse, unobstructed
    out[idx, 4] = svf.cpu().numpy()
    out[idx, 5] = area[idx]

    np.savez_compressed(
        args.out, per_tri=out, normals=n, centroid=c, keep=keep, sem=sem,
        tri_bldg=data["tri_bldg"], origin=data["origin"],
    )
    tot = out[idx, 0] + out[idx, 1]
    meta = {
        "tile": args.tile,
        "device": str(dev),
        "cpu_count": os.cpu_count(),
        "torch_threads": torch.get_num_threads(),
        "gpu": torch.cuda.get_device_name(0) if dev.type == "cuda" else None,
        "triangles": int(len(tri)),
        "triangles_used": int(keep.sum()),
        "scene_bldg_frac": args.scene_bldg_frac,
        "scene_triangles": int(scene_mask.sum()),
        "scene_buildings": int(len(np.unique(data["tri_bldg"][scene_mask]))),
        "splat_points": int(len(pts)),
        "texel_m": args.texel,
        "neigh": args.neigh,
        "bias_base_m": args.bias,
        "samples_per_m2": args.samples_per_m2,
        "directions": int(day.sum()) + int(len(pdirs)),
        "time_steps": int(len(times)),
        "daylight_steps": int(day.sum()),
        "light_transport_seconds": round(light_s, 3),
        "annual_kwh_m2": {
            "mean": float(tot.mean()), "p05": float(np.percentile(tot, 5)),
            "median": float(np.median(tot)), "p95": float(np.percentile(tot, 95)),
            "max": float(tot.max()),
        },
        "orientation_fallback_buildings": int(fallback),
        "buried_faces_excluded": int(buried.sum()),
        "fully_dark_surfaces": int((out[idx, 0] + out[idx, 1] < 1.0).sum()),
        "mean_sky_view_factor": float(out[idx, 4].mean()),
        "shading_loss_fraction": float(1 - tot.sum() / (out[idx, 2] + out[idx, 3]).sum()),
        "model": "Hottel clear sky, isotropic 145-patch Tregenza dome, monthly "
                 "representative days weighted by days per month. Clear-sky "
                 "model, not measured weather.",
    }
    print(json.dumps(meta, indent=2))
    with open(args.out + ".meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    return meta


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tile", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--tz", type=float, default=9.0)
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--hour-step", type=float, default=1.0)
    ap.add_argument("--min-alt", type=float, default=1.0)
    ap.add_argument("--texel", type=float, default=1.0)
    ap.add_argument("--samples-per-m2", type=float, default=1.0)
    ap.add_argument("--offset", type=float, default=0.05)
    ap.add_argument("--bias", type=float, default=0.05)
    ap.add_argument("--neigh", type=int, default=0, help="texel lookup radius")
    ap.add_argument("--only-index", default="",
                    help="npz with an 'index' array: query only those faces")
    ap.add_argument("--enclosed-threshold", type=float, default=0.02,
                    help="sky fraction below which a surface is called enclosed")
    ap.add_argument("--normals", default="", help="npz from orient_normals.py")
    ap.add_argument("--scene-bldg-frac", type=float, default=1.0,
                    help="fraction of the buildings kept as occluders in the "
                         "scene; the queried surfaces are unchanged")
    ap.add_argument("--scene-seed", type=int, default=0)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--seed", type=int, default=0)
    run(ap.parse_args())


if __name__ == "__main__":
    main()
