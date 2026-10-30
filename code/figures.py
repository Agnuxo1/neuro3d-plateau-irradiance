"""Figures for the report and the slides. Japanese labels, dark background."""

from __future__ import annotations

import argparse
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

JP = ["Yu Gothic", "Meiryo", "MS Gothic", "Noto Sans JP", "DejaVu Sans"]
BG, FG, DIM = "#0b0f14", "#e8eef6", "#9fb0c3"
ACC = "#4cc9f0"
CLS = {1: ("#f4a261", "壁面"), 2: ("#4cc9f0", "屋根面"), 3: ("#a78bfa", "LOD1 面")}


def style():
    plt.rcParams.update({
        "font.family": JP,
        "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG,
        "text.color": FG, "axes.labelcolor": FG, "axes.edgecolor": "#223042",
        "xtick.color": DIM, "ytick.color": DIM, "grid.color": "#1b2634",
        "axes.grid": True, "axes.spines.top": False, "axes.spines.right": False,
        "font.size": 11, "figure.dpi": 150,
    })


def fig_scatter(pairs, out):
    own, ref, sem = pairs["own"], pairs["control"], pairs["sem"]
    m = ref > 1
    fig, ax = plt.subplots(figsize=(5.4, 5.0))
    hi = max(own[m].max(), ref[m].max()) * 1.05
    ax.plot([0, hi], [0, hi], color=DIM, lw=1, ls="--", label="1:1")
    for s, (c, lab) in CLS.items():
        k = m & (sem == s)
        if k.sum():
            ax.scatter(ref[k], own[k], s=16, c=c, alpha=.85, lw=0, label=lab)
    ax.set_xlabel("Cycles 対照値  kWh/m²·年")
    ax.set_ylabel("Neuro3D  kWh/m²·年")
    ax.set_title("年間日射量：自前エンジンと対照の一致", color=FG)
    ax.set_xlim(0, hi); ax.set_ylim(0, hi)
    ax.legend(frameon=False, labelcolor=DIM, fontsize=9, loc="upper left")
    fig.tight_layout(); fig.savefig(out); plt.close(fig)


def fig_error(pairs, out):
    own, ref = pairs["own"], pairs["control"]
    m = ref > 1
    rel = np.abs(own[m] - ref[m]) / ref[m] * 100
    fig, ax = plt.subplots(figsize=(5.4, 3.4))
    ax.hist(np.clip(rel, 0, 120), bins=40, color=ACC, alpha=.9)
    for q, lab, col in [(50, "中央値", "#8fd14f"), (95, "95 パーセンタイル", "#f4a261")]:
        v = np.percentile(rel, q)
        ax.axvline(min(v, 120), color=col, lw=1.4,
                   label=f"{lab} {v:.0f} %")
    ax.set_xlabel("相対誤差 %（120 % で打ち切り）")
    ax.set_ylabel("面の数")
    ax.set_title("対照に対する相対誤差の分布", color=FG)
    ax.legend(frameon=False, labelcolor=DIM, fontsize=9)
    fig.tight_layout(); fig.savefig(out); plt.close(fig)


def fig_map(n3, out, key=0):
    per, keep, cen = n3["per_tri"], n3["keep"], n3["centroid"]
    nrm = n3["normals"]
    m = keep & (nrm[:, 2] > -0.5)
    v = per[m, 0] + per[m, 1] if key == 0 else per[m, 4]
    fig, ax = plt.subplots(figsize=(6.6, 5.0))
    o = np.argsort(v)
    sc = ax.scatter(cen[m][o, 0], cen[m][o, 1], c=v[o], s=2.0, lw=0,
                    cmap="inferno" if key == 0 else "viridis")
    cb = fig.colorbar(sc, ax=ax)
    cb.set_label("年間日射量 kWh/m²·年" if key == 0 else "天空率", color=DIM)
    cb.ax.yaxis.set_tick_params(color=DIM)
    ax.set_aspect("equal"); ax.grid(False)
    ax.set_xlabel("東 m"); ax.set_ylabel("北 m")
    ax.set_title("広島市中心部・3次メッシュ 51324376" if key == 0
                 else "天空率の分布", color=FG)
    fig.tight_layout(); fig.savefig(out); plt.close(fig)


def fig_cost(res, out):
    h2 = res["H2"]
    eq = h2.get("equal_load") or {}
    fig, ax = plt.subplots(figsize=(6.0, 3.4))
    labels = ["Neuro3D\n同じ 900 面", "Cycles 対照\n900 面",
              "Neuro3D\n全 %s 面" % f"{h2['own_surfaces']:,}"]
    vals = [eq.get("own_seconds_same_900", float("nan")) / h2["control_surfaces"] * 1e3,
            h2["control_seconds_per_surface"] * 1e3,
            h2["own_seconds_per_surface"] * 1e3]
    ax.bar(labels, vals, color=[ACC, "#f4a261", "#8fd14f"], width=.55)
    ax.set_yscale("log")
    ax.set_ylabel("1 面あたりの計算時間 ms（対数軸）")
    for x, v in zip(labels, vals):
        ax.text(x, v * 1.3, f"{v:.3g}", ha="center", color=FG, fontsize=10)
    ax.set_title("同じ負荷で %.0f 倍、街区全体に広げると %.0f 倍"
                 % (eq.get("speedup", float("nan")), h2["speedup_per_surface"]),
                 color=FG, fontsize=12)
    fig.tight_layout(); fig.savefig(out); plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    style()
    os.makedirs(a.out, exist_ok=True)
    res = json.load(open(os.path.join(a.results, "CONTRATO-001.json"), encoding="utf-8"))
    pairs = np.load(os.path.join(a.results, "CONTRATO-001.json.pairs.npz"))
    n3 = np.load(os.path.join(a.results, "neuro3d.npz"))
    fig_scatter(pairs, os.path.join(a.out, "fig1_scatter.png"))
    fig_error(pairs, os.path.join(a.out, "fig2_error.png"))
    fig_map(n3, os.path.join(a.out, "fig3_map.png"), key=0)
    fig_map(n3, os.path.join(a.out, "fig4_svf.png"), key=1)
    fig_cost(res, os.path.join(a.out, "fig5_cost.png"))
    print("figures written to", a.out)


if __name__ == "__main__":
    main()
