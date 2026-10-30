# Neuro3D × PLATEAU — 都市のなかで光を計算する / Urban irradiance by rasterisation

**ビューア / live viewer:** https://agnuxo1.github.io/neuro3d-plateau-irradiance/

PLATEAU の 3D 都市モデル（CityGML LOD2）に対し、**GPU の描画と同じやり方**で
日射と日影を解くエンジンと、その検証一式です。パストレーサ（Blender Cycles）を
対照に置き、事前に登録した合否条件（[CONTRATO-001](CONTRATO-001-irradiancia.md)）で
測りました。通らなかった条件もそのまま載せています。

An engine that computes urban solar irradiance on Project PLATEAU CityGML LOD2
the way a 3D engine computes light — as a rasterisation pass over the whole
scene — validated against a Blender Cycles path-traced control under
pre-registered acceptance criteria. Results that failed those criteria are
published here too.

---

## 何をしたか / What this does

対象：広島市 2022 年度 CityGML LOD2、3 次メッシュ **51324376**（平和記念公園・紙屋町周辺）。
1,190 棟、46,862 三角形。出力は面ごとの年間日射量（kWh/m²·年、直達と天空散乱に分離）と
天空率。

光の方向ごとに、シーンを面の向きで分けた **2 枚の正射投影デプスバッファ**に点群で書き込み、
全クエリ点を 1 回のベクトル比較で判定します。1 方向のコストは「散布書き込み 1 回 ＋ 参照 1 回」で、
遮蔽物の数に依存しません。

- **背面バッファ**（光に背を向けた面）＝ 市街の影。閉じた立体に入るときに必ず通る面なので、
  自己遮蔽なしに、小さな厳密バイアスで判定できます。
- **前面バッファ**（光を向いた面）＝ 体積に埋もれた面の検出。CityGML では立体が重なることが
  あり、そこから「出る」面は前面です。クエリ面自身も写るため、テクセル内の自面の奥行き幅を
  覆う傾斜バイアスを使います。

## 結果 / Results

対照：Blender Cycles 4.5.9（CPU）。太陽位置・晴天モデル（Hottel + Liu–Jordan）・
天空 145 分割・**相互反射なし**を両エンジンで共有。評価は層化抽出した 900 面。
実行は 16 コア CPU（両エンジンとも同一機・同一時刻列、太陽 141 位置＋天空 145 分割 ＝ 286 方向）。

| 事前登録した条件 | 実測 | 判定 |
|---|---|---|
| C1 対照の校正誤差 ≤ 3 %（上空の水平センサ 対 解析解） | 2.2 × 10⁻⁶ | **合格** |
| H1 決定係数 R² ≥ 0.90 | **0.977** | 合格 |
| H1 平均の偏り ≤ 10 % | **−0.5 %** | 合格 |
| H1 相対誤差の中央値 ≤ 15 % | **8.5 %** | 合格 |
| H1 相対誤差の 95 パーセンタイル ≤ 40 % | **605 %** | **不合格** |
| H2 1 面あたりの計算コスト 20 倍以上 | **1,216 倍**（0.91 ms 対 1,112 ms） | 合格 |
| H3 遮蔽が効いていること | 遮蔽損失 39.0 %、天空率 p05 0.00 / p95 0.97 | 合格 |

**H1 は総合では不合格**です。裾が理由で、面の種類で分かれます。

| 面の種類 | 比較数 | 相対誤差の中央値 | 平均の偏り | 対照の平均 |
|---|---|---|---|---|
| 屋根面 | 250 | **1.3 %** | +2.4 % | 1,445 kWh/m²·年 |
| 壁面 | 239 | 13.8 % | −3.5 % | 462 kWh/m²·年 |
| LOD1 面 | 294 | 13.7 % | −3.5 % | 835 kWh/m²·年 |

95 パーセンタイルが暴れるのは、**絶対値がごく小さい暗い面**です。対照が 1 kWh/m²·年 前後を
返す面では、わずかな差が数百 % の比率になります。900 面のうち 117 面は対照がほぼ 0 で、
比較から外れました（CityGML の立体が重なって埋もれた面。検出して除いた 1,924 面に加え、
検出しきれなかったぶん）。設計上の限界として記録します。

日射量の分布（全 44,902 面）：中央値 414、95 パーセンタイル 1,906、最大 2,205 kWh/m²·年。
平均天空率 0.44。**晴天モデルによる計算値であり、実測気象データではありません。**

![一致](docs/fig1_scatter.png)
![誤差](docs/fig2_error.png)
![日射マップ](docs/fig3_map.png)
![コスト](docs/fig5_cost.png)

## 解析解による単体試験 / Analytic self-tests

データなしで走り、CI で毎回実行されます（`code/selftest_shadow.py`）。

| 試験 | 期待値 | 実測 |
|---|---|---|
| T1 遮蔽なしの地面の天空率 | 1.000 | 1.000 |
| T2 高い壁の足元の天空率 | 0.500 | 0.519 |
| T3 箱の影／日なた／屋根（4 点） | 0 / 1 / 1 / 1 | 一致 |
| T4 正方形中庭の中心の天空率 | 0.554（解析） | 0.588 |

T2・T4 の差は天空 145 分割の離散化によるものです。拡散成分の絶対値はこの離散化を比として
使い、遮蔽なしの厳密値 DHI·(1+cos β)/2 から出すので、離散化の偏りは打ち消されます。

## 再現手順 / Reproducing

```bash
pip install -r requirements.txt
# 1. PLATEAU から必要なタイル 1 枚だけを取得（ZIP 全体はダウンロードしない）
python code/fetch_plateau.py \
  --url https://assets.cms.plateau.reearth.io/assets/ef/d3f4c5-aca6-415e-b560-d86512e004f9/34100_hiroshima-shi_city_2022_citygml_3_op.zip \
  --extract udx/bldg/51324376_bldg_6697_op.gml --out data_plateau
# 2. CityGML → 局所 ENU メートル系の三角形メッシュ
python code/citygml_mesh.py --gml data_plateau/51324376_bldg_6697_op.gml \
  --out data_plateau/tile_51324376.npz
# 3. 外向き法線と埋没面の検出（前処理。計測時間には含めない）
python code/orient_normals.py --tile data_plateau/tile_51324376.npz \
  --out data_plateau/normals_51324376.npz
# 4. 自前エンジン＋Cycles 対照＋契約の判定を一括実行（Blender は自動取得）
python code/run_pilot.py --tile data_plateau/tile_51324376.npz \
  --normals data_plateau/normals_51324376.npz --outdir results
```

`code/neuro3d_irradiance.py` は `--device cuda` で GPU でも動きますが、本リポジトリの
計測は CPU のみです。GPU の速度は測っていないので主張しません。

## このリポジトリが言えないこと / What is not claimed

- 実測日射との一致。気象データも現地測定もありません。晴天モデルの計算値です。
- この街区の外での精度。1 タイルでしか測っていません。
- 相互反射、植生、地形。両エンジンで同じように除いてあります。
- Cycles が絶対の真値であること。対照であり、512 サンプルのばらつきを持ちます。
- GPU 実装の速度。CPU 16 コアでの同一条件比較のみです。

## データとライセンス / Data and licence

PLATEAU のデータは**再配布しません**。`code/fetch_plateau.py` が HTTP レンジ要求で
必要な 1 タイル（30 MB）だけを取り出します（ZIP 全体は 1 GB）。データの利用は
[PLATEAU サイトポリシー](https://www.mlit.go.jp/plateau/site-policy/)に従います。

コードは Apache-2.0（[LICENSE](LICENSE)）。第三者の構成要素は [NOTICE](NOTICE) に記載。

## 状態 / Status

PLATEAU AWARD 2026 一般部門（国土交通省）への応募作品として作成。
本エントリー締切は 2026-11-19 23:59 JST。応募そのものは作者本人が行います。
本リポジトリの数値は 2026-10-30 の実行によるもので、独立した第三者監査は未了です。
