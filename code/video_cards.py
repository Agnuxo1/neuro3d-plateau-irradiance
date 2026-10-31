"""Title and caption cards for the submission video, and the frame timeline.

Cards are rendered at the video resolution with Japanese text, then written
once per frame they occupy, so the whole video is a single numbered image
sequence that Blender encodes in one pass.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil

import matplotlib
matplotlib.use("Agg")
import matplotlib.image as mpimg  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

JP = ["Yu Gothic", "Meiryo", "MS Gothic", "DejaVu Sans"]
BG, FG, DIM, ACC, OK, WARN = "#0b0f14", "#f2f6fb", "#9fb0c3", "#4cc9f0", "#8fd14f", "#f4a261"


def card(path, res, title, lines, foot="", figure=None, title_size=40):
    w = res / 100.0
    fig = plt.figure(figsize=(w, w * 9 / 16), dpi=100)
    fig.patch.set_facecolor(BG)
    plt.rcParams.update({"font.family": JP})
    if figure:
        ax = fig.add_axes([.52, .12, .44, .72]); ax.axis("off")
        ax.imshow(mpimg.imread(figure))
        tx, tw = .05, .44
    else:
        tx, tw = .07, .86
    fig.text(tx, .80, title, color=FG, fontsize=title_size, va="top",
             fontfamily=JP, wrap=True)
    y = .62
    for ln in lines:
        fig.text(tx, y, ln, color=ACC if ln.startswith("▸") else DIM,
                 fontsize=19, va="top", fontfamily=JP, linespacing=1.6)
        y -= .10
    if foot:
        fig.text(tx, .09, foot, color=OK, fontsize=17, va="top", fontfamily=JP)
    fig.savefig(path, facecolor=BG)
    plt.close(fig)


def hold(src, out_dir, start, n):
    for i in range(n):
        shutil.copyfile(src, os.path.join(out_dir, "f%05d.png" % (start + i)))
    return start + n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--figs", required=True)
    ap.add_argument("--frames", required=True, help="sequence directory")
    ap.add_argument("--cards", required=True, help="where the card PNGs go")
    ap.add_argument("--res", type=int, default=1280)
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--viewer-url", default="")
    ap.add_argument("--repo-url", default="")
    ap.add_argument("--plan-only", action="store_true")
    a = ap.parse_args()

    os.makedirs(a.cards, exist_ok=True)
    os.makedirs(a.frames, exist_ok=True)
    res = json.load(open(os.path.join(a.results, "CONTRATO-001.json"),
                         encoding="utf-8"))
    n3 = res["engines"]["own"]
    h1, h2, h3 = res["H1"], res["H2"], res["H3"]
    ctl = res["engines"]["control"]

    specs = [
        ("c1", 4.0, dict(
            title="都市のなかで光を計算する",
            lines=["▸ PLATEAU の 3D 都市モデルを、GPU の描画そのもので解く",
                   "日射・日影エンジン Neuro3D",
                   "広島市 2022 年度 CityGML LOD2／3次メッシュ 51324376"],
            foot="PLATEAU AWARD 2026 ／ 一般部門", title_size=46)),
        ("c2", 5.0, dict(
            title="屋根・壁・地盤を一度に",
            lines=[f"▸ 1,190 棟 ／ {n3['triangles_used']:,} 面",
                   f"太陽 {n3['daylight_steps']} 位置 ＋ 天空 145 分割 ＝ "
                   f"{n3['directions']:,} 方向",
                   f"光伝播の計算時間 {n3['light_transport_seconds']:.0f} 秒（CPU 16 コア）"],
            foot="色は年間日射量 kWh/m²·年（晴天モデル）")),
        ("c3", 5.0, dict(
            title="しくみ：影は描画である",
            lines=["▸ 方向ごとに深度バッファを 2 枚つくる",
                   "背面バッファ＝市街の影、前面バッファ＝体積に埋もれた面",
                   "1 方向のコストは散布書き込み 1 回＋参照 1 回。"
                   "遮る物の数に依らない"])),
        ("c4", 4.0, dict(
            title="天空率",
            lines=["▸ 同じ走査から、面ごとの天空の見え方も出る",
                   f"市街による遮蔽損失 {h3['shading_loss_fraction']*100:.0f} %",
                   "太陽光パネルの適地、壁面の受熱、日かげの評価に直結する"])),
        ("c5", 6.0, dict(
            title="対照との一致",
            lines=[f"▸ 比較できた {res['probes_compared']} 面で R² = {h1['r2']:.3f}",
                   f"相対誤差の中央値 {h1['median_rel_error']*100:.1f} %"
                   f"（屋根面 1.2 %、壁面 6.3 %）",
                   "対照は Blender Cycles。太陽・晴天モデル・天空の範囲・"
                   "相互反射なしを揃えた"],
            figure=os.path.join(a.figs, "fig1_scatter.png"))),
        ("c6", 6.0, dict(
            title="通らなかった条件も載せる",
            lines=[f"▸ 事前条件は全 900 面で判定：R² "
                   f"{res['H1_all_probes_preregistered']['r2']:.3f} で不合格",
                   f"{900 - res['probes_compared']} 面は封じられた面で、"
                   "本エンジンだけが光を返す",
                   f"対照の校正誤差 {ctl['calibration_rel_error']:.1e}（解析解と一致）"],
            figure=os.path.join(a.figs, "fig2_error.png"))),
        ("c7", 6.0, dict(
            title="計算コスト",
            lines=[f"▸ 同じ 900 面で "
                   f"{(h2.get('equal_load') or {}).get('speedup', 0):.0f} 倍",
                   f"街区全体（44,902 面）に広げると "
                   f"{h2['speedup_per_surface']:.0f} 倍",
                   "1 方向のコストが面の数にほぼ依存しないため"],
            figure=os.path.join(a.figs, "fig5_cost.png"))),
        ("c8", 6.0, dict(
            title="触って確かめられる",
            lines=["▸ ブラウザのビューアで日射量と天空率を切り替え、"
                   "面ごとの数値を読める",
                   "画面の数値は計算結果ファイルから読み込み",
                   "コードは Apache-2.0、解析解の単体試験つき。"
                   "PLATEAU データは再配布しない"],
            foot=(a.viewer_url + ("   ／   " + a.repo_url if a.repo_url else ""))
                 if a.viewer_url else a.repo_url)),
    ]

    fps = a.fps
    timeline = []
    idx = 1
    for name, secs, kw in specs:
        p = os.path.join(a.cards, name + ".png")
        card(p, a.res, **kw)
        timeline.append((name, idx, int(secs * fps)))
        idx += int(secs * fps)
        if name == "c2":
            timeline.append(("ORBIT_IRR", idx, int(26 * fps)))
            idx += int(26 * fps)
        if name == "c4":
            timeline.append(("ORBIT_SVF", idx, int(16 * fps)))
            idx += int(16 * fps)

    plan = {"fps": fps, "res": a.res, "total_frames": idx - 1,
            "seconds": round((idx - 1) / fps, 1),
            "timeline": [{"name": n, "start": s, "frames": f} for n, s, f in timeline]}
    with open(os.path.join(a.frames, "..", "timeline.json"), "w",
              encoding="utf-8") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)
    print(json.dumps(plan, indent=2, ensure_ascii=False))

    if a.plan_only:
        return
    for name, start, nframes in timeline:
        if name.startswith("ORBIT"):
            continue
        hold(os.path.join(a.cards, name + ".png"), a.frames, start, nframes)
    print("cards written into the sequence")


if __name__ == "__main__":
    main()
