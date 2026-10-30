"""Export the computed district to a compact binary the web viewer streams.

Layout of `district.bin` (little endian):

    magic   4 bytes  "N3DP"
    version uint32   1
    ntri    uint32
    bbox    6 x float32   minx miny minz maxx maxy maxz
    pos     ntri*9 x float32   triangle vertices, metres, origin-centred
    value   ntri  x float32    annual irradiation kWh/m2/yr
    svf     ntri  x uint8      sky view factor * 255
    sem     ntri  x uint8      0 ground 1 wall 2 roof 3 other

A sidecar `district.json` carries the metadata the page shows, so the page
never states a number that the run did not produce.
"""

from __future__ import annotations

import argparse
import json
import struct

import numpy as np


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tile", required=True)
    ap.add_argument("--neuro3d", required=True)
    ap.add_argument("--contract", default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--drop-downward", action="store_true",
                    help="omit ground slabs and other downward faces")
    a = ap.parse_args()

    tile = np.load(a.tile)
    n3 = np.load(a.neuro3d)
    tri = tile["tri"].astype(np.float32)
    per = n3["per_tri"]
    keep = n3["keep"].copy()
    nrm = n3["normals"]
    sem = n3["sem"]
    if a.drop_downward:
        keep &= nrm[:, 2] > -0.5
    idx = np.nonzero(keep)[0]

    v = (per[idx, 0] + per[idx, 1]).astype(np.float32)
    svf = np.clip(per[idx, 4] * 255.0, 0, 255).astype(np.uint8)
    pos = tri[idx]
    c = pos.reshape(-1, 3)
    centre = (c.min(0) + c.max(0)) / 2.0
    centre[2] = c[:, 2].min()
    pos = (pos - centre).astype(np.float32)
    cc = pos.reshape(-1, 3)

    with open(a.out + ".bin", "wb") as f:
        f.write(b"N3DP")
        f.write(struct.pack("<II", 1, len(idx)))
        f.write(np.concatenate([cc.min(0), cc.max(0)]).astype(np.float32).tobytes())
        f.write(pos.tobytes())
        f.write(v.tobytes())
        f.write(svf.tobytes())
        f.write(sem[idx].astype(np.uint8).tobytes())

    meta = {
        "triangles": int(len(idx)),
        "kwh_per_m2_year": {
            "min": float(v.min()), "max": float(v.max()),
            "mean": float(v.mean()), "median": float(np.median(v)),
        },
        "engine": json.load(open(a.neuro3d + ".meta.json", encoding="utf-8")),
    }
    if a.contract:
        meta["contract"] = json.load(open(a.contract, encoding="utf-8"))
    with open(a.out + ".json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"wrote {a.out}.bin triangles={len(idx)} "
          f"size={(len(idx)*(9*4+4+2)+34)/1e6:.1f} MB")


if __name__ == "__main__":
    main()
