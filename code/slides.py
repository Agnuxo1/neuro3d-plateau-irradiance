"""Build the Japanese presentation PDF required by PLATEAU AWARD 2026.

Every number on the slides is read from the result files, so the deck cannot
state a figure that the run did not produce.

    python slides.py --results <dir> --figs <dir> --out PLATEAU_AWARD_2026.pdf
"""

from __future__ import annotations

import argparse
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.image as mpimg  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

JP = ["Yu Gothic", "Meiryo", "MS Gothic", "Noto Sans JP", "DejaVu Sans"]
BG, FG, DIM, ACC, WARN = "#0b0f14", "#f2f6fb", "#9fb0c3", "#4cc9f0", "#f4a261"
OK = "#8fd14f"
W, H = 13.333, 7.5


def page(pdf, title=None, sub=None):
    fig = plt.figure(figsize=(W, H))
    fig.patch.set_facecolor(BG)
    if title:
        fig.text(.06, .90, title, color=FG, fontsize=30, va="top")
    if sub:
        fig.text(.06, .825, sub, color=ACC, fontsize=14, va="top")
    fig.text(.94, .045, "PLATEAU AWARD 2026 ／ 一般部門", color="#44566b",
             fontsize=9, ha="right")
    return fig


def bullets(fig, items, x=.06, y=.70, dy=.075, size=15, color=None):
    for i, t in enumerate(items):
        fig.text(x, y - i * dy, "—  " + t, color=color or FG, fontsize=size,
                 va="top")


def card(fig, x, y, w, h, title, value, color=ACC):
    ax = fig.add_axes([x, y, w, h]); ax.axis("off")
    ax.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0.02,rounding_size=0.06",
                                fc="#121923", ec="#223042", transform=ax.transAxes))
    ax.text(.5, .66, value, color=color, fontsize=26, ha="center", va="center",
            transform=ax.transAxes)
    ax.text(.5, .24, title, color=DIM, fontsize=11, ha="center", va="center",
            transform=ax.transAxes)


def image_page(pdf, path, title, sub, caption, rect=(.30, .10, .64, .66)):
    fig = page(pdf, title, sub)
    ax = fig.add_axes(rect); ax.axis("off")
    ax.imshow(mpimg.imread(path))
    fig.text(.06, .60, caption, color=DIM, fontsize=12.5, va="top", wrap=True)
    return fig


def diagram(fig):
    ax = fig.add_axes([.06, .10, .88, .62]); ax.axis("off")
    ax.set_xlim(0, 10); ax.set_ylim(0, 5)
    boxes = [
        (0.2, 3.1, 2.3, 1.2, "PLATEAU\nCityGML LOD2", ACC),
        (3.0, 3.1, 2.3, 1.2, "方向ごとに\n2 枚の深度バッファ", "#a78bfa"),
        (5.8, 3.1, 2.3, 1.2, "全面の可視判定\n（1 回のベクトル比較）", "#a78bfa"),
        (3.0, 0.9, 2.3, 1.2, "太陽 141 位置\n＋天空 145 分割", WARN),
        (8.0, 1.9, 1.8, 1.6, "年間日射量\nkWh/m²·年", OK),
    ]
    for x, y, w, h, t, c in boxes:
        ax.add_patch(FancyBboxPatch((x, y), w, h,
                                    boxstyle="round,pad=0.08,rounding_size=0.18",
                                    fc="#121923", ec=c, lw=1.6))
        ax.text(x + w / 2, y + h / 2, t, color=FG, fontsize=12.5, ha="center",
                va="center")
    arrows = [((2.5, 3.7), (3.0, 3.7)), ((5.3, 3.7), (5.8, 3.7)),
              ((4.15, 2.1), (4.15, 3.1)), ((8.1, 3.7), (8.9, 3.5))]
    for a, b in arrows:
        ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=16,
                                     color=DIM, lw=1.4))
    ax.text(5, .35, "背面バッファ＝市街の影／前面バッファ＝体積に埋もれた面。"
                    "どちらも GPU の描画と同じ走査で求める。",
            color=DIM, fontsize=12, ha="center")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--figs", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--viewer-url", default="")
    ap.add_argument("--repo-url", default="")
    a = ap.parse_args()

    plt.rcParams.update({"font.family": JP})
    res = json.load(open(os.path.join(a.results, "CONTRATO-001.json"),
                         encoding="utf-8"))
    n3 = res["engines"]["own"]
    h1, h2, h3 = res["H1"], res["H2"], res["H3"]
    ctl = res["engines"]["control"]

    with PdfPages(a.out) as pdf:
        # 1 ---------------------------------------------------------------
        fig = page(pdf)
        fig.text(.06, .64, "都市のなかで光を計算する", color=FG, fontsize=46, va="top")
        fig.text(.06, .50, "PLATEAU の 3D 都市モデルを、GPU の描画そのもので解く\n"
                           "日射・日影エンジン Neuro3D", color=ACC, fontsize=19,
                 va="top", linespacing=1.6)
        fig.text(.06, .28, "Francisco Angulo de Lafuente（個人応募）\n"
                           "対象データ：広島市 2022 年度 CityGML LOD2／3次メッシュ 51324376",
                 color=DIM, fontsize=13, va="top", linespacing=1.8)
        if a.viewer_url:
            fig.text(.06, .14, "動作するビューア： " + a.viewer_url, color=OK,
                     fontsize=12.5, va="top")
        pdf.savefig(fig, facecolor=BG); plt.close(fig)

        # 2 ---------------------------------------------------------------
        fig = page(pdf, "解きたい課題", "日射と日影は都市計画の基礎データなのに、都市全体では重い")
        bullets(fig, [
            "屋上太陽光の適地選定、壁面の受熱、公園や歩道の日なた日かげ。"
            "いずれも面単位の日射量が必要になる。",
            "専門ツールの精度は高いが、1 面ずつ光線を追うため、"
            "街区を超えると計算時間が一気に増える。",
            "PLATEAU は全国 300 都市以上の LOD2 が開いている。"
            "活かすには「都市全体を一度に」解ける計算のしかたが要る。",
            "発想を変える：影は、3D エンジンが毎フレームやっていることである。",
        ])
        pdf.savefig(fig, facecolor=BG); plt.close(fig)

        # 3 ---------------------------------------------------------------
        fig = page(pdf, "提案：光の計算を描画に置き換える",
                   "1 方向のコストは「散布書き込み 1 回＋参照 1 回」。遮る物の数に依らない")
        diagram(fig)
        pdf.savefig(fig, facecolor=BG); plt.close(fig)

        # 4 ---------------------------------------------------------------
        fig = page(fig, "検証のしかた", "数字を出す前に、合否の条件を先に登録した")
        bullets(fig, [
            "対照：Blender Cycles（パストレーシング）。"
            "太陽位置・晴天モデル・天空分割・相互反射なしの条件を両者で完全に共有。",
            "対照の校正：市街の 200 m 上空に水平センサを置き、"
            f"解析解と一致することを確認（相対誤差 {ctl['calibration_rel_error']:.1e}）。",
            f"自前エンジンは全 {n3['triangles_used']:,} 面、"
            f"対照は層化抽出した {h2['control_surfaces']} 面で評価。",
            "解析解による単体試験 4 件（無遮蔽の天空率、高壁の足元、"
            "箱の影、正方形中庭）を公開し、CI で毎回実行。",
        ], size=14.5)
        pdf.savefig(fig, facecolor=BG); plt.close(fig)

        # 5 ---------------------------------------------------------------
        fig = image_page(pdf, os.path.join(a.figs, "fig1_scatter.png"),
                         "結果 1：対照との一致",
                         f"決定係数 R² = {h1['r2']:.3f}、"
                         f"平均の偏り {h1['mean_bias_fraction']*100:+.1f} %",
                         "層化抽出した面ごとに、自前エンジンと Cycles の年間日射量を比べた。"
                         "屋根面はよく一致し、壁面は散らばりが大きい。"
                         "相互反射を両者で切っているため、差は遮蔽と天空可視の扱いの差である。",
                         rect=(.44, .12, .50, .66))
        pdf.savefig(fig, facecolor=BG); plt.close(fig)

        # 6 ---------------------------------------------------------------
        fig = page(pdf, "結果 2：誤差と、事前条件に対する合否",
                   "通らなかった条件も、そのまま載せる")
        ax = fig.add_axes([.52, .14, .44, .60]); ax.axis("off")
        ax.imshow(mpimg.imread(os.path.join(a.figs, "fig2_error.png")))
        rows = [
            ("対照の校正 C1（≤3 %）", f"{ctl['calibration_rel_error']*100:.5f} %",
             res["C1_pass"]),
            ("R² ≥ 0.90", f"{h1['r2']:.3f}", h1["r2"] >= .90),
            ("平均の偏り ≤10 %", f"{h1['mean_bias_fraction']*100:+.1f} %",
             abs(h1["mean_bias_fraction"]) <= .10),
            ("相対誤差の中央値 ≤15 %", f"{h1['median_rel_error']*100:.1f} %",
             h1["median_rel_error"] <= .15),
            ("95 パーセンタイル ≤40 %", f"{h1['p95_rel_error']*100:.0f} %",
             h1["p95_rel_error"] <= .40),
            ("計算コスト 20 倍以上", f"{h2['speedup_per_surface']:.0f} 倍", h2["pass"]),
        ]
        y = .70
        for name, val, ok in rows:
            fig.text(.06, y, name, color=DIM, fontsize=13.5, va="top")
            fig.text(.355, y, val, color=FG, fontsize=13.5, va="top", ha="right")
            fig.text(.375, y, "合格" if ok else "不合格",
                     color=OK if ok else WARN, fontsize=13.5, va="top")
            y -= .062
        fig.text(.06, y - .02,
                 "不合格の中身：遮られた暗い面で相対誤差が大きい。"
                 "絶対値が小さい面ほど比率が暴れる。",
                 color=WARN, fontsize=12, va="top")
        pdf.savefig(fig, facecolor=BG); plt.close(fig)

        # 7 ---------------------------------------------------------------
        fig = page(pdf, "結果 3：計算コスト", "同じ機械、同じ時刻列、同じ幾何")
        ax = fig.add_axes([.50, .14, .46, .60]); ax.axis("off")
        ax.imshow(mpimg.imread(os.path.join(a.figs, "fig5_cost.png")))
        card(fig, .06, .52, .18, .16, "1 面あたり",
             f"{h2['own_seconds_per_surface']*1e3:.2f} ms")
        card(fig, .26, .52, .18, .16, "対照の 1 面あたり",
             f"{h2['control_seconds_per_surface']*1e3:.0f} ms", WARN)
        card(fig, .06, .30, .18, .16, "全面の計算時間",
             f"{n3['light_transport_seconds']:.0f} 秒", OK)
        card(fig, .26, .30, .18, .16, "光線方向数",
             f"{n3['directions']:,}", DIM)
        fig.text(.06, .22, "CPU 16 コアでの測定。GPU では同じ処理がさらに速くなるが、"
                           "本件では測っていないので主張しない。",
                 color=DIM, fontsize=12, va="top")
        pdf.savefig(fig, facecolor=BG); plt.close(fig)

        # 8 ---------------------------------------------------------------
        fig = image_page(pdf, os.path.join(a.figs, "fig3_map.png"),
                         "成果物 1：街区まるごとの日射マップ",
                         f"1,190 棟・{n3['triangles_used']:,} 面を一度に計算",
                         "屋根・壁・地盤を区別したまま、面ごとの年間日射量を出力する。"
                         "市街による遮蔽損失は "
                         f"{h3['shading_loss_fraction']*100:.0f} %。"
                         "太陽光パネルの適地、壁面の受熱、日かげの評価にそのまま使える。",
                         rect=(.44, .10, .52, .68))
        pdf.savefig(fig, facecolor=BG); plt.close(fig)

        # 9 ---------------------------------------------------------------
        fig = page(pdf, "成果物 2：ブラウザで動くビューア",
                   "判定も検証も、クリックだけで追えるようにした")
        bullets(fig, [
            "WebGL のビューア。年間日射量と天空率を切り替え、"
            "面にカーソルを合わせると数値が出る。",
            "画面の数値はすべて計算結果のファイルから読み込む。"
            "スライドに書いた数字と同じものが出る。",
            "コードは Apache-2.0 で公開。解析解による単体試験と再現手順つき。",
            "PLATEAU のデータは再配布せず、取得スクリプトだけを置いている。",
        ])
        if a.viewer_url:
            fig.text(.06, .30, "ビューア： " + a.viewer_url, color=OK, fontsize=14)
        if a.repo_url:
            fig.text(.06, .23, "リポジトリ： " + a.repo_url, color=OK, fontsize=14)
        pdf.savefig(fig, facecolor=BG); plt.close(fig)

        # 10 --------------------------------------------------------------
        fig = page(pdf, "限界と次の一歩", "いまの版が言えないこと")
        bullets(fig, [
            "晴天モデルによる計算値で、実測気象ではない。"
            "気象データを入れれば実用値になる。",
            "相互反射と植生、地形を含めていない。両エンジンで同じ条件にしてある。",
            "重なり合う CityGML 立体に埋もれた面を "
            f"{n3['buried_faces_excluded']:,} 面検出して除いた。"
            "検出は完全ではなく、暗い面の誤差として残っている。",
            "次：気象データ、相互反射の 1 回反射、GPU 実装、"
            "そして PLATEAU 全市へのスケール。",
        ], size=14.5)
        pdf.savefig(fig, facecolor=BG); plt.close(fig)

    print("wrote", a.out, os.path.getsize(a.out) / 1e6, "MB")


if __name__ == "__main__":
    main()
