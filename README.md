# Earth Twin — 確率的世界リスクモデル

**世界266カ国の紛争・クーデターリスクをリアルタイムで可視化するフルスタック機械学習プロジェクトです。**

XGBoost で学習した予測モデルが、GDP・民主主義指標・難民数など13種以上のデータソースをもとに各国のリスクを0〜100%の確率で算出します。予測結果はインタラクティブな世界地図にリアルタイムで表示され、国をクリックするとリスク要因の詳細を確認できます。

![version](https://img.shields.io/badge/version-0.2-00d2aa?style=flat-square)
![license](https://img.shields.io/badge/license-MIT-blue?style=flat-square)
![Python](https://img.shields.io/badge/python-3.11-blue?style=flat-square)
![React](https://img.shields.io/badge/react-18-61dafb?style=flat-square)
![XGBoost](https://img.shields.io/badge/XGBoost-ROC--AUC_0.977-orange?style=flat-square)

**ライブデモ:** https://earth-twin-tt.vercel.app

---

## 主な特徴

| 項目 | 内容 |
|---|---|
| 対象国数 | 266カ国・地域 |
| 学習データ期間 | 1990〜2024年 |
| 予測タスク | 紛争発生確率・クーデター試み確率 |
| 予測精度 | 紛争 ROC-AUC **0.977** · クーデター ROC-AUC **0.825** |
| 予測年 | 2026年・2027年（UI で切り替え可能） |
| 月間コスト | **ほぼ $0**（Vercel・Railway・Neon・Upstash は無料プラン。Data Scout の Claude Haiku API は月1回の実行で約 $0.01） |

---

## 技術スタック

### フロントエンド
- **React 18 + TypeScript + Vite** でビルドし、**Leaflet** でインタラクティブな世界地図を実現しています。
- デスクトップとモバイルの両方に対応しており、モバイルではハンバーガーメニューを採用しています。
- ダークモードのダッシュボード UI（グリッドテクスチャ・スキャンライン・ヴィネット）で、リアルタイム監視システムの雰囲気を表現しています。

### バックエンド
- **FastAPI** で REST API を構築しています（`/global_map?year=`・`/country/{code}`・`/health`）。
- **XGBoost + Platt Calibration** により、モデルの出力を正確な確率値に変換しています。
- **Walk-Forward Validation**（時系列専用の交差検証）でモデルの汎化性能を評価しています。
- **SQLAlchemy + Neon (PostgreSQL)** で予測結果を永続化しています。

### データパイプライン
- UCDP・V-Dem・World Bank・WGI・UNHCR・GDELT など複数のオープンデータを統合する 9ステップの ETL パイプラインを構築しています。
- **Upstash Redis Streams** でリアルタイムデータをキューイングしています。
- **Claude AI（Data Scout）** が月次で新しいオープンデータソースを自律的に発見し、テンプレートベースのコード生成で品質基準を満たしたものを自動で統合します。
- **GitHub Actions** で年次のモデル再学習を完全自動化しています。

### インフラ（すべて無料プラン）

| サービス | 役割 |
|---|---|
| Vercel | フロントエンドホスティング |
| Railway | FastAPI バックエンド・バックグラウンドワーカー |
| Neon | PostgreSQL（予測 DB） |
| Upstash | Redis Streams |

---

## システム構成

```
┌─────────────────────────────────────────────────────────────┐
│                  Vercel (フロントエンド)                      │
│   React + Leaflet  ·  年別予測セレクタ  ·  国別詳細パネル     │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTPS /global_map?year=2026|2027
┌──────────────────────────▼──────────────────────────────────┐
│                  Railway (FastAPI)                           │
│   /global_map?year=  ·  available_years[]  ·  /health       │
└──────────────────────────┬──────────────────────────────────┘
                           │ PostgreSQL
┌──────────────────────────▼──────────────────────────────────┐
│                  Neon (PostgreSQL)                           │
│   risk_predictions (country × year × model_version)         │
│   scout_registry · scout_features                           │
└──────────────────────────▲──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│                  Railway (バックグラウンドワーカー)            │
│                                                             │
│  ┌─ コレクター（13ソース · 常時稼働スレッド）                  │
│  │   地震 · GDELT · 気象 · 太陽活動 · 山火事                  │
│  │   海水温 · WHO · 食料 · バッタ · コモディティ               │
│  │           │ XADD → Upstash Redis Streams                 │
│  ├─ ストリームプロセッサ → Neon raw_signals                   │
│  │                                                          │
│  ├─ Data Scout（月次: 毎月1日）                              │
│  │   Claude が新データソースを自律発見・テンプレートで検証・統合  │
│  │   発見データは Neon に永続化（Railway 再起動後も保持）        │
│  │                                                          │
│  └─ 日次予測（24時間ごと）                                   │
│      2026年モデル + 2027年モデルで全266カ国を予測              │
│      → Neon risk_predictions に書き込み                      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                  GitHub Actions（年次自動更新）               │
│   毎年 2月・4月: データ取得 → 特徴量生成 → XGBoost 再学習     │
│   → Neon 更新 → モデルを git commit & push                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 機械学習モデルの設計

### 予測の仕組み

年次パネルデータ（国 × 年）を入力とし、**N年先の紛争・クーデター発生確率**を予測します。
「現在のデータで将来を予測する」という構造を保つため、ラベルシフト量を動的に計算しています。

```
horizon = 今年 − データ最新年 + n

例: データ最新年 2024、現在 2026 の場合
    n=1 → shift(-2) → 2026年の予測モデル（ROC-AUC 0.977）
    n=2 → shift(-3) → 2027年の予測モデル（ROC-AUC 0.976）
```

### 紛争モデル（XGBoost + Platt Calibration）

| 項目 | 内容 |
|---|---|
| ラベル | UCDP GED: 年25件以上の戦闘死者が発生した場合を「紛争あり」と定義 |
| バリデーション | Walk-Forward Cross-Validation（1990〜2022年） |
| ROC-AUC | **0.977** |
| Brier Score | 0.040 |

**主要特徴量（重要度順）：**

| カテゴリ | 特徴量 |
|---|---|
| 紛争履歴 | `conflict_onset_lag1/2/3`（過去1〜3年の紛争有無）· `conflict_onset_rolling5y`（5年間紛争率） |
| 近傍スピルオーバー | `neighbor_conflict_avg`（隣国の紛争率加重平均） |
| ガバナンス (WGI) | `pv_est`（政治安定性）· `va_est`（発言・説明責任）· `rl_est`（法の支配）· `ge_est`（政府効率性）· `cc_est`（汚職抑制） |
| 民主主義 (V-Dem) | `v2x_polyarchy`（選挙民主主義）· `v2x_libdem`（自由民主主義） |
| 経済 | `gdp_per_capita_log`（対数 GDP）· `gdp_growth`（成長率）· `inflation`（インフレ率） |
| 人口圧力 | `refugees_per_capita`（人口あたり難民数）· `population`（人口） |

### クーデターモデル（XGBoost）

| 項目 | 内容 |
|---|---|
| ラベル | Powell-Thyne クーデターデータベース（1950年〜）に基づく |
| クラス不均衡の対処 | `scale_pos_weight` を動的計算（陰性:陽性 ≈ 138:1）|
| ROC-AUC | **0.825** |

### 総合リスクスコアの計算

```
risk_score = conflict_probability × 0.6 + regime_change_probability × 0.4
```

### 構造的脆弱性スコア（structural_risk）

モデル予測とは独立して、WGI・V-Dem・経済指標から「構造的な脆弱性」を 0〜1 で算出します。現在の紛争状態に依存しないため、平和だが不安定な国の差別化に使用します。

```
structural_risk =
  (1 − 政治安定性)  × 0.20
+ (1 − 民主主義指数) × 0.12
+ (1 − log(GDP))    × 0.12
+ (1 − 発言責任)    × 0.09
+ (1 − 法の支配)    × 0.09
+ 過去5年紛争率      × 0.09
+ 隣国紛争平均       × 0.05
+ その他（腐敗・インフレ・難民・貿易） × 0.24
```

---

## 工夫した点

### 1. AI によるデータ自律発見（Data Scout）
毎月1日に Claude が新しいオープンデータソースを探索し、テンプレートベースのコードで自動取得・検証・統合します。コード生成は Claude に頼らずテンプレートで賄うため API コストを最小化しています。

**品質検証の基準（3条件すべてを満たす必要がある）：**
- カバー国数 ≥ 50カ国
- カバー年数 ≥ 5年
- NaN 率 ≤ 40%

Railway コンテナが再起動しても Neon の `scout_registry` テーブルから復元されるため、発見済みのデータが失われることはありません。サイクルごとに最低 3件の統合を目標とし、達成するまで最大 2ラウンド繰り返します。

### 2. 複数予測年の同時提供
2026年・2027年の2つのモデルを保持しており、`GET /global_map?year=2026` のように年単位で予測を取得できます。UI のツールバーで年を切り替えるだけで比較でき、`available_years` フィールドによってクライアントが利用可能な年を動的に把握できます。

### 3. 年次自動再学習（GitHub Actions）
毎年2月（UCDP 更新）と4月（V-Dem 更新）に CI が自動起動し、データ取得 → 特徴量生成 → モデル学習 → Neon 更新 → git push まで無人で完結します。

### 4. $0 のフルスタック運用
すべてのコンポーネントを無料プランで構成しており、月額コストほぼ $0 のまま266カ国を常時監視できます。

### 5. API パフォーマンス最適化
- **GZip ミドルウェア**（minimum_size=500B）でレスポンスを約 70% 圧縮
- **TTL キャッシュ**（1時間）で parquet 読み込みと DB クエリをリクエストごとに実行しない
- **SQLAlchemy 接続プール**（pool_size=5）でモジュールレベルの接続管理を実現

---

## データソース

### 年次学習データ

| ソース | 内容 |
|---|---|
| UCDP GED | 武力紛争イベント（1989年〜） |
| Powell-Thyne | クーデター試みデータベース（1950年〜） |
| V-Dem | 民主主義指標 |
| World Bank WDI | GDP・インフレ・失業率・軍事費 |
| WGI | ガバナンス6指標（政治安定・腐敗・法の支配など） |
| UNHCR | 難民・国内避難民数 |

### リアルタイムストリーミング

| ソース | ドメイン | 更新間隔 |
|---|---|---|
| USGS 地震 | 地球物理 | 60秒 |
| GDELT v2 | ニュース・紛争イベント | 15分 |
| Open-Meteo | 気象 | 1時間 |
| NOAA SWPC | 太陽活動 | 1時間 |
| NASA FIRMS | 山火事 | 24時間 |
| NOAA Nino3.4 | 海水温 | 24時間 |
| WHO GHO | 疾病監視 | 24時間 |
| World Bank | 食料価格 | 24時間 |
| FAO | 砂漠バッタ | 24時間 |
| コモディティ市場 | 経済 | 6時間 |

---

## API リファレンス

### `GET /global_map?year=2027`

```json
{
  "countries": [
    {
      "country_code": "AFG",
      "country_name": "Afghanistan",
      "risk_score": 0.958,
      "conflict_probability_1y": 0.958,
      "regime_change_probability_1y": 0.031,
      "risk_trend": "stable",
      "top_features": ["Active conflict", "5-year conflict rate", "Political instability"]
    }
  ],
  "prediction_from": "2027/01/01",
  "prediction_to": "2027/12/31",
  "selected_year": 2027,
  "available_years": [2026, 2027],
  "data_year": 2024
}
```

### `GET /health`
```json
{"status": "ok", "service": "earth-twin-api"}
```

---

## 更新サイクル

| 内容 | タイミング | 方法 |
|---|---|---|
| リアルタイムシグナル | 常時 | Railway → Upstash → Neon |
| 日次予測 | 24時間ごと | Railway → 2年分 → Neon |
| 新データソース発見 | 月次（毎月1日） | Data Scout（Claude） |
| モデル再学習 | **年1〜2回（自動）** | GitHub Actions |

---

## ローカル開発

```bash
git clone https://github.com/Taiyo-Tanabe/Earth-Twin-Code.git
cd Earth-Twin-Code

# .env を作成（Neon の接続文字列を設定）
echo "DATABASE_URL=postgresql://..." > .env

# Docker Compose で API + フロントエンドを起動
docker compose up --build
```

| URL | サービス |
|---|---|
| http://localhost:3000 | フロントエンド（Vite dev server） |
| http://localhost:8002 | バックエンド API |

Docker を使わない場合：

```bash
# バックエンド API（ポート 8002）
cd backend
pip install -r requirements-api.txt
DATABASE_URL=postgresql://... uvicorn api.main:app --reload --port 8002

# フロントエンド
cd frontend
npm install && npm run dev
```

---

## ライセンス

MIT
