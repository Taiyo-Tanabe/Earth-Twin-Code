# Earth Twin — 確率的世界モデル

> 世界は複雑系だ。政治的決断だけで紛争やクーデターが起きるのではなく、経済崩壊・ガバナンス劣化・隣国の不安定化・気候ストレス・食料危機・難民流出——無数の要因が絡み合い、臨界点を超えたとき事態は動く。
>
> Earth Twin は、そのすべての要因を同時に観測し、世界の現在の状態をできる限り忠実に再現しようとするシステムだ。出力は確率であり、予言ではない。

![version](https://img.shields.io/badge/version-0.2-00d2aa?style=flat-square)
![license](https://img.shields.io/badge/license-MIT-blue?style=flat-square)
![Python](https://img.shields.io/badge/python-3.11-blue?style=flat-square)
![React](https://img.shields.io/badge/react-18-61dafb?style=flat-square)
![XGBoost](https://img.shields.io/badge/XGBoost-ROC--AUC_0.977-orange?style=flat-square)

**ライブデモ:** https://earth-twin-tt.vercel.app

---

## 概要

| 項目 | 内容 |
|---|---|
| 対象国数 | 266カ国・地域 |
| 学習データ期間 | 1990–2024年 |
| 予測タスク | 紛争発生確率 / クーデター試み確率 |
| 予測精度 | 紛争 ROC-AUC **0.977** · クーデター ROC-AUC **0.825** |
| 予測年 | 2026年・2027年（UI で切り替え可能） |
| データソース | 13種以上のリアルタイムソース + AI自律発見 |
| 月間コスト | **$0**（全サービス無料プラン） |

---

## 技術スタック

### フロントエンド
- **React 18** + **TypeScript** + **Vite**
- **Leaflet** / **React-Leaflet** — インタラクティブな世界地図
- レスポンシブ対応（デスクトップ・モバイル両対応）
- ダークモード AIダッシュボード UI（グリッドテクスチャ・スキャンライン・ヴィネット）

### バックエンド
- **FastAPI** — REST API（`/global_map?year=`・`/country/{code}`・`/health`）
- **XGBoost** + **Platt Calibration** — 確率出力に調整された機械学習モデル
- **Walk-Forward Validation** — 時系列データに適した交差検証
- **SQLAlchemy** + **Neon (PostgreSQL)** — 予測結果の永続化

### データエンジニアリング
- 9ステップの ETL パイプライン（UCDP / V-Dem / World Bank / WGI / UNHCR / GDELT）
- **Upstash Redis Streams** — リアルタイムデータのメッセージキュー
- **Claude AI (Data Scout)** — 6時間ごとに新規オープンデータを自律発見・統合
- **GitHub Actions** — 年次モデル再学習の完全自動化

### インフラ
| サービス | 役割 | プラン |
|---|---|---|
| Vercel | フロントエンドホスティング | 無料 |
| Render | FastAPI バックエンド | 無料 |
| Neon | PostgreSQL（予測DB） | 無料 |
| Upstash | Redis Streams | 無料 |
| Railway | バックグラウンドワーカー | 無料 ($5/月クレジット内) |

---

## アーキテクチャ

```
┌─────────────────────────────────────────────────────────────┐
│                  Vercel (フロントエンド)                      │
│   React + Leaflet  ·  年別予測セレクタ  ·  Arcゲージ          │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTPS /global_map?year=2026|2027
┌──────────────────────────▼──────────────────────────────────┐
│                  Render (FastAPI)                            │
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
│  ├─ Data Scout（6時間ごと）                                  │
│  │   Claude が新データソースを自律発見・コード生成・検証・統合   │
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

## 機械学習モデル

### 設計の考え方

年次パネルデータ（country × year）を入力とし、**N年先の紛争・クーデター発生確率**を予測する。ラベルシフトを動的に計算することで、データが古くても現在から見て意味のある予測年を指し続ける。

```
horizon = 今年 − データ最新年 + n
例: データ年 2024、現在 2026:
    n=1 → shift(-2) → 2026年モデル  (ROC-AUC 0.977)
    n=2 → shift(-3) → 2027年モデル  (ROC-AUC 0.976)
```

### 紛争モデル (XGBoost + Platt Calibration)

| 項目 | 内容 |
|---|---|
| ラベル | UCDP GED: 年25件以上の戦闘死者 |
| 主要特徴量 | WGI 政治安定性・V-Dem 民主主義・GDP 成長率・紛争ラグ・隣国スピルオーバー |
| バリデーション | Walk-Forward (1990–2022) |
| ROC-AUC | **0.977** |
| Brier Score | 0.040 |

### クーデターモデル (XGBoost)

| 項目 | 内容 |
|---|---|
| ラベル | Powell-Thyne クーデター試み（1950年〜） |
| クラス不均衡対処 | `scale_pos_weight` 動的計算（約138倍）|
| ROC-AUC | **0.825** |

### 総合リスクスコア

```
risk_score = conflict_probability × 0.6 + regime_change_probability × 0.4
```

---

## 主な実装上の工夫

### 1. Data Scout（AI自律データ発見）
Claude が毎6時間、新たなオープンデータソースを自律的に探索・評価・コード生成・検証し、品質基準を満たしたデータを自動統合する。Railway コンテナが再起動しても Neon の `scout_registry` / `scout_features` テーブルから復元される。

### 2. 複数予測年の並列提供
2026年・2027年の2モデルを保持し、`GET /global_map?year=2026` のように年別に予測を取得できる。UI にはツールバーの年セレクタが表示され、ワンクリックで比較可能。`available_years` フィールドで利用可能な年をクライアントに通知する。

### 3. 年次自動再学習（GitHub Actions）
毎年2月（UCDP更新）と4月（V-Dem更新）に CI が自動起動し、データ取得からモデル学習・Neon 更新・git push まで無人で完結する。

### 4. $0 フルスタック運用
全コンポーネントを無料プランで構成。月額コスト $0 のまま 266カ国の常時監視を実現。

---

## データソース

### 年次学習データ

| ソース | 内容 |
|---|---|
| UCDP GED | 武力紛争イベント（1989年〜） |
| Powell-Thyne | クーデター試みデータベース（1950年〜） |
| V-Dem | 民主主義指標 |
| World Bank WDI | GDP・インフレ・失業率・軍事費 |
| WGI | ガバナンス 6指標（政治安定・腐敗・法の支配等） |
| UNHCR | 難民・国内避難民数 |

### リアルタイムストリーミング

| ソース | ドメイン | 間隔 |
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

## API

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
| 新データソース発見 | 6時間ごと | Data Scout (Claude) |
| モデル再学習 | **年1〜2回（自動）** | GitHub Actions |

---

## ローカル開発

```bash
git clone https://github.com/Taiyo-Tanabe/Earth-Twin-Code.git
cd Earth-Twin-Code

# フロントエンド
cd frontend
cp .env.local.example .env.local   # VITE_API_URL を設定
npm install && npm run dev

# バックエンド API
cd backend
pip install -r requirements.txt
python -m uvicorn api.main:app --reload --port 8001
```

---

## ライセンス

MIT
