# 応募に添付するファイル / Qué se presenta

> ## ⚠ 送ってはいけない PDF があります
>
> **`PLATEAU_AWARD_2026_Neuro3D_VisualReview.pdf` は、現状のまま応募に使わないでください。**
> 測定によって撤回した記述が 2 か所そのまま残っているためです。
>
> | ページ | 残っている記述 | 測定した事実 |
> |---|---|---|
> | p.3 | 「遮蔽物の数に依存しません。」 | 両対数の傾き **0.943**（ほぼ線形）。依存しないのは 1 面あたりの問い合わせだけ — `pruebas/P1_scaling.json` |
> | p.8 | 128 面の原因は「**特定済み**」 | 確認できたのは **81 / 128 面**（適合率 0.95）。**47 面は原因不明** — `pruebas/P4_detector.json` |
>
> この 2 文を載せたまま提出すると、**測定していないことを審査員に主張する**ことになります。
> 同じ作品の別ビルドなので、現行の `code/dossier.py` で生成し直せば直ります。
> 悪意ではなく、4 つの測定を行う前に作られたビルドだという、ただの時系列の問題です。
>
> **No enviéis ese PDF mientras contenga esas dos frases.** Son afirmaciones que nuestras
> propias medidas desmienten; se arreglan regenerándolo con el `code/dossier.py` actual.

このフォルダには、同じ作品について作られた **2 組**の資料があります。応募フォーム
（https://form.run/@plateauaward2026-apply ）に添付できるのは **PDF 1 つと動画 1 つ**だけです。

**応募者本人が別の指示を出すまで、応募用として指定するのは次の 2 ファイルです。**

| 役割 | ファイル | 制限 | 実測 |
|---|---|---|---|
| プレゼン用スライド資料 | **`PLATEAU_AWARD_2026_Neuro3D.pdf`** | 10 MB 以内 | 15 ページ・2.40 MB |
| 作品の動作がわかる動画 | **`PLATEAU_AWARD_2026_Neuro3D.mp4`** | 3 分以内 | 1 分 46 秒・1280×720・17.7 MB |
| フォームに入力する本文 | **`application_text_ja.md`** | — | 7,809 バイト |

> The two files in bold are the ones attached to the entry form, unless the applicant says
> otherwise. The rest of this folder is additional material about the same work.

---

## 2 組の資料 / Las dos versiones

| | **A — 応募用（`main` の現行版）** | **B — Visual Review 版** |
|---|---|---|
| PDF | `PLATEAU_AWARD_2026_Neuro3D.pdf` | `PLATEAU_AWARD_2026_Neuro3D_VisualReview.pdf` |
| 本文 | `application_text_ja.md` | `PLATEAU_APPLICATION_FINAL_JA.md` |
| 作成 | Claude（このセッション）、2026-10-31 の夕方 | 別のエージェント、2026-10-31 の午後 |
| コミット | `e66ceb6` | `5a83c4a` |

### PDF の比較（数えた事実のみ）

| 項目 | A 応募用 | B Visual Review |
|---|---|---|
| ページ数 | 15 | 8 |
| ファイルサイズ（上限 10 MB） | 2.40 MB ✓ | 1.21 MB ✓ |
| 言語 | 日本語 ✓ | 日本語 ✓ |
| 本文テキストの選択・検索 | 不可（matplotlib のグリフ出力） | 不可（同上） |
| 1 要旨（エグゼクティブサマリ） | あり（p.2「要旨」） | 一部（p.2「できること」） |
| 2 解決する課題 | あり（p.3） | **なし** |
| 3 革新 | あり（p.4） | あり（p.3「考え方」） |
| 4 方法 | あり（p.4） | あり（p.3） |
| 5 科学的根拠 | あり（p.5 対照との一致、p.11 単体試験） | あり（p.4、p.6） |
| 6 結果 | あり（p.6 コスト、p.7–p.10 の P1–P4） | 一部（p.5 コストのみ） |
| 7 応用 | あり（p.12 屋上太陽光の候補） | 一部（p.2 の箇条書き） |
| 8 影響 | あり（p.12 想定利用者と街区合計） | **なし** |
| 9 結論 | あり（p.14） | **なし** |
| 10 観察事項と限界 | あり（p.15） | あり（p.8） |
| 契約後の 4 測定（P1–P4） | あり | **なし**（作成時点で未実施） |
| 別都市への移植（名古屋 R² 0.986） | あり | **なし** |

### 事実として指摘しておくこと

B の PDF は、**このセッションで 4 つの測定を行う前の版**です（同じ `code/dossier.py` の
前のビルド）。そのため、測定後に撤回した記述が 2 か所そのまま残っています。

| 箇所 | B の記述 | 測定した結果 |
|---|---|---|
| p.3 | 「遮蔽物の数に依存しません。」 | **否定された。** P1 の両対数の傾きは 0.943 で、ほぼ線形（`pruebas/P1_scaling.json`）。依存しないのは 1 面あたりの問い合わせのみ |
| p.8 | 「原因は 900 面のうち 128 面が…封じられた面であることに**特定済み**で」 | **128 面すべてについては裏づけがない。** 3 次元検出器が確認できたのは 81 面（適合率 0.95）、残る 47 面は原因不明（`pruebas/P4_detector.json`） |

### 動画の長さの食い違い

B の本文 `PLATEAU_APPLICATION_FINAL_JA.md` は動画を「**84 秒**」と書いていますが、`main` に
置いてある `PLATEAU_AWARD_2026_Neuro3D.mp4` は **1 分 46 秒（106 秒）** です。84 秒だったのは
10 月 30 日版の動画で、現物は差し替わっています。

**フォームや資料に長さを書く場合は、必ず実測値の 1 分 46 秒を書いてください。**
どちらも 3 分の上限内なので応募要項には違反しませんが、提出物の記述が現物と一致しない
のは避けます。確認方法：ブラウザで再生するか、`video2/timeline2.json`（2,544 フレーム ÷
24 fps = 106.0 秒）を見てください。

B の本文自体に撤回すべき主張はありません。「封じられた面が主因**と考えられます**」という
仮説の書き方で、これは P4 が 81 面について裏づけました。ただし
「新しい検証は既存配列に対する解析であり、別都市・別データを用いた独立した全工程の
再検証ではありません」という一文は、P3（名古屋での全工程の再実行）の後では古くなっています。

**どちらも応募要項（日本語・10 MB・3 分）には違反していません。** 違いは網羅範囲と、
B に残っている 2 つの撤回済み記述です。

### B にあって A にない価値

B と一緒に公開された `docs/independent_review_20261031.md` は、公開済みの配列に対する
3 つの解析チェック（物理的不変量、面積重み付け、層化ブートストラップ）で、
**全 900 面の R² 0.884 に 95 % 信頼区間 0.846–0.912 を与えています**。A にはない情報で、
A と競合しません。残すべき資料です。

---

## Para Fran

En `submission/` hay dos PDF y dos textos para el mismo concurso. **Solo se adjuntan uno y uno.**

- **Recomendación (A):** `PLATEAU_AWARD_2026_Neuro3D.pdf` + `application_text_ja.md`. Cubre los
  diez apartados que pide la convocatoria, incluye las cuatro medidas nuevas y la transferencia a
  Nagoya, y no contiene ninguna afirmación desmentida.
- **B** (`..._VisualReview.pdf` + `PLATEAU_APPLICATION_FINAL_JA.md`) es una versión anterior del
  mismo generador. **Ese PDF no debe enviarse mientras contenga las dos frases de la cabecera**:
  no porque sea peor, sino porque afirmaría ante el jurado dos cosas que nuestras propias
  medidas desmienten (pendiente 0,943 frente a «no depende de los oclusores», y 81 de 128 caras
  explicadas frente a «causa identificada»). Se arregla regenerándolo con el `code/dossier.py`
  actual. Su texto además dice que el vídeo dura 84 s cuando dura 1:46.
- **La revisión independiente que acompaña a B sí aporta** (intervalo de confianza del R²) y se
  queda donde está.

La elección es tuya; nada se ha borrado. Si prefieres B, hay que corregir antes esas dos frases y
la duración del vídeo.
