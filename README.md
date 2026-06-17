# Earth Twin — Global Risk Intelligence

A probabilistic geopolitical risk forecasting platform. Earth Twin predicts **1-year conflict and coup probabilities** for 150+ countries using XGBoost models trained on historical armed conflict, governance, economic, and democratic data.

![Earth Twin](https://img.shields.io/badge/version-0.1-00d2aa?style=flat-square) ![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square) ![Python](https://img.shields.io/badge/python-3.11-blue?style=flat-square) ![React](https://img.shields.io/badge/react-18-61dafb?style=flat-square)

---

## Features

- **Interactive risk map** — Choropleth world map with country-level conflict and coup risk scores
- **1-year forecasts** — Rolling predictions from today to today+365 days, updated weekly
- **Dual risk models** — Conflict Risk (UCDP GED) + Coup Risk (Powell-Thyne dataset)
- **AI Data Scout** — Monthly autonomous agent (Claude API) that discovers and integrates new open data sources
- **Automated pipeline** — Apache Airflow DAGs handle ingestion, feature engineering, model retraining, and prediction
- **Full-stack Docker** — Single `docker-compose up` spins up the entire system

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Browser (React + Leaflet)            │
│         Interactive map · Country panels · TOP 5 list    │
└──────────────────┬──────────────────────────────────────┘
                   │ HTTP (Vite proxy → FastAPI)
┌──────────────────▼──────────────────────────────────────┐
│                   FastAPI Backend                         │
│  /global-map  ·  /country/{code}  ·  /health            │
└──────┬──────────────┬────────────────────────────────────┘
       │              │
┌──────▼──────┐  ┌────▼────────────────────────────────────┐
│ TimescaleDB │  │  Local file storage (/app/data/)         │
│  (risk      │  │  ├── raw/        (downloaded datasets)   │
│  scores +   │  │  ├── processed/  (parquet panel data)    │
│  metadata)  │  │  └── models/     (trained .pkl files)    │
└─────────────┘  └────────────────────────────────────────-┘
                        ▲
          ┌─────────────┴───────────────┐
          │     Apache Airflow DAGs      │
          │  annual_ucdp_pipeline        │
          │  daily_signal_pipeline       │
          │  weekly_predictions          │
          │  vdem_annual_update          │
          │  unhcr_annual_update         │
          │  wgi_retrain_pipeline        │
          │  ai_data_scout (monthly)     │
          └──────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite, Leaflet / react-leaflet |
| Backend API | FastAPI, Uvicorn, Pydantic |
| ML | XGBoost, scikit-learn, MLflow |
| Data pipeline | Apache Airflow 2.9 |
| Database | TimescaleDB (PostgreSQL 16) |
| Object storage | MinIO (S3-compatible) |
| AI agent | Anthropic Claude API (Haiku) |
| Containerization | Docker Compose |

---

## Data Sources

| Source | Description | Update |
|---|---|---|
| [UCDP GED v24](https://ucdp.uu.se/downloads/) | Armed conflict events, 124 countries, 1989–2023 | Annual |
| [World Bank WDI](https://data.worldbank.org/indicator) | GDP, inflation, unemployment, trade, 266 countries | Annual |
| [WGI](https://info.worldbank.org/governance/wgi/) | 6 governance indicators, 210 countries, 1996–2023 | Annual |
| [V-Dem v14](https://www.v-dem.net/) | Democracy indices, 202 countries, 1789–2023 | Annual |
| [UNHCR Population](https://www.unhcr.org/refugee-statistics/) | Refugees & IDPs, 200+ countries | Annual |
| [GDELT v2](https://www.gdeltproject.org/) | News-based conflict signals, global, daily | Daily |
| [Powell-Thyne Coup](https://www.jonathanmpowell.com/coup-detat-dataset.html) | Coup attempts, 1950–present | Annual |
| ACLED *(optional)* | Armed conflict events with weekly updates | Weekly |

---

## Models

### Conflict Risk Model
- **Label**: UCDP GED conflict onset (25+ battle deaths/year)
- **Features**: Economic indicators, WGI governance scores, V-Dem democracy indices, conflict history lags (1–3y + 5y rolling), neighbor conflict, UNHCR refugees, GDELT signals
- **Training**: Walk-forward validation (1990–2022), final model on all data
- **Calibration**: Platt scaling (sigmoid)

### Coup Risk Model
- **Label**: Powell-Thyne coup attempts (successful or failed)
- **Features**: All conflict features + coup history lags (1–3y + 5y rolling)
- **Class imbalance**: Dynamic `scale_pos_weight` (~132x) for ~0.75% positive rate
- **Label shift**: `shift(-2)` — 2024 features predict 2026 events, displayed as "today → today+1 year"

Both models use **XGBoost** with walk-forward validation and are retrained annually via Airflow.

---

## Quick Start

### Prerequisites
- Docker Desktop
- 8 GB RAM (recommended)
- Anthropic API key (for AI Data Scout, optional)

### 1. Clone & configure

```bash
git clone https://github.com/<your-username>/earth-twin.git
cd earth-twin
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# Required
ANTHROPIC_API_KEY=sk-ant-...

# Optional — ACLED armed conflict data (requires Research access)
# https://acleddata.com/
ACLED_EMAIL=your@email.com
ACLED_PASSWORD=your_password
```

### 2. Start all services

```bash
docker-compose up -d
```

This starts:
| Service | URL |
|---|---|
| Frontend (React map) | http://localhost:3000 |
| Backend API | http://localhost:8001 |
| Airflow UI | http://localhost:8080 (admin / admin) |
| MinIO console | http://localhost:9001 |
| MLflow UI | http://localhost:5000 |

### 3. Run the initial data pipeline

```bash
# Via Airflow UI → trigger `annual_ucdp_pipeline` manually
# Or directly:
docker exec earth-twin-backend-1 python pipeline_runner.py
```

The pipeline runs in order:
1. Download UCDP, World Bank, WGI, V-Dem, UNHCR, GDELT data
2. Build panel features (`panel_features.parquet`)
3. Train conflict and coup models
4. Generate country-level predictions
5. Write scores to TimescaleDB

---

## Airflow DAGs

| DAG | Schedule | Description |
|---|---|---|
| `annual_ucdp_pipeline` | Jan 15 | Full annual retraining with new UCDP data |
| `wgi_retrain_pipeline` | Nov 1 | Retrain after WGI release |
| `vdem_annual_update` | Mar 1 | V-Dem data update |
| `unhcr_annual_update` | Jul 1 | UNHCR refugee data update |
| `daily_signal_pipeline` | Daily 07:30 UTC | GDELT signal refresh |
| `weekly_predictions` | Monday 06:00 UTC | Re-score all countries with latest signals |
| `ai_data_scout` | 1st of month | Claude discovers and integrates 5 new data sources |

---

## AI Data Scout

The Data Scout is an autonomous agent that runs monthly and:

1. Analyzes model weaknesses (feature importance, missing data rates)
2. Asks Claude (Haiku) to suggest 10 free, API-key-free data sources
3. Generates Python ingestion scripts for each suggestion
4. Executes and validates each script (50+ country coverage, 5+ year span, <60% NaN)
5. Integrates successful sources into the pipeline (target: 5 per month)
6. Retries with new suggestions if fewer than 5 pass quality checks

Integrated sources are saved to `backend/data/scout_logs/scout_registry.json` and automatically refreshed each month.

---

## Project Structure

```
earth-twin/
├── frontend/                  # React + TypeScript + Vite
│   ├── src/
│   │   ├── components/        # Map, panels, toolbar, search
│   │   ├── hooks/             # useRiskData, useIsMobile
│   │   └── types/             # TypeScript interfaces
│   └── Dockerfile
├── backend/                   # Python monorepo
│   ├── api/main.py            # FastAPI endpoints
│   ├── ingestion/             # Data downloaders (UCDP, WB, WGI, V-Dem, ...)
│   ├── features/panel.py      # Panel data builder
│   ├── models/
│   │   ├── train.py           # XGBoost training + walk-forward validation
│   │   └── predict.py         # Inference + DB write
│   ├── agents/data_scout.py   # AI Data Scout
│   ├── pipeline_runner.py     # Manual pipeline trigger
│   └── requirements.txt
├── airflow/
│   └── dags/                  # Airflow DAG definitions
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## API Reference

### `GET /global-map`
Returns risk scores for all countries with metadata.

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
      "top_features": ["5-year conflict rate", "Political instability", ...]
    }
  ],
  "prediction_from": "2026/06/17",
  "prediction_to": "2027/06/17",
  "data_year": 2024,
  "conflict_definition": "UCDP GED: Countries with 25+ battle-related deaths per year",
  "regime_change_definition": "Powell-Thyne: Coup attempts against the incumbent head of state"
}
```

### `GET /country/{country_code}`
Returns detailed data for a single country (ISO 3166-1 alpha-3).

### `GET /health`
Service health check.

---

## Contributing

Pull requests are welcome. For major changes, open an issue first.

---

## License

MIT
