"""Turn one PLATEAU CityGML building tile into a triangle mesh in local metres.

Input: a `*_bldg_6697_op.gml` tile from Project PLATEAU (CRS EPSG:6697,
JGD2011 geographic 3D: latitude, longitude, ellipsoidal height, in that order).
Output: an .npz with

    tri        (F, 3, 3) float32  triangle vertices in local ENU metres
    tri_bldg   (F,)      int32    index of the building each triangle belongs to
    tri_sem    (F,)      int8     0 ground, 1 wall, 2 roof, 3 other/closure
    bldg_id    (B,)      <U40     gml:id of each building
    origin     (3,)      float64  lat, lon, h of the local origin
    lod        (F,)      int8     geometric LOD the surface came from

Semantic surfaces (bldg:RoofSurface / WallSurface / GroundSurface) are the LOD2
representation; tiles also carry lod1Solid, used only for buildings without LOD2.
"""

from __future__ import annotations

import argparse
import math
import time

import numpy as np
from lxml import etree

NS_BLDG = "{http://www.opengis.net/citygml/building/2.0}"
NS_GML = "{http://www.opengis.net/gml}"
NS_CORE = "{http://www.opengis.net/citygml/2.0}"

SEM = {"GroundSurface": 0, "WallSurface": 1, "RoofSurface": 2,
       "OuterCeilingSurface": 3, "OuterFloorSurface": 3, "ClosureSurface": 3}


def enu_factors(lat_deg: float) -> tuple[float, float]:
    """Metres per degree of latitude and longitude on the GRS80 ellipsoid."""
    a, f = 6378137.0, 1.0 / 298.257222101
    e2 = f * (2 - f)
    lat = math.radians(lat_deg)
    s = math.sin(lat)
    w = math.sqrt(1 - e2 * s * s)
    m_lat = a * (1 - e2) / w**3 * math.pi / 180.0
    m_lon = a / w * math.cos(lat) * math.pi / 180.0
    return m_lat, m_lon


def fan_triangulate(ring: np.ndarray) -> np.ndarray:
    """Fan-triangulate one planar polygon ring given as (n, 3) metres."""
    if len(ring) >= 2 and np.allclose(ring[0], ring[-1]):
        ring = ring[:-1]
    n = len(ring)
    if n < 3:
        return np.zeros((0, 3, 3), np.float32)
    idx = [(0, i, i + 1) for i in range(1, n - 1)]
    return ring[np.asarray(idx, np.int32)].astype(np.float32)


def parse_poslist(text: str) -> np.ndarray:
    v = np.fromstring(text, sep=" ")
    return v.reshape(-1, 3)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gml", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-buildings", type=int, default=0)
    a = ap.parse_args()

    t0 = time.time()
    tris: list[np.ndarray] = []
    tri_b: list[np.ndarray] = []
    tri_s: list[np.ndarray] = []
    tri_l: list[np.ndarray] = []
    ids: list[str] = []
    origin: list[float] | None = None
    m_lat = m_lon = 1.0

    ctx = etree.iterparse(a.gml, events=("end",), tag=NS_BLDG + "Building", huge_tree=True)
    for _, bld in ctx:
        bid = bld.get(NS_GML + "id") or f"b{len(ids)}"
        b_index = len(ids)
        got_lod2 = False
        local: list[tuple[np.ndarray, int, int]] = []

        for sem_name, sem_code in SEM.items():
            for surf in bld.iter(NS_BLDG + sem_name):
                for pl in surf.iter(NS_GML + "posList"):
                    pts = parse_poslist(pl.text)
                    local.append((pts, sem_code, 2))
                    got_lod2 = True

        if not got_lod2:
            for solid in bld.iter(NS_BLDG + "lod1Solid"):
                for pl in solid.iter(NS_GML + "posList"):
                    pts = parse_poslist(pl.text)
                    local.append((pts, 3, 1))

        if local:
            if origin is None:
                first = local[0][0][0]
                origin = [float(first[0]), float(first[1]), 0.0]
                m_lat, m_lon = enu_factors(origin[0])
            for pts, sem_code, lod in local:
                xyz = np.empty_like(pts)
                xyz[:, 0] = (pts[:, 1] - origin[1]) * m_lon      # east
                xyz[:, 1] = (pts[:, 0] - origin[0]) * m_lat      # north
                xyz[:, 2] = pts[:, 2] - origin[2]                # up
                t = fan_triangulate(xyz)
                if len(t):
                    tris.append(t)
                    tri_b.append(np.full(len(t), b_index, np.int32))
                    tri_s.append(np.full(len(t), sem_code, np.int8))
                    tri_l.append(np.full(len(t), lod, np.int8))
            ids.append(bid)

        bld.clear()
        while bld.getprevious() is not None:
            del bld.getparent()[0]
        if a.max_buildings and len(ids) >= a.max_buildings:
            break

    tri = np.concatenate(tris) if tris else np.zeros((0, 3, 3), np.float32)
    np.savez_compressed(
        a.out,
        tri=tri,
        tri_bldg=np.concatenate(tri_b) if tri_b else np.zeros(0, np.int32),
        tri_sem=np.concatenate(tri_s) if tri_s else np.zeros(0, np.int8),
        lod=np.concatenate(tri_l) if tri_l else np.zeros(0, np.int8),
        bldg_id=np.asarray(ids, dtype="<U40"),
        origin=np.asarray(origin or [0, 0, 0], np.float64),
    )
    print(f"buildings={len(ids)} triangles={len(tri)} "
          f"bbox_m={tri.reshape(-1,3).min(0) if len(tri) else None} .. "
          f"{tri.reshape(-1,3).max(0) if len(tri) else None} "
          f"({time.time()-t0:.1f} s)")


if __name__ == "__main__":
    main()
