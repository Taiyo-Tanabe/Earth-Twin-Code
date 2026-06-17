# Earth Twin — Probabilistic World Model

Earth Twin is not a geopolitical prediction tool. It is a **copy of the world** — a probabilistic model that continuously absorbs physical, biological, ecological, economic, and social signals to reproduce the state of Earth in real time.

> *If a complex system is fully reproduced and the universe contains no true randomness, the future becomes deterministic. Since full reproduction is impossible, we express outcomes as probability.*

![version](https://img.shields.io/badge/version-0.1-00d2aa?style=flat-square) ![license](https://img.shields.io/badge/license-MIT-blue?style=flat-square) ![Python](https://img.shields.io/badge/python-3.11-blue?style=flat-square) ![React](https://img.shields.io/badge/react-18-61dafb?style=flat-square)

---

## Live

| | URL |
|---|---|
| **App** | https://earth-twin-phi.vercel.app |
| **API** | https://earth-twin-api.onrender.com/global_map |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Vercel (Frontend)                           │
│   React + Leaflet  ·  3-layer risk map  ·  Arc gauges       │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTPS (VITE_API_URL)
┌──────────────────────────▼──────────────────────────────────┐
│                  Render (Backend API)                        │
│   FastAPI  ·  /global_map  ·  /country/{code}  ·  /health   │
└──────────────────────────┬──────────────────────────────────┘
                           │ PostgreSQL (DATABASE_URL)
┌──────────────────────────▼──────────────────────────────────┐
│                  Neon (Database)                             │
│   risk_predictions  ·  raw_signals                          │
└──────────────────────────▲──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│                  Railway (Background Worker)                 │
│                                                             │
│  ┌─ Collectors (13 sources, always-on threads)              │
│  │   Earthquake · GDELT · Weather · Solar · Wildfire        │
│  │   Sea Temp · WHO · Food · Locust · Commodity             │
│  │   Economic · UCDP · V-Dem · World Bank                   │
│  │           │ XADD                                         │
│  │    ┌──────▼──────┐                                       │
│  │    │Upstash Redis│  (Streams)                            │
│  │    └──────┬──────┘                                       │
│  │           │ XREAD                                        │
│  ├─ Stream Processor → Neon raw_signals                     │
│  │   (500 rows蓄積で予測を自動トリガー)                        │
│  │                                                          │
│  ├─ Data Scout (every 6h)                                   │
│  │   Claude が新データソースを5件発見・統合                     │
│  │                                                          │
│  └─ Daily Predict (every 24h)                               │
│      学習済みモデルで全国予測 → Neon risk_predictions 更新     │
└─────────────────────────────────────────────────────────────┘
```

---

## Infrastructure

| Layer | Service | Plan |
|---|---|---|
| Frontend | Vercel | Free |
| Backend API | Render | Free (sleeps on idle) |
| Database | Neon | Free |
| Message Queue | Upstash Redis | Free (500k cmd/mo) |
| Background Worker | Railway | Free ($5 credit/mo) |

**月額 $0**（Railway の $5 クレジット内で収まる見込み）

---

## Risk Layers

| Layer | Data Source | Description |
|---|---|---|
| **Overall Risk** | Composite | Conflict × 0.6 + Coup × 0.4 |
| **Conflict Risk** | UCDP GED | 25+ battle deaths/year |
| **Coup Risk** | Powell-Thyne | Coup attempts 1950–present |

---

## Data Sources

### Core training data (annual, local pipeline)

| Source | Domain |
|---|---|
| UCDP GED | Armed conflict events |
| Powell-Thyne Coups | Coup attempts |
| V-Dem | Democracy indices |
| World Bank WDI | GDP, inflation, unemployment |
| WGI | Governance indicators |
| UNHCR | Refugee population |

### Streaming sources (always-on, Railway worker)

| Source | Domain | Interval |
|---|---|---|
| USGS Earthquake | Physical | 60s |
| GDELT v2 | News / Social | 15min |
| Open-Meteo | Weather | 1h |
| NOAA SWPC | Solar activity | 1h |
| NASA FIRMS | Wildfire | 24h |
| NOAA Nino3.4 | Sea temperature | 24h |
| WHO GHO | Disease | 24h |
| World Bank prices | Food | 24h |
| FAO Desert Locust | Ecological | 24h |
| Commodity prices | Economic | 6h |
| World Bank signals | Economic | 6h |

### Autonomous discovery (Data Scout, every 6h)

Claude (AI) が毎6時間、新しいオープンデータソースを5件発見・統合する。対象ドメインは社会系に限らず物理・生物・生態系・経済系すべて。

---

## Models

### Conflict Risk (XGBoost + Platt calibration)
- Label: UCDP GED conflict onset (25+ battle deaths/year)
- Features: WGI governance, V-Dem democracy, economic indicators, conflict history lags, neighbor spillover, GDELT signals
- Validation: Walk-forward (1990–2022)

### Coup Risk (XGBoost + Platt calibration)
- Label: Powell-Thyne coup attempts
- Class imbalance: scale_pos_weight ~132× (~0.75% positive rate)
- Label shift: shift(-2) — 2-year forward prediction

---

## Update Cycle

| What | When | How |
|---|---|---|
| Raw signals | Continuously | Railway collectors → Upstash → Neon |
| Predictions | Every 24h | Railway daily-predict → Neon |
| New data sources | Every 6h | Railway Data Scout (Claude) |
| Model retraining | Annually | Local pipeline → push_to_neon.py → git push |

---

## Local Development

```bash
git clone https://github.com/Taiyo-Tanabe/Earth-Twin-Code.git
cd Earth-Twin-Code
cp .env.example .env
# Edit .env with your credentials

# Frontend
cd frontend && npm install && npm run dev

# Backend API
cd backend && pip install -r requirements.txt
uvicorn api.main:app --reload --port 8001
```

---

## Annual Model Update (manual)

新しい UCDP / V-Dem データがリリースされた年に1回実行:

```bash
cd backend
python pipeline_runner.py        # Download + feature engineering + retrain
python push_to_neon.py           # Push new predictions to Neon

git add data/models/ data/processed/panel_latest.parquet
git commit -m "update: retrain with 2025 data"
git push                         # Railway auto-deploys new models
```

---

## API

### `GET /global_map`
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

## License

MIT
