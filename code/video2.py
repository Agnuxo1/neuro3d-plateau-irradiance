"""Build the submission video as one numbered image sequence.

The animated segments are the GIFs produced by visuals.py, so the video shows
the same measured arrays as the repository and nothing re-drawn by hand. The
cards are rendered here, with every number read from the result files.

    python video2.py --results <dir> --tests <dir> --figs <dir> \
        --testfigs <dir> --media <dir> --out <frames dir>
then
    blender -b --factory-startup -P video_encode.py -- --frames <frames dir> \
        --out video.mp4 --fps 24 --count <N>
"""

from __future__ import annotations

import argparse
import glob
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.image as mpimg  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

JP = ["Yu Gothic", "Meiryo", "MS Gothic", "DejaVu Sans"]
BG, FG, DIM = "#0b0f14", "#f2f6fb", "#9fb0c3"
ACC, OK, WARN = "#4cc9f0", "#8fd14f", "#f4a261"
RES = (1280, 720)
FPS = 24


def card_image(title, lines, foot="", figure=None, title_size=40,
               title_color=FG):
    plt.rcParams.update({"font.family": JP})
    fig = plt.figure(figsize=(RES[0] / 100, RES[1] / 100), dpi=100)
    fig.patch.set_facecolor(BG)
    if figure and os.path.exists(figure):
        ax = fig.add_axes([.50, .10, .46, .76]); ax.axis("off")
        ax.imshow(mpimg.imread(figure))
        tx = .055
    else:
        tx = .07
    fig.text(tx, .82, title, color=title_color, fontsize=title_size, va="top")
    y = .63
    for ln in lines:
        fig.text(tx, y, ln, color=ACC if ln.startswith("▸") else DIM,
                 fontsize=19, va="top", linespacing=1.6)
        y -= .105
    if foot:
        fig.text(tx, .08, foot, color=OK, fontsize=17, va="top")
    fig.canvas.draw()
    img = Image.fromarray(np.asarray(fig.canvas.buffer_rgba())[..., :3].copy())
    plt.close(fig)
    return img.resize(RES, Image.LANCZOS)


def fit(img: Image.Image) -> Image.Image:
    """Letterbox onto the video frame without cropping or stretching."""
    canvas = Image.new("RGB", RES, BG)
    s = min(RES[0] / img.width, RES[1] / img.height)
    im = img.resize((max(1, int(img.width * s)), max(1, int(img.height * s))),
                    Image.LANCZOS)
    canvas.paste(im, ((RES[0] - im.width) // 2, (RES[1] - im.height) // 2))
    return canvas


def gif_frames(path):
    im = Image.open(path)
    out = []
    for i in range(im.n_frames):
        im.seek(i)
        out.append(fit(im.convert("RGB")))
    return out


class Timeline:
    def __init__(self, outdir):
        self.out = outdir
        os.makedirs(outdir, exist_ok=True)
        for f in os.listdir(outdir):
            if f.endswith(".png"):
                os.remove(os.path.join(outdir, f))
        self.n = 0
        self.marks = []

    def hold(self, img, seconds, label=""):
        k = int(round(seconds * FPS))
        start = self.n + 1
        for _ in range(k):
            self.n += 1
            img.save(os.path.join(self.out, f"{self.n:05d}.png"))
        self.marks.append({"label": label, "start": start, "end": self.n})

    def play(self, frames, seconds, label="", pingpong=False):
        seq = frames + frames[::-1] if pingpong else frames
        k = int(round(seconds * FPS))
        start = self.n + 1
        for i in range(k):
            self.n += 1
            seq[int(i * len(seq) / k)].save(
                os.path.join(self.out, f"{self.n:05d}.png"))
        self.marks.append({"label": label, "start": start, "end": self.n})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--tests", required=True)
    ap.add_argument("--figs", required=True)
    ap.add_argument("--testfigs", required=True)
    ap.add_argument("--media", required=True)
    ap.add_argument("--viewer", default="", help="directory of recorded viewer frames")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    res = json.load(open(os.path.join(a.results, "CONTRATO-001.json"),
                         encoding="utf-8"))
    sub, hp = res["H1"], res["H1_all_probes_preregistered"]
    eng = res["engines"]["own"]
    h2 = res["H2"]
    eq = h2.get("equal_load") or {}

    def tj(n):
        p = os.path.join(a.tests, n)
        return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None
    p1, p2, p3, p4 = (tj("P1_scaling.json"), tj("P2_convergence.json"),
                      tj("P3_transfer.json"), tj("P4_detector.json"))

    tl = Timeline(a.out)
    M = lambda n: os.path.join(a.media, n)
    F = lambda n: os.path.join(a.figs, n)
    T = lambda n: os.path.join(a.testfigs, n)

    tl.hold(card_image(
        "都市のなかで光を計算する",
        ["▸ Neuro3D 都市日射エンジン",
         "PLATEAU の 3D 都市モデル（CityGML LOD2）から、",
         "面ごとの年間日射量と天空率を、街区まるごと。"],
        foot="PLATEAU AWARD 2026 ／ 一般部門", title_size=46), 5, "title")

    tl.hold(fit(Image.open(M("hero_irradiance.png"))), 4, "hero")

    tl.play(gif_frames(M("orbit.gif")), 7, "orbit")

    tl.hold(card_image(
        "1 日の光を、そのまま計算する",
        ["▸ 6 月 21 日・20 分ごと",
         "太陽の位置ごとに街区の全面を判定します。",
         "次の映像の色は計算した直達日射そのものです。"],
        title_size=40), 3.5, "sun_card")
    tl.play(gif_frames(M("sun_day.gif")), 8, "sun")

    tl.hold(card_image(
        "考え方：描画として解く",
        ["▸ 光の方向ごとに 2 枚のデプスバッファ",
         "背面バッファ＝街区の影、前面バッファ＝埋もれた面。",
         "1 面あたりの問い合わせは、遮蔽物が何棟あっても 1 回の参照。",
         "その 1 パスを街区の全面で使い回します。"], title_size=40), 4, "method_card")
    if os.path.exists(M("method.gif")):
        tl.play(gif_frames(M("method.gif")), 6, "method")

    tl.hold(card_image(
        "対照はパストレーサ",
        ["▸ Blender Cycles、同一機・同一条件",
         f"開けた {res['probes_compared']} 面で R² {sub['r2']:.3f}、",
         f"相対誤差の中央値 {sub['median_rel_error']*100:.1f} %。",
         f"対照自身の校正誤差は解析解に対して "
         f"{res['C1_calibration_rel_error']:.1e}。"],
        figure=F("fig1_scatter.png"), title_size=38), 7, "agreement")

    tl.hold(card_image(
        "速さ",
        ["▸ 同じ 900 面・同じ 286 方向で "
         f"{eq.get('speedup', float('nan')):.0f} 倍",
         f"街区全体 {h2['own_surfaces']:,} 面に広げると",
         f"1 面あたり {h2['speedup_per_surface']:.0f} 倍。",
         "前処理は計測に含めていません。"],
        figure=F("fig5_cost.png"), title_size=40), 6, "cost")

    if p1:
        tl.hold(card_image(
            "新しい検証 ①　スケーリング",
            ["▸ クエリ面を固定し、遮蔽物だけを増やす",
             f"遮蔽物の点を {p1['occluder_growth_5pc_to_100pc']:.0f} 倍にしても",
             f"時間は {p1['time_growth_5pc_to_100pc']:.1f} 倍"
             f"（両対数の傾き {p1['exponent_log_log']:.2f}）。"],
            figure=T("p1_scaling.png"), title_size=34), 6, "p1")
    if p2:
        sh = {k: abs(v["base_vs_finest_mean_shift"]) * 100
              for k, v in p2["sweeps"].items()}
        tl.hold(card_image(
            "新しい検証 ②　数値の収束",
            ["▸ 設定を変えても答えが動かないこと",
             "採用した設定と最も細かい設定の差："]
            + ["　" + "、".join(f"{k} {v:.2f} %" for k, v in sh.items())],
            figure=T("p2_convergence.png"), title_size=34), 6, "p2")
    if p3:
        t = p3["published_configuration"]["H1_all_probes_preregistered"]
        tl.hold(card_image(
            "新しい検証 ③　別の都市へ",
            ["▸ 調整に使っていない名古屋市の街区",
             "設定は一切変えずに測り直しました。",
             f"R² {t['r2']:.3f}、相対誤差の中央値 "
             f"{t['median_rel_error']*100:.1f} %。"],
            figure=T("p3_transfer.png"), title_size=34), 6, "p3")
    if p4:
        q = p4["detection_quality_on_probes"]
        af = p4["contract_with_better_detector"]["H1_all_probes_preregistered"]
        tl.hold(card_image(
            "新しい検証 ④　埋もれた面の検出",
            ["▸ 鉛直の判定を 3 次元の多数決へ",
             f"再現率 {q['vertical']['recall']:.2f} → "
             f"{q['majority3d_union']['recall']:.2f}、",
             f"全 900 面の R² は {hp['r2']:.3f} → {af['r2']:.3f}。",
             "登録時の判定はそのまま残しています。"],
            figure=T("p4_detector.png"), title_size=34), 6.5, "p4")

    rt_path = os.path.join(a.tests, "rooftop.json")
    if os.path.exists(rt_path):
        rt = json.load(open(rt_path, encoding="utf-8"))
        tl.hold(card_image(
            "そのまま使える出力",
            ["▸ 屋上太陽光の候補リスト",
             f"候補 {rt['buildings_listed']:,} 棟、利用可能な屋根 "
             f"{rt['usable_roof_area_m2']:,.0f} m²、",
             f"推定 {rt['district_estimated_annual_mwh']:,.0f} MWh/年"
             "（晴天モデル・係数は差し替え可）。"],
            figure=T("rooftop.png"), title_size=38), 6.5, "rooftop")

    tl.hold(card_image(
        "ブラウザでそのまま触れます",
        ["▸ agnuxo1.github.io/neuro3d-plateau-irradiance",
         "面にカーソルを合わせると年間日射量と天空率が読めます。",
         "インストール不要。スマートフォンでも動きます。"],
        figure=M("viewer_screenshot.jpg"), title_size=36), 4.5, "viewer")

    # The real viewer, recorded while it runs: the camera orbits, the display
    # switches to the sky view factor and the wall class is filtered out, all
    # through the page's own controls.
    shots = sorted(glob.glob(os.path.join(a.viewer, "v*.png")))
    if shots:
        frames = [fit(Image.open(f).convert("RGB")) for f in shots]
        tl.play(frames, 7.5, "viewer_live")

    lim = [f"▸ 事前登録した条件 H1 は全 900 面では通っていません"
           f"（登録時の構成で R² {hp['r2']:.3f}）"]
    if p4:
        af2 = p4["contract_with_better_detector"]["H1_all_probes_preregistered"]
        q2 = p4["detection_quality_on_probes"]["majority3d_union"]
        lim += [f"3 次元検出器では R² {af2['r2']:.3f} まで改善しますが契約後の測定で、",
                f"95 パーセンタイルは {af2['p95_rel_error']*100:.0f} % のまま未達。"
                f"残る {q2['fn']} 面は原因不明。"]
    lim += ["晴天モデルの計算値で、実測気象ではありません。独立監査は未了です。"]
    tl.hold(card_image("観察事項と限界", lim, title_size=38,
                       title_color=WARN), 7.5, "limits")

    tl.hold(card_image(
        "すべて公開しています",
        ["▸ github.com/Agnuxo1/neuro3d-plateau-irradiance",
         "コードは Apache-2.0。失敗した反復も含む全履歴つき。",
         "PLATEAU の元データは再配布せず、取得スクリプトのみ。"],
        foot="Francisco Angulo de Lafuente ／ 個人応募", title_size=38),
        5, "closing")

    with open(os.path.join(a.out, "..", "timeline2.json"), "w",
              encoding="utf-8") as f:
        json.dump({"fps": FPS, "frames": tl.n,
                   "seconds": round(tl.n / FPS, 2), "marks": tl.marks},
                  f, indent=2, ensure_ascii=False)
    print(f"frames={tl.n}  seconds={tl.n/FPS:.1f}")


if __name__ == "__main__":
    main()
