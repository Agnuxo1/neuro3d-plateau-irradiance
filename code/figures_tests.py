"""Figures for the four new measurements (P1-P4).

Each figure reads its own result file and draws nothing that is not in it; a
missing file is skipped and reported, never drawn from memory.
"""

from __future__ import annotations

import argparse
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from figures import ACC, BG, DIM, FG, style  # noqa: E402

OK, WARN, VIO = "#8fd14f", "#f4a261", "#a78bfa"


def load(path):
    if not os.path.exists(path):
        print("missing, skipped:", path)
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fig_p1(res, out):
    curve = res["curve"]
    x = np.array([c["splat_points"] for c in curve], float)
    t = np.array([c["light_transport_seconds"] for c in curve], float)
    fig, ax = plt.subplots(figsize=(6.2, 4.0))
    ax.plot(x, t, "o-", color=ACC, lw=2, ms=7, label="実測した光輸送時間")
    lin = t[0] * x / x[0]
    ax.plot(x, lin, "--", color=WARN, lw=1.4,
            label="遮蔽物の数に比例した場合")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("シーンに入れた遮蔽物の点の数")
    ax.set_ylabel("光輸送の時間 秒（対数軸）")
    ax.set_title("P1 遮蔽物を 20 倍にしても時間は %.1f 倍"
                 % res["time_growth_5pc_to_100pc"], color=FG, fontsize=13)
    for c in curve:
        ax.annotate(f"{int(c['scene_bldg_frac']*100)} %",
                    (c["splat_points"], c["light_transport_seconds"]),
                    textcoords="offset points", xytext=(6, -12),
                    color=DIM, fontsize=9)
    ax.legend(frameon=False, labelcolor=DIM, fontsize=9, loc="upper left")
    fig.tight_layout(); fig.savefig(out); plt.close(fig)
    print("wrote", out)


JP_PARAM = {"texel_m": "デプステクセル m", "samples_per_m2": "1 m² あたりの点の数",
            "hour_step_h": "太陽の時間刻み 時間"}


def fig_p2(res, out):
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.6))
    for ax, (name, sw) in zip(axes, res["sweeps"].items()):
        vals = [r["config"][name] for r in sw["runs"]]
        dev = [100 * abs(r["mean_shift_vs_finest"]) for r in sw["runs"]]
        ax.plot(vals, dev, "o-", color=ACC, lw=2, ms=6)
        base = res["base_config"][name]
        bi = vals.index(base)
        ax.plot([base], [dev[bi]], "o", ms=12, mfc="none", mec=OK, mew=2)
        ax.annotate("採用値 %.3g\n%.2f %%" % (base, dev[bi]), (base, dev[bi]),
                    textcoords="offset points", xytext=(8, 8), color=OK,
                    fontsize=9)
        ax.set_xscale("log")
        ax.set_xlabel(JP_PARAM.get(name, name))
        ax.set_ylabel("最も細かい設定との差 %")
    fig.suptitle("P2 離散化の誤差：採用した設定は最も細かい設定から数 %",
                 color=FG, fontsize=13)
    fig.tight_layout(); fig.savefig(out); plt.close(fig)
    print("wrote", out)


def _h1(contract):
    return contract["H1_all_probes_preregistered"]


def fig_p3(res, out):
    a = _h1(res["published_configuration"])
    b = _h1(res["with_3d_detector"])
    hiro = res.get("_hiroshima")
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    labels = ["R²", "相対誤差の中央値 %", "平均の偏り %"]
    series = [("名古屋（未見の都市）", a, ACC), ("名古屋＋3 次元検出", b, OK)]
    if hiro:
        series.insert(0, ("広島（調整に使った街区）", hiro, VIO))
    w = 0.8 / len(series)
    xs = np.arange(len(labels))
    for i, (nm, h, col) in enumerate(series):
        v = [h["r2"], h["median_rel_error"] * 100,
             h["mean_bias_fraction"] * 100]
        ax.bar(xs + i * w - 0.4 + w / 2, v, width=w * .9, color=col, label=nm)
        for x, y in zip(xs + i * w - 0.4 + w / 2, v):
            ax.text(x, y + 0.4, f"{y:.2f}", ha="center", color=FG, fontsize=8.5)
    ax.set_xticks(xs); ax.set_xticklabels(labels)
    ax.axhline(0, color="#223042", lw=1)
    ax.legend(frameon=False, labelcolor=DIM, fontsize=9)
    ax.set_title("P3 調整に使っていない都市へそのまま移したとき",
                 color=FG, fontsize=13)
    fig.tight_layout(); fig.savefig(out); plt.close(fig)
    print("wrote", out)


def fig_p4(res, before, out):
    q = res["detection_quality_on_probes"]
    after = _h1(res["contract_with_better_detector"])
    fig, axes = plt.subplots(1, 2, figsize=(10.0, 3.9))

    ax = axes[0]
    names = ["適合率", "再現率", "F1"]
    for i, (key, nm, col) in enumerate([("vertical", "鉛直のみ（公開版）", WARN),
                                        ("majority3d_union", "3 次元の多数決", OK)]):
        v = [q[key]["precision"], q[key]["recall"], q[key]["f1"]]
        ax.bar(np.arange(3) + i * .38 - .19, v, width=.34, color=col, label=nm)
        for x, y in zip(np.arange(3) + i * .38 - .19, v):
            ax.text(x, y + .02, f"{y:.2f}", ha="center", color=FG, fontsize=9)
    ax.set_xticks(range(3)); ax.set_xticklabels(names); ax.set_ylim(0, 1.15)
    ax.set_title("封じられた面の検出（対照を真値として）", color=FG, fontsize=12)
    ax.legend(frameon=False, labelcolor=DIM, fontsize=9, loc="lower right")

    ax = axes[1]
    labels = ["R²", "相対誤差の\n中央値 %", "95 パーセン\nタイル %"]
    bv = [before["r2"], before["median_rel_error"] * 100,
          min(before["p95_rel_error"] * 100, 1000)]
    av = [after["r2"], after["median_rel_error"] * 100,
          min(after["p95_rel_error"] * 100, 1000)]
    for i, (v, nm, col) in enumerate([(bv, "公開版", WARN), (av, "3 次元検出", OK)]):
        ax.bar(np.arange(3) + i * .38 - .19, v, width=.34, color=col, label=nm)
        for x, y, raw in zip(np.arange(3) + i * .38 - .19, v,
                             [v[0], v[1], v[2]]):
            ax.text(x, y * 1.08 + .05, f"{raw:.2f}", ha="center", color=FG,
                    fontsize=9)
    ax.set_yscale("symlog", linthresh=1)
    ax.set_xticks(range(3)); ax.set_xticklabels(labels)
    ax.set_title("全 900 面での事前条件（1000 % で打ち切り）", color=FG,
                 fontsize=12)
    ax.legend(frameon=False, labelcolor=DIM, fontsize=9)
    fig.tight_layout(); fig.savefig(out); plt.close(fig)
    print("wrote", out)


def fig_rooftop(res, out):
    top = res["top"][:15]
    names = [f"{i+1}" for i in range(len(top))]
    kwh = [r["estimated_annual_kwh"] / 1000.0 for r in top]
    area = [r["usable_roof_area_m2"] for r in top]
    fig, ax = plt.subplots(figsize=(7.4, 4.0))
    ax.bar(names, kwh, color=ACC, width=.65)
    for x, y, ar in zip(names, kwh, area):
        ax.text(x, y + max(kwh) * .015, f"{ar:,.0f} m²", ha="center",
                color=DIM, fontsize=8, rotation=90, va="bottom")
    ax.set_ylim(0, max(kwh) * 1.28)
    ax.set_xlabel("建物（推定発電量の上位 15 棟）")
    ax.set_ylabel("推定年間発電量 MWh/年")
    ax.set_title("屋上太陽光の候補：街区で %s 棟、合計 %.0f MWh/年（晴天モデル）"
                 % (f"{res['buildings_listed']:,}",
                    res["district_estimated_annual_mwh"]),
                 color=FG, fontsize=12)
    fig.tight_layout(); fig.savefig(out); plt.close(fig)
    print("wrote", out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tests", required=True, help="directory with P*.json")
    ap.add_argument("--published", required=True, help="CONTRATO-001.json")
    ap.add_argument("--rooftop", default="")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    style()
    os.makedirs(a.out, exist_ok=True)
    pub = load(a.published)

    p1 = load(os.path.join(a.tests, "P1_scaling.json"))
    if p1:
        fig_p1(p1, os.path.join(a.out, "p1_scaling.png"))
    p2 = load(os.path.join(a.tests, "P2_convergence.json"))
    if p2:
        fig_p2(p2, os.path.join(a.out, "p2_convergence.png"))
    p3 = load(os.path.join(a.tests, "P3_transfer.json"))
    if p3:
        if pub:
            p3["_hiroshima"] = _h1(pub)
        fig_p3(p3, os.path.join(a.out, "p3_transfer.png"))
    rt = load(a.rooftop) if a.rooftop else None
    if rt:
        fig_rooftop(rt, os.path.join(a.out, "rooftop.png"))
    p4 = load(os.path.join(a.tests, "P4_detector.json"))
    if p4 and pub:
        fig_p4(p4, _h1(pub), os.path.join(a.out, "p4_detector.png"))


if __name__ == "__main__":
    main()
