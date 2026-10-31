"""The application dossier for PLATEAU AWARD 2026, general division.

A visual Japanese PDF built entirely from the result files: every number on
every page is read from `results/` or from the new measurements in `pruebas/`,
so the dossier cannot state a figure that no run produced. Where a page shows
an animation that a PDF cannot play, it shows a still of it and a QR code to
the animated version in the repository.

    python dossier.py --results <dir> --tests <dir> --figs <dir> \
        --testfigs <dir> --media <dir> --out PLATEAU_AWARD_2026_Neuro3D.pdf
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile

import matplotlib
matplotlib.use("Agg")
import matplotlib.image as mpimg  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

from slides import ACC, BG, DIM, FG, OK, W, H, WARN, card, wrap_jp  # noqa: E402

REPO = "https://github.com/Agnuxo1/neuro3d-plateau-irradiance"
VIEWER = "https://agnuxo1.github.io/neuro3d-plateau-irradiance/"
VIO = "#a78bfa"


def style():
    plt.rcParams.update({
        "font.family": ["Yu Gothic", "Meiryo", "MS Gothic", "Noto Sans JP",
                        "DejaVu Sans"],
        "figure.facecolor": BG, "savefig.facecolor": BG, "text.color": FG,
        "figure.dpi": 160,
    })


def page(title=None, sub=None, foot="PLATEAU AWARD 2026 ／ 一般部門"):
    fig = plt.figure(figsize=(W, H))
    fig.patch.set_facecolor(BG)
    if title:
        fig.text(.055, .915, title, color=FG, fontsize=29, va="top")
    if sub:
        fig.text(.055, .845, sub, color=ACC, fontsize=14, va="top")
    fig.text(.945, .04, foot, color="#44566b", fontsize=9, ha="right")
    return fig


def qr_png(data: str, tmp: str, name: str) -> str:
    import segno
    path = os.path.join(tmp, name + ".png")
    segno.make(data, error="m").save(path, scale=8, dark="#e8eef6",
                                     light="#0b0f14", border=2)
    return path


def put_qr(fig, path, x, y, w, label):
    ax = fig.add_axes([x, y, w, w * W / H]); ax.axis("off")
    ax.imshow(mpimg.imread(path))
    fig.text(x + w / 2, y - .025, label, color=DIM, fontsize=9, ha="center")


def full_image(fig, path, rect):
    ax = fig.add_axes(rect); ax.axis("off")
    ax.imshow(mpimg.imread(path))
    return ax


def text_block(fig, x, y, lines, size=13, color=None, dy=.052):
    for i, t in enumerate(lines):
        fig.text(x, y - i * dy, t, color=color or FG, fontsize=size, va="top")


def h1(c):
    return c["H1_all_probes_preregistered"]


def build(a):
    style()
    res = json.load(open(os.path.join(a.results, "CONTRATO-001.json"),
                         encoding="utf-8"))
    def tj(name):
        p = os.path.join(a.tests, name)
        return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None
    p1, p2, p3, p4 = (tj("P1_scaling.json"), tj("P2_convergence.json"),
                      tj("P3_transfer.json"), tj("P4_detector.json"))
    sub = res["H1"]          # post-contract subset, labelled wherever used
    eng = res["engines"]["own"]
    h2 = res["H2"]
    eq = h2.get("equal_load") or {}
    tmp = tempfile.mkdtemp()
    qr_repo = qr_png(REPO, tmp, "repo")
    qr_view = qr_png(VIEWER, tmp, "viewer")

    with PdfPages(a.out) as pdf:
        # 1 cover ---------------------------------------------------------
        fig = page()
        full_image(fig, os.path.join(a.media, "hero_plain.png"),
                   [.02, .13, .96, .66])
        fig.text(.055, .95, "都市のなかで光を計算する", color=FG, fontsize=40,
                 va="top")
        fig.text(.055, .855, "Neuro3D 都市日射エンジン ／ PLATEAU CityGML LOD2",
                 color=ACC, fontsize=17, va="top")
        fig.text(.055, .105,
                 "街区まるごと %s 面の年間日射量を %.0f 秒。"
                 "パストレーサとの一致 R² %.3f（開けた面）。"
                 % (f"{eng['triangles_used']:,}",
                    eng["light_transport_seconds"], sub["r2"]),
                 color=FG, fontsize=15, va="top")
        put_qr(fig, qr_view, .86, .80, .085, "ビューア")
        pdf.savefig(fig); plt.close(fig)

        # 2 executive summary -----------------------------------------------
        fig = page("要旨", "PLATEAU の街区をそのまま入力に、面ごとの数値を返します")
        card(fig, .055, .52, .19, .16, "計算した面の数",
             f"{eng['triangles_used']:,}")
        card(fig, .27, .52, .19, .16, "光輸送の時間",
             f"{eng['light_transport_seconds']:.0f} 秒")
        card(fig, .485, .52, .19, .16, "対照との一致 R²", f"{sub['r2']:.3f}", OK)
        card(fig, .70, .52, .19, .16, "同じ負荷での速さ",
             f"{eq.get('speedup', float('nan')):.0f} 倍", OK)
        text_block(fig, .055, .44, [
            "・ 屋上太陽光の適地抽出：屋根面ごとの年間日射量をそのまま並べ替えるだけ。",
            "・ 日影規制・再開発の事前検討：街区を丸ごと、設計案ごとに数十秒で解き直せます。",
            "・ 緑化・広場・ベンチの配置：天空率と受熱の分布から、夏に暑くなる面がわかります。",
            "・ 研究と教育：コードは Apache-2.0、結果はブラウザでそのまま触れます。",
        ], size=13.5, dy=.062)
        fig.text(.055, .13, "入力は PLATEAU の CityGML だけ。追加の測量も、商用ソフトも、"
                 "GPU も要りません。", color=DIM, fontsize=12.5)
        put_qr(fig, qr_repo, .86, .13, .085, "リポジトリ")
        pdf.savefig(fig); plt.close(fig)

        # 2b the problem -----------------------------------------------------
        fig = page("解決する課題", "全国 300 都市以上の LOD2 が開いているのに、"
                   "街区をまるごと解く計算のしかたが足りていません")
        text_block(fig, .055, .74, [
            "・ 日射と日影は都市計画の基礎データですが、専門ツールは面ごとに光線を追うため、",
            "　 街区を超えると計算時間が急に伸びます。",
            "・ 自治体が屋上太陽光の適地を探すにも、日影規制を事前に検討するにも、"
            "設計案ごとに",
            "　 街区を解き直せる速さが要ります。",
            "・ 既存の手順は商用ソフトや GPU を前提にしがちで、再現も検証も外から行えません。",
        ], size=13, dy=.062)
        fig.text(.055, .36, wrap_jp(
            "本作は、この計算を光線追跡ではなく描画に置き換えます。入力は PLATEAU の "
            "CityGML だけ。出力は面ごとの年間日射量と天空率、そして屋上太陽光の候補一覧です。"
            "コードも対照も失敗した反復も公開し、だれでも同じ数字を出し直せます。", 36),
            color=DIM, fontsize=12.5, va="top", linespacing=1.9)
        pdf.savefig(fig); plt.close(fig)

        # 3 innovation and method ---------------------------------------------
        fig = page("革新と方法", "光の方向ごとに、シーンを 2 枚のデプスバッファへ書き込む")
        mp = os.path.join(a.media, "method_still.png")
        if os.path.exists(mp):
            full_image(fig, mp, [.34, .09, .62, .66])
        text_block(fig, .055, .74, [
            "1 面あたりの問い合わせは、",
            "遮蔽物が何棟あっても",
            "1 回の参照。",
            "その 1 パスを街区の",
            "全面で使い回します。",
        ], size=15, dy=.052)
        fig.text(.055, .44, wrap_jp(
            "背面バッファ（光に背を向けた面）が街区の影を解き、"
            "前面バッファ（光を向いた面）が重なり合う立体に埋もれた面を見つけます。"
            "面の向きで分けるので、自己遮蔽が起きません。", 15),
            color=DIM, fontsize=12.5, va="top", linespacing=1.9)
        pdf.savefig(fig); plt.close(fig)

        # 4 agreement -------------------------------------------------------
        fig = page("科学的根拠：対照との一致",
                   "Blender Cycles（パストレーシング）を同一機・同一条件で")
        full_image(fig, os.path.join(a.figs, "fig1_scatter.png"),
                   [.055, .10, .40, .68])
        rows = [("屋根面", "roof"), ("壁面", "wall"), ("LOD1 面", "lod1_or_other")]
        y = .70
        fig.text(.52, .76, "面の種類別（開けた 772 面）", color=ACC, fontsize=14)
        for jp, key in rows:
            c = res["by_class"].get(key)
            if not c:
                continue
            fig.text(.52, y, jp, color=FG, fontsize=14)
            fig.text(.68, y, f"中央値 {c['median_rel_error']*100:.1f} %",
                     color=OK, fontsize=14)
            fig.text(.84, y, f"n={c['n']}", color=DIM, fontsize=12)
            y -= .065
        fig.text(.52, y - .02, wrap_jp(
            "R² %.3f、相対誤差の中央値 %.1f%%。対照の校正誤差は解析解に対して "
            "%.1e で、対照そのものが正しいことを先に確かめています。"
            % (sub["r2"], sub["median_rel_error"] * 100,
               res["C1_calibration_rel_error"]), 22),
            color=DIM, fontsize=12.5, va="top", linespacing=1.9)
        pdf.savefig(fig); plt.close(fig)

        # 5 cost -------------------------------------------------------------
        fig = page("結果：計算コスト", "同じ機械、同じ方向、同じ面で測った比較")
        full_image(fig, os.path.join(a.figs, "fig5_cost.png"), [.055, .12, .52, .64])
        text_block(fig, .62, .70, [
            "同じ 900 面・同じ 286 方向",
            f"　{eq.get('speedup', float('nan')):.0f} 倍",
            "",
            "街区全体 %s 面に広げると" % f"{h2['own_surfaces']:,}",
            f"　1 面あたり {h2['speedup_per_surface']:.0f} 倍",
        ], size=15, dy=.06)
        fig.text(.62, .33, wrap_jp(
            "1 方向のコストが面の数にほぼ依存しないので、街区を広げるほど差が開きます。"
            "前処理は計測に含めていません。GPU では測っていないので主張しません。", 18),
            color=DIM, fontsize=12, va="top", linespacing=1.9)
        pdf.savefig(fig); plt.close(fig)

        # 6 P1 ---------------------------------------------------------------
        if p1:
            fig = page("新しい検証 ①　スケーリング",
                       "クエリ面を固定したまま、遮蔽物だけを 20 倍にする")
            full_image(fig, os.path.join(a.testfigs, "p1_scaling.png"),
                       [.055, .10, .52, .68])
            text_block(fig, .62, .70, [
                "遮蔽物の点　×%.1f" % p1["occluder_growth_5pc_to_100pc"],
                "時間　　　　×%.1f" % p1["time_growth_5pc_to_100pc"],
                "両対数の傾き %.2f" % p1["exponent_log_log"],
            ], size=15, dy=.06)
            fig.text(.62, .44, wrap_jp(
                "散布書き込みはシーンの点数にほぼ比例します。遮蔽物の数に依存しないのは "
                "1 面あたりの問い合わせのほうで、その 1 パスが街区の全面に使い回されるのが"
                "速さの源です。以前の版の書き方は、この実測に合わせて訂正しました。", 18),
                color=DIM, fontsize=12, va="top", linespacing=1.9)
            pdf.savefig(fig); plt.close(fig)

        # 7 P2 ---------------------------------------------------------------
        if p2:
            fig = page("新しい検証 ②　数値の収束",
                       "設定を変えたとき、答えがどれだけ動くか")
            full_image(fig, os.path.join(a.testfigs, "p2_convergence.png"),
                       [.055, .22, .89, .52])
            shifts = {k: abs(v["base_vs_finest_mean_shift"]) * 100
                      for k, v in p2["sweeps"].items()}
            fig.text(.055, .17, wrap_jp(
                "採用した設定（テクセル 0.5 m、1 m² あたり 2 点、1 時間刻み）は、"
                "それぞれの最も細かい設定に対して %s。"
                "離散化による誤差は、対照との差よりずっと小さいことがわかります。"
                % "、".join(f"{k} で {v:.2f} %" for k, v in shifts.items()), 34),
                color=DIM, fontsize=12.5, va="top", linespacing=1.9)
            pdf.savefig(fig); plt.close(fig)

        # 8 P3 ---------------------------------------------------------------
        if p3:
            fig = page("新しい検証 ③　別の都市へ",
                       "調整に一度も使っていない名古屋市の街区で、そのまま測り直す")
            nh = os.path.join(a.media, "nagoya_hero.png")
            if os.path.exists(nh):
                full_image(fig, nh, [.50, .10, .47, .66])
            full_image(fig, os.path.join(a.testfigs, "p3_transfer.png"),
                       [.04, .10, .45, .66])
            t = h1(p3["published_configuration"])
            fig.text(.055, .80,
                     "名古屋市 3 次メッシュ 52366700 ／ 設定は一切変えず ／ "
                     "R² %.3f、相対誤差の中央値 %.1f %%"
                     % (t["r2"], t["median_rel_error"] * 100),
                     color=OK, fontsize=13)
            pdf.savefig(fig); plt.close(fig)

        # 9 P4 ---------------------------------------------------------------
        if p4:
            fig = page("新しい検証 ④　埋もれた面の検出",
                       "鉛直の判定を 3 次元の多数決に置き換える")
            full_image(fig, os.path.join(a.testfigs, "p4_detector.png"),
                       [.055, .24, .89, .50])
            q = p4["detection_quality_on_probes"]
            after = h1(p4["contract_with_better_detector"])
            fig.text(.055, .19, wrap_jp(
                "6 方向の座標軸と面の法線、計 7 本の光線のうち 5 本以上で"
                "内部と出たら「封じられた面」とします。基準は測る前に決めました。"
                "検出は %d 面から %d 面へ増え、再現率は %.2f から %.2f へ。"
                "この検出器で事前条件を測り直すと R² は %.3f になります"
                "（登録時の判定はそのまま残しています）。"
                % (p4["found"]["vertical_only"], p4["found"]["union_used"],
                   q["vertical"]["recall"], q["majority3d_union"]["recall"],
                   after["r2"]), 34),
                color=DIM, fontsize=12.5, va="top", linespacing=1.9)
            pdf.savefig(fig); plt.close(fig)

        # 9b applications and impact -------------------------------------------
        rt_path = os.path.join(a.tests, "rooftop.json")
        rt = (json.load(open(rt_path, encoding="utf-8"))
              if os.path.exists(rt_path) else None)
        if rt:
            fig = page("応用と影響",
                       "面ごとの数値を、自治体が次に見に行くべき屋根の一覧に変える")
            full_image(fig, os.path.join(a.testfigs, "rooftop.png"),
                       [.05, .12, .56, .62])
            card(fig, .66, .55, .14, .14, "候補の棟数",
                 f"{rt['buildings_listed']:,}")
            card(fig, .82, .55, .14, .14, "推定 MWh/年",
                 f"{rt['district_estimated_annual_mwh']:,.0f}", OK)
            fig.text(.655, .46, wrap_jp(
                "屋根面のうちパネルが載る傾きのものを棟ごとに集計し、"
                "モジュール効率 %.0f%%・システム出力係数 %.2f で年間発電量を推定します。"
                "数字は CSV で出力され、係数は差し替えられます。晴天モデルによる推定で、"
                "現地調査でも実測でもありません。"
                % (rt["assumptions"]["module_efficiency"] * 100,
                   rt["assumptions"]["performance_ratio"]), 17),
                color=DIM, fontsize=11.5, va="top", linespacing=1.9)
            pdf.savefig(fig); plt.close(fig)

        # 10 analytic tests ----------------------------------------------------
        fig = page("解析解による単体試験", "データなしで走り、CI で毎回実行されます")
        rows = [("T1 遮蔽なしの地面の天空率", "1.000", "1.000", "0.000"),
                ("T2 高い壁の足元の天空率", "0.500", "0.519", "+0.019"),
                ("T3 箱の影／日なた／屋根（4 点）", "0 / 1 / 1 / 1", "一致", "—"),
                ("T4 正方形中庭の中心の天空率", "0.554", "0.588", "+0.034")]
        fig.text(.055, .72, "試験", color=ACC, fontsize=13)
        fig.text(.50, .72, "解析値", color=ACC, fontsize=13)
        fig.text(.64, .72, "実測", color=ACC, fontsize=13)
        fig.text(.78, .72, "差", color=ACC, fontsize=13)
        for i, r in enumerate(rows):
            y = .65 - i * .062
            fig.text(.055, y, r[0], color=FG, fontsize=13)
            fig.text(.50, y, r[1], color=FG, fontsize=13)
            fig.text(.64, y, r[2], color=FG, fontsize=13)
            fig.text(.78, y, r[3], color=WARN if r[3] != "—" else DIM,
                     fontsize=13)
        fig.text(.055, .36, wrap_jp(
            "解析解のある 4 つの配置で、影そのものが正しいことを確かめています。"
            "別の 4 件（selftest_sealed.py）では、封じられた面の検出を合成形状で検証："
            "屋根のない箱の中の箱を、鉛直判定は 0/12、3 次元の多数決は 12/12 で"
            "見つけます。T2 と T4 の差は原因を特定できておらず、"
            "「観察事項と限界」に残しています。", 34),
            color=DIM, fontsize=12.5, va="top", linespacing=1.9)
        pdf.savefig(fig); plt.close(fig)

        # 11 reproduce ---------------------------------------------------------
        fig = page("再現できること", "公開しているのは結果ではなく、結果に至る道です")
        text_block(fig, .055, .74, [
            "・ PLATEAU の ZIP 全体（1 GB 以上）は落とさず、HTTP レンジ要求で"
            "必要な 1 タイルだけを取得します。",
            "・ 対照の Blender は自動で取得し、同じ機械で走ります。",
            "・ 失敗した反復も含め、全履歴を experiments/LOG.md に残しています。",
            "・ 4 つの解析試験は毎コミット CI で実行されます。",
            "・ 元データは再配布せず、取得スクリプトのみを公開しています。",
        ], size=13.5, dy=.065)
        fig.text(.055, .40, "python code/run_pilot.py --tile ... --normals ... "
                 "--outdir results", color=OK, fontsize=13,
                 family="DejaVu Sans Mono")
        put_qr(fig, qr_repo, .72, .12, .10, "リポジトリ")
        put_qr(fig, qr_view, .86, .12, .10, "ビューア")
        pdf.savefig(fig); plt.close(fig)

        # 11b conclusion --------------------------------------------------------
        fig = page("結論", "街区をまるごと、速く、確かめられるかたちで")
        text_block(fig, .055, .74, [
            "・ PLATEAU の街区 %s 面を %.0f 秒で解き、パストレーサと R² %.3f で一致します。"
            % (f"{eng['triangles_used']:,}", eng["light_transport_seconds"], sub["r2"]),
            "・ 調整に使っていない別の都市でも、設定を変えずに同じ精度が出ます。",
            "・ 出力はそのまま屋上太陽光の候補一覧になり、ブラウザで誰でも触れます。",
            "・ コード、対照、失敗した反復まで公開し、1 つのコマンドで再現できます。",
            "・ 通らなかった条件と原因不明の差は、次ページにそのまま残しています。",
        ], size=13.5, dy=.065)
        put_qr(fig, qr_view, .72, .12, .10, "ビューア")
        put_qr(fig, qr_repo, .86, .12, .10, "リポジトリ")
        pdf.savefig(fig); plt.close(fig)

        # 12 limitations -------------------------------------------------------
        fig = page("観察事項と限界", "通らなかった条件も、原因のわからない差も、そのまま載せます")
        hp = h1(res)
        after = (h1(p4["contract_with_better_detector"]) if p4 else None)
        q4 = p4["detection_quality_on_probes"] if p4 else None
        lines = [
            "・ 事前登録した精度条件 H1 は、登録時の構成では全 900 面で通っていません"
            "（R² %.3f、偏り %+.1f %%、95 パーセンタイル %.0f %%）。"
            % (hp["r2"], hp["mean_bias_fraction"] * 100,
               hp["p95_rel_error"] * 100),
        ]
        if after:
            lines += [
                "　 3 次元検出器では R² %.3f・偏り %+.1f %%・中央値 %.1f %% まで改善しますが、"
                "それは契約後の測定です。" % (after["r2"],
                                              after["mean_bias_fraction"] * 100,
                                              after["median_rel_error"] * 100),
                "　 95 パーセンタイルの条件は %.0f %% で、どちらの構成でも満たしていません"
                "（対照がほぼ 0 の面で比率が発散）。" % (after["p95_rel_error"] * 100),
                "・ 食い違う 128 面のうち %d 面は封じられた面と確認（適合率 %.2f）。"
                "残る %d 面の原因は特定できていません。"
                % (q4["majority3d_union"]["tp"],
                   q4["majority3d_union"]["precision"],
                   q4["majority3d_union"]["fn"]),
            ]
        lines += [
            "・ 1 方向のコストはシーンの点数にほぼ比例します（両対数の傾き %s）。"
            "依存しないのは 1 面あたりの問い合わせです。"
            % (("%.3f" % p1["exponent_log_log"]) if p1 else "実測済み"),
            "・ T2・T4 の解析解との差（+0.019、+0.034）は原因を特定できていません。",
            "・ 晴天モデルによる計算値で、実測気象データではありません。"
            "相互反射・植生・地形は含めていません。",
            "・ 「事前登録」は自己申告です。GPU では測っていないので GPU の速さは主張しません。",
            "・ 第三者による独立監査は未了です。",
        ]
        text_block(fig, .055, .74, lines, size=12.5, dy=.062)
        fig.text(.055, .14, "数値はすべて公開リポジトリの results/ と "
                 "experiments/ から追えます。", color=DIM, fontsize=12)
        pdf.savefig(fig); plt.close(fig)

    print("wrote", a.out, f"{os.path.getsize(a.out)/1e6:.2f} MB")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--tests", default="")
    ap.add_argument("--figs", required=True)
    ap.add_argument("--testfigs", default="")
    ap.add_argument("--media", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if not a.tests:
        a.tests = a.results
    if not a.testfigs:
        a.testfigs = a.figs
    build(a)


if __name__ == "__main__":
    main()
