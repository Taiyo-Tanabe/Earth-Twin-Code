# Earth Twin — Probabilistic World Model

Earth Twin is not a geopolitical prediction tool. It is a **copy of the world** — a probabilistic model that continuously absorbs physical, biological, ecological, economic, and social signals to reproduce the state of Earth in real time. The output is a probability distribution over future events, not a deterministic forecast.

![version](https://img.shields.io/badge/version-0.1-00d2aa?style=flat-square) ![license](https://img.shields.io/badge/license-MIT-blue?style=flat-square) ![Python](https://img.shields.io/badge/python-3.11-blue?style=flat-square) ![React](https://img.shields.io/badge/react-18-61dafb?style=flat-square)

---

## Philosophy

> *If a complex system is fully reproduced and the universe contains no true randomness, the future becomes deterministic. Since full reproduction is impossible, we express outcomes as probability.*

Earth Twin aims to absorb as many real-world signals as possible — spanning physical, biological, ecological, economic, and social domains — and compress them into a probabilistic world state. Risk scores are a side-effect of that compression, not the goal.

---

## Features

- **3-layer interactive risk map** — Overall Risk, Conflict Risk, Coup Risk; choropleth world map with arc-gauge detail panels
- **1-year probabilistic forecasts** — Rolling predictions (today → today+365), updated continuously as new signals arrive
- **Dual risk models** — Conflict Risk (UCDP GED) + Coup Risk (Powell-Thyne dataset), XGBoost + Platt calibration
- **Truly continuous data collection** — 13 always-on collector processes stream real-world data at each source's natural frequency (1 min → daily), replacing batch scheduling
- **AI Data Scout** — Autonomous agent (Claude API) that discovers and integrates new open data sources across all domains; retries until exactly 5 sources pass quality checks each run
- **Concept Overlay** — In-app explanation of Earth Twin's philosophy, accessible from toolbar (desktop + mobile)
- **Full English UI** — All labels, definitions, and badges in English

---

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│              Browser (React + Leaflet)                      │
│   Overall / Conflict / Coup map · Arc-gauge panels          │
│   ConceptOverlay · SearchBar · TopRisk list                 │
└──────────────────────┬─────────────────────────────────────┘
                       │ HTTP (Vite proxy → FastAPI)
┌──────────────────────▼─────────────────────────────────────┐
│                   FastAPI Backend                            │
│   /global-map  ·  /country/{code}  ·  /health              │
└──────┬───────────────────────────────────────────-──────────┘
       │
┌──────▼──────┐   ┌──────────────────────────────────────────┐
│ TimescaleDB │◄──│  Stream Processor                         │
│ raw_signals │   │  Reads Redis → writes TimescaleDB         │
│ risk_scores │   │  Triggers model retraining at 500+ rows   │
└─────────────┘   └────────────────────┬─────────────────────┘
                                        │
                  ┌─────────────────────▼─────────────────────┐
                  │              Redis Streams                  │
                  │   earth_twin:stream:{source_name}          │
                  └────────────────────┬────────────────────── ┘
                                        │
          ┌─────────────────────────────▼──────────────────────┐
          │            Always-On Collectors (13 sources)        │
          │                                                     │
          │  Physical domain                                    │
          │    EarthquakeCollector     (60s)   — USGS           │
          │    WeatherCollector        (1h)    — Open-Meteo     │
          │    SolarActivityCollector  (1h)    — NOAA SWPC      │
          │    ForestFireCollector     (24h)   — NASA FIRMS     │
          │    SeaTemperatureCollector (24h)   — NOAA Nino3.4   │
          │                                                     │
          │  Biological / Ecological domain                     │
          │    WHODiseaseCollector     (24h)   — WHO GHO        │
          │    FoodPriceCollector      (24h)   — World Bank     │
          │    LocustCollector         (24h)   — FAO Desert     │
          │                                                     │
          │  Economic / Social domain                           │
          │    GDELTCollector          (15min) — news signals   │
          │    CommodityPriceCollector (6h)                     │
          │    EconomicSignalCollector (6h)    — WB API         │
          │                                                     │
          │  Annual release detectors (hash-based)             │
          │    UCDPAnnualCollector     (24h)   — UCDP GED       │
          │    VDemAnnualCollector     (24h)   — V-Dem          │
          │    WorldBankAnnualCollector(24h)   — WB bulk data   │
          └─────────────────────────────────────────────────── ┘

          ┌─────────────────────────────────────────────────── ┐
          │         AI Data Scout (runs every 6h)              │
          │  Asks Claude for 10 new open data source ideas     │
          │  Generates + validates ingestion scripts           │
          │  Retries until exactly 5 sources are integrated    │
          └────────────────────────────────────────────────── ─┘
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite, Leaflet / react-leaflet |
| Backend API | FastAPI, Uvicorn, Pydantic |
| ML | XGBoost, scikit-learn, MLflow |
| Message queue | Redis 7 (Streams) |
| Database | TimescaleDB (PostgreSQL 16) |
| AI agent | Anthropic Claude API |
| Containerization | Docker Compose |

> **Removed:** Apache Airflow — replaced entirely by always-on collector processes and the stream processor.

---

## Data Sources

### Core model training data

| Source | Description | Frequency |
|---|---|---|
| [UCDP GED](https://ucdp.uu.se/downloads/) | Armed conflict events, 124 countries, 1989–present | Annual |
| [Powell-Thyne Coups](https://www.jonathanmpowell.com/coup-detat-dataset.html) | Coup attempts, 1950–present | Annual |
| [V-Dem](https://www.v-dem.net/) | Democracy indices, 202 countries | Annual |
| [World Bank WDI](https://data.worldbank.org/indicator) | GDP, inflation, unemployment | Annual |
| [WGI](https://info.worldbank.org/governance/wgi/) | 6 governance indicators, 210 countries | Annual |
| [UNHCR Population](https://www.unhcr.org/refugee-statistics/) | Refugees & IDPs | Annual |

### Continuous streaming sources

| Source | Domain | Interval |
|---|---|---|
| USGS Earthquake Feed | Physical | 60s |
| GDELT v2 | Social / News | 15min |
| Open-Meteo | Physical / Weather | 1h |
| NOAA SWPC (K-index) | Physical / Solar | 1h |
| NASA FIRMS | Physical / Wildfire | 24h |
| NOAA Nino3.4 SST | Physical / Ocean | 24h |
| WHO GHO Disease | Biological | 24h |
| FAO World Food Prices | Biological / Economic | 24h |
| FAO Desert Locust RSS | Biological / Ecological | 24h |
| Commodity Prices | Economic | 6h |
| World Bank signals (inflation/GDP) | Economic | 6h |

### Autonomously discovered sources (AI Data Scout)

The Data Scout runs every 6 hours and integrates **exactly 5** new open data sources per run, spanning physical, biological, ecological, economic, and social domains. Sources are validated against quality thresholds (50+ country coverage, 5+ year span, <60% missing) before integration.

---

## Risk Layers

| Layer | Source | Description |
|---|---|---|
| **Overall Risk** | Combined score | Composite of conflict + coup probabilities, weighted by model confidence |
| **Conflict Risk** | UCDP GED | Countries with 25+ battle-related deaths/year (interstate, civil, non-state) |
| **Coup Risk** | Powell-Thyne | Coup attempts against the incumbent head of state (successful or failed) |

---

## Models

### Conflict Risk Model
- **Label**: UCDP GED conflict onset (25+ battle deaths/year)
- **Features**: Economic indicators, WGI governance, V-Dem democracy, conflict history lags (1–3y + 5y rolling), neighbor conflict spillover, UNHCR refugees, GDELT signals
- **Training**: Walk-forward validation (1990–2022), final model on all data
- **Calibration**: Platt scaling (sigmoid)

### Coup Risk Model
- **Label**: Powell-Thyne coup attempts (successful or failed)
- **Features**: All conflict features + coup history lags (1–3y + 5y rolling)
- **Class imbalance**: Dynamic `scale_pos_weight` (~132×) for ~0.75% positive rate
- **Label shift**: `shift(-2)` — latest features predict 2-year forward events

Both models use **XGBoost**. Retraining is triggered automatically when the stream processor accumulates 500+ new rows.

---

## Quick Start

### Prerequisites
- Docker Desktop (8 GB RAM recommended)
- Anthropic API key (for AI Data Scout — optional)

### 1. Clone & configure

```bash
git clone https://github.com/<your-username>/earth-twin.git
cd earth-twin
cp .env.example .env
```

Edit `.env`:

```env
# Required for AI Data Scout
ANTHROPIC_API_KEY=sk-ant-...

# Optional — ACLED data (requires research access at acleddata.com)
ACLED_EMAIL=your@email.com
ACLED_PASSWORD=your_password
```

### 2. Start all services

```bash
docker-compose up -d
```

| Service | URL |
|---|---|
| Frontend (React map) | http://localhost:3000 |
| Backend API | http://localhost:8001 |
| MLflow UI | http://localhost:5000 |

### 3. Run the initial pipeline

```bash
docker exec earth-twin-backend-1 python pipeline_runner.py
```

This downloads all core datasets, builds the feature panel, trains both models, generates predictions, and writes scores to TimescaleDB. Collectors and the stream processor start automatically and run continuously thereafter.

---

## Project Structure

```
earth-twin/
├── frontend/                        # React + TypeScript + Vite
│   ├── src/
│   │   ├── components/
│   │   │   ├── RiskMap.tsx          # Leaflet choropleth (3 layers)
│   │   │   ├── CountryPanel.tsx     # Desktop detail panel (Arc gauges)
│   │   │   ├── BottomSheet.tsx      # Mobile detail sheet (Arc gauges)
│   │   │   ├── TopRiskList.tsx      # TOP 5 sidebar
│   │   │   ├── Toolbar.tsx          # Desktop nav + layer switcher
│   │   │   ├── MobileToolbar.tsx    # Mobile nav + concept button
│   │   │   ├── SearchBar.tsx        # Country search
│   │   │   └── ConceptOverlay.tsx   # Full-screen concept explanation
│   │   ├── hooks/
│   │   └── types/
│   └── Dockerfile
├── backend/
│   ├── api/main.py                  # FastAPI endpoints
│   ├── ingestion/                   # Core dataset downloaders
│   ├── features/panel.py            # Feature panel builder
│   ├── models/
│   │   ├── train.py                 # XGBoost + walk-forward
│   │   └── predict.py               # Inference + DB write
│   ├── collectors/                  # Always-on streaming collectors
│   │   ├── base.py                  # BaseCollector + run_forever()
│   │   ├── runner.py                # Starts all 13 collectors as threads
│   │   ├── stream_processor.py      # Redis → TimescaleDB + retrain trigger
│   │   └── sources/
│   │       ├── earthquakes.py       # USGS
│   │       ├── gdelt.py             # GDELT v2
│   │       ├── weather.py           # Open-Meteo
│   │       ├── physical.py          # Solar, wildfire, sea temp
│   │       ├── biological.py        # WHO, food prices, locust
│   │       ├── economic.py          # Commodities, WB signals
│   │       └── annual.py            # Hash-based release detectors
│   ├── agents/
│   │   ├── data_scout.py            # AI Data Scout (5 integrations/run)
│   │   └── scout_runner.py          # Runs scout every 6h
│   └── requirements.txt
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## API Reference

### `GET /global-map`

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
      "top_features": ["5-year conflict rate", "Political instability"]
    }
  ],
  "prediction_from": "2026/06/17",
  "prediction_to": "2027/06/17",
  "data_year": 2024,
  "conflict_definition": "UCDP GED: Countries with 25+ battle-related deaths per year (interstate, civil, and non-state violence)",
  "regime_change_definition": "Powell-Thyne: Coup attempts against the incumbent head of state (successful or failed, 1950–present)"
}
```

### `GET /country/{country_code}`
Detailed data for a single country (ISO 3166-1 alpha-3).

### `GET /health`
Service health check.

---

## License

MIT
