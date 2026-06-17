# Earth Twin — 確率的世界モデル

政治・経済・気象・社会など、複雑に絡み合う世界の要因をできる限り再現し、各国のリスクを確率として示すシステム。

![version](https://img.shields.io/badge/version-0.1-00d2aa?style=flat-square) ![license](https://img.shields.io/badge/license-MIT-blue?style=flat-square) ![Python](https://img.shields.io/badge/python-3.11-blue?style=flat-square) ![React](https://img.shields.io/badge/react-18-61dafb?style=flat-square)

---

## ライブ

| | URL |
|---|---|
| **アプリ** | https://earth-twin-tt.vercel.app |
| **API** | https://earth-twin-api.onrender.com/global_map |

---

## アーキテクチャ

```
┌─────────────────────────────────────────────────────────────┐
│                  Vercel (フロントエンド)                      │
│   React + Leaflet  ·  3層リスクマップ  ·  Arcゲージ           │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTPS (VITE_API_URL)
┌──────────────────────────▼──────────────────────────────────┐
│                  Render (バックエンド API)                    │
│   FastAPI  ·  /global_map  ·  /country/{code}  ·  /health   │
└──────────────────────────┬──────────────────────────────────┘
                           │ PostgreSQL (DATABASE_URL)
┌──────────────────────────▼──────────────────────────────────┐
│                  Neon (データベース)                          │
│   risk_predictions  ·  raw_signals                          │
└──────────────────────────▲──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│                  Railway (バックグラウンドワーカー)            │
│                                                             │
│  ┌─ コレクター (13ソース、常時稼働スレッド)                    │
│  │   地震 · GDELT · 気象 · 太陽活動 · 山火事                  │
│  │   海水温 · WHO · 食料 · バッタ · コモディティ               │
│  │   経済 · UCDP · V-Dem · 世界銀行                          │
│  │           │ XADD                                         │
│  │    ┌──────▼──────┐                                       │
│  │    │Upstash Redis│  (Streams)                            │
│  │    └──────┬──────┘                                       │
│  │           │ XREAD                                        │
│  ├─ ストリームプロセッサ → Neon raw_signals                   │
│  │   (500行蓄積で予測を自動トリガー)                           │
│  │                                                          │
│  ├─ Data Scout (6時間ごと)                                   │
│  │   Claude が新データソースを5件発見・統合                     │
│  │                                                          │
│  └─ 日次予測 (24時間ごと)                                    │
│      学習済みモデルで全国予測 → Neon risk_predictions 更新     │
└─────────────────────────────────────────────────────────────┘
```

---

## インフラ

| レイヤー | サービス | プラン |
|---|---|---|
| フロントエンド | Vercel | 無料 |
| バックエンド API | Render | 無料（アイドル時スリープ） |
| データベース | Neon | 無料 |
| メッセージキュー | Upstash Redis | 無料（50万コマンド/月） |
| バックグラウンドワーカー | Railway | 無料（$5クレジット/月） |

**月額 $0**（Railway の $5 クレジット内で収まる見込み）

---

## リスクレイヤー

| レイヤー | データソース | 説明 |
|---|---|---|
| **総合リスク** | 複合 | 紛争 × 0.6 + クーデター × 0.4 |
| **紛争リスク** | UCDP GED | 年25件以上の戦闘死者 |
| **クーデターリスク** | Powell-Thyne | 1950年以降のクーデター試み |

---

## データソース

### 年次学習データ（ローカルパイプライン）

| ソース | ドメイン |
|---|---|
| UCDP GED | 武力紛争イベント |
| Powell-Thyne Coups | クーデター試み |
| V-Dem | 民主主義指標 |
| World Bank WDI | GDP・インフレ・失業率 |
| WGI | ガバナンス指標 |
| UNHCR | 難民・国内避難民 |

### ストリーミングソース（常時稼働、Railwayワーカー）

| ソース | ドメイン | 間隔 |
|---|---|---|
| USGS 地震 | 物理 | 60秒 |
| GDELT v2 | ニュース・社会 | 15分 |
| Open-Meteo | 気象 | 1時間 |
| NOAA SWPC | 太陽活動 | 1時間 |
| NASA FIRMS | 山火事 | 24時間 |
| NOAA Nino3.4 | 海水温 | 24時間 |
| WHO GHO | 疾病 | 24時間 |
| World Bank 価格 | 食料 | 24時間 |
| FAO 砂漠バッタ | 生態 | 24時間 |
| コモディティ価格 | 経済 | 6時間 |
| World Bank シグナル | 経済 | 6時間 |

### 自律的発見（Data Scout、6時間ごと）

Claudeが毎6時間、新しいオープンデータソースを5件発見・統合する。対象ドメインは社会系に限らず物理・生物・生態系・経済系すべて。

---

## モデル

### 紛争リスク（XGBoost + Platt calibration）
- ラベル: UCDP GED 紛争発生（年25件以上の戦闘死者）
- 特徴量: WGIガバナンス、V-Dem民主主義、経済指標、紛争履歴ラグ、隣国スピルオーバー、GDELTシグナル
- バリデーション: ウォークフォワード（1990–2022）

### クーデターリスク（XGBoost + Platt calibration）
- ラベル: Powell-Thyne クーデター試み
- クラス不均衡: scale_pos_weight 約132倍（陽性率 約0.75%）
- ラベルシフト: shift(-2)（2年先予測）

---

## 更新サイクル

| 更新内容 | タイミング | 方法 |
|---|---|---|
| 生シグナル | 常時 | Railwayコレクター → Upstash → Neon |
| 予測値 | 24時間ごと | Railway 日次予測 → Neon |
| 新データソース | 6時間ごと | Railway Data Scout（Claude） |
| モデル再学習 | **年1回（自動）** | GitHub Actions → Neon → git push |

### 予測ホライズン

予測期間は「今日から1年後」。ラベルシフトを動的計算:

```
horizon = 現在年 − データ最新年
例: データ年 2024、今 2026 → shift(-2) → 2026年の紛争を予測
```

毎年の自動再学習時にもこの計算が適用されるため、データが更新されても予測期間はつねに「今年」を指す。

---

## 年次自動更新（GitHub Actions）

毎年2月1日（UCDP更新）と4月1日（V-Dem更新）に自動実行される:

```
.github/workflows/annual_update.yml
  ├─ データ取得（UCDP / V-Dem / WorldBank / WGI / UNHCR）
  ├─ 特徴量エンジニアリング
  ├─ XGBoost 再学習
  ├─ 予測値を Neon に書き込み
  └─ 更新済みモデルを git commit & push → Railway 自動デプロイ
```

手動実行: GitHub リポジトリの **Actions** タブ → `Annual Model Update` → `Run workflow`

必要なシークレット（`Settings > Secrets > Actions`）:

| シークレット | 説明 |
|---|---|
| `DATABASE_URL` | Neon PostgreSQL URL |

---

## ローカル開発

```bash
git clone https://github.com/Taiyo-Tanabe/Earth-Twin-Code.git
cd Earth-Twin-Code
cp .env.example .env
# .env に認証情報を記入

# フロントエンド
cd frontend && npm install && npm run dev

# バックエンド API
cd backend && pip install -r requirements.txt
uvicorn api.main:app --reload --port 8001
```

---

## API

### `GET /global_map`
```json
{
  "countries": [
    {
      "country_code": "AFG",
      "country_name": "アフガニスタン",
      "risk_score": 0.958,
      "conflict_probability_1y": 0.958,
      "regime_change_probability_1y": 0.031,
      "risk_trend": "stable",
      "top_features": ["Active conflict", "5-year conflict rate"]
    }
  ],
  "prediction_from": "2026/06/17",
  "prediction_to": "2027/06/17",
  "data_year": 2024
}
```

### `GET /health`
```json
{"status": "ok", "service": "earth-twin-api"}
```

---

## ライセンス

MIT
