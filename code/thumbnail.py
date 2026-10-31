"""YouTube thumbnail (1280x720) and the repository's social preview image.

Both are built from the rendered district image and the measured numbers; no
stock art, no mock-up.
"""

from __future__ import annotations

import argparse
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.image as mpimg  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

JP = ["Yu Gothic", "Meiryo", "MS Gothic", "DejaVu Sans"]
BG, FG, ACC, OK, DIM = "#0b0f14", "#ffffff", "#4cc9f0", "#8fd14f", "#9fb0c3"


def build(hero, res, out, w=1280, h=720):
    plt.rcParams.update({"font.family": JP})
    fig = plt.figure(figsize=(w / 100, h / 100), dpi=100)
    fig.patch.set_facecolor(BG)
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off")
    ax.imshow(mpimg.imread(hero), extent=(0, 1, 0, 1), aspect="auto")
    ax.add_patch(Rectangle((0, 0), 1, 1, color=BG, alpha=.42))
    ax.add_patch(Rectangle((0, 0), 1, .30, color=BG, alpha=.72))

    eng = res["engines"]["own"]
    fig.text(.045, .93, "都市のなかで", color=FG, fontsize=62, va="top")
    fig.text(.045, .72, "光を計算する", color=ACC, fontsize=62, va="top")
    fig.text(.045, .235, "PLATEAU の街区まるごと "
             f"{eng['triangles_used']:,} 面を "
             f"{eng['light_transport_seconds']:.0f} 秒",
             color=FG, fontsize=27, va="top")
    fig.text(.045, .125, f"パストレーサとの一致 R² {res['H1']['r2']:.3f}"
             "（開けた面）　／　Neuro3D", color=OK, fontsize=22, va="top")
    fig.savefig(out, facecolor=BG)
    plt.close(fig)
    print("wrote", out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hero", required=True)
    ap.add_argument("--results", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    with open(os.path.join(a.results, "CONTRATO-001.json"),
              encoding="utf-8") as f:
        res = json.load(f)
    build(a.hero, res, a.out)


if __name__ == "__main__":
    main()
