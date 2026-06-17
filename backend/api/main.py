from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os
import logging
import pycountry

logger = logging.getLogger(__name__)

# World Bank の地域集計コード（国ではない）
_WB_AGGREGATES = {
    "AFE","AFW","ARB","CEB","CSS","EAP","EAR","EAS","ECA","ECE","ECS","EMU",
    "EUU","FCS","HIC","HPC","IBD","IBT","IDA","IDB","IDX","INX","LAC","LCN",
    "LDC","LIC","LMC","LMY","LTE","MEA","MIC","MNA","NAC","NOC","OED","OSS",
    "PRE","PSS","PST","SAS","SSA","SSF","SST","TEA","TEC","TLA","TMN","TSA",
    "TSS","UMC","WLD",
}

# pycountry が対応しない特殊コード
_EXTRA_NAMES = {
    "CHI": "Channel Islands",
    "XKX": "Kosovo",
    "PSE": "Palestine",
    "TWN": "Taiwan",
    "HKG": "Hong Kong",
    "MAC": "Macao",
}

def _country_name(iso3: str) -> str:
    if iso3 in _EXTRA_NAMES:
        return _EXTRA_NAMES[iso3]
    try:
        c = pycountry.countries.get(alpha_3=iso3)
        if c:
            return c.name
    except Exception:
        pass
    return iso3

app = FastAPI(title="Earth Twin API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class CountryRisk(BaseModel):
    country_code: str
    country_name: str
    conflict_probability_1y: float
    regime_change_probability_1y: float
    risk_score: float
    risk_trend: str
    top_features: list[str]
    gdp_growth: Optional[float] = None
    inflation: Optional[float] = None
    polity_score: Optional[int] = None
    structural_risk: Optional[float] = None  # 構造的脆弱性スコア (0-1)


class GlobalMapResponse(BaseModel):
    countries: list[CountryRisk]
    updated_at: str
    model_version: str
    data_year: Optional[int] = None
    prediction_from: Optional[str] = None   # 予測開始日 (予測実行日, YYYY-MM-DD)
    prediction_to: Optional[str] = None     # 予測終了日 (1年後, YYYY-MM-DD)
    conflict_definition: str = "UCDP GED: Countries with 25+ battle-related deaths per year (interstate, civil, and non-state violence)"
    regime_change_definition: str = "Powell-Thyne: Coup attempts against the incumbent head of state (successful or failed, 1950–present)"


def _get_db():
    import sqlalchemy as sa
    url = (
        os.environ.get("DATABASE_URL") or
        os.environ.get("TIMESCALE_URL") or
        "postgresql://earthtwin:earthtwin123@timescaledb:5432/earthtwin"
    )
    # Neon requires SSL; other hosts are fine without it
    connect_args = {"sslmode": "require"} if "neon.tech" in url else {}
    return sa.create_engine(url, connect_args=connect_args)


def _compute_structural_risk(row) -> float:
    """
    WGI・V-Dem・経済指標から構造的脆弱性スコア (0=安全, 1=危険) を計算。
    現在の紛争状態に依存しないため、平和な国の差別化に使用できる。
    """
    import math

    def safe(key, default=0.0):
        v = row.get(key)
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return default
        return float(v)

    def clamp(v):
        return max(0.0, min(1.0, float(v)))

    pv       = safe("pv_est", 0.0)
    va       = safe("va_est", 0.0)
    rl       = safe("rl_est", 0.0)
    ge       = safe("ge_est", 0.0)
    cc       = safe("cc_est", 0.0)
    poly     = safe("v2x_polyarchy", 0.5)
    gdp_log  = safe("gdp_per_capita_log", 7.0)
    growth   = safe("gdp_growth", 0.0)
    inf      = safe("inflation", 5.0)
    conf5y   = safe("conflict_onset_rolling5y", 0.0)
    refugees = safe("refugees_per_capita", 0.0)
    neighbor = safe("neighbor_conflict_avg", 0.0)

    score = (
        clamp(1.0 - (pv + 2.5) / 5.0)         * 0.20 +
        clamp(1.0 - poly)                        * 0.12 +
        clamp(1.0 - (gdp_log - 5.0) / 7.0)     * 0.12 +
        clamp(1.0 - (va + 2.5) / 5.0)           * 0.09 +
        clamp(1.0 - (rl + 2.5) / 5.0)           * 0.09 +
        clamp(1.0 - (ge + 2.5) / 5.0)           * 0.06 +
        clamp(1.0 - (cc + 2.5) / 5.0)           * 0.06 +
        clamp(conf5y)                            * 0.09 +
        clamp(neighbor)                          * 0.05 +
        clamp((-growth + 10.0) / 20.0)          * 0.05 +
        clamp(min(inf, 50.0) / 50.0)            * 0.04 +
        clamp(refugees / 0.2)                   * 0.03
    )
    return clamp(score)


def _load_panel_econ() -> dict:
    """panel_latest.parquet から経済指標・構造的脆弱性を国別マップとして返す"""
    from pathlib import Path
    import pandas as pd, math

    path = Path("/app/data/processed/panel_latest.parquet")
    if not path.exists():
        return {}
    try:
        df = pd.read_parquet(path)
        result = {}
        for _, row in df.iterrows():
            cc = str(row.get("country_code", "")).strip()
            if not cc:
                continue
            gdp_growth = row.get("gdp_growth")
            inflation = row.get("inflation")
            pv = row.get("pv_est")
            polity = round(float(pv) * 4) if pv is not None and not (isinstance(pv, float) and math.isnan(pv)) else None
            result[cc] = {
                "gdp_growth": float(gdp_growth) if gdp_growth is not None and not (isinstance(gdp_growth, float) and math.isnan(gdp_growth)) else None,
                "inflation": float(inflation) if inflation is not None and not (isinstance(inflation, float) and math.isnan(inflation)) else None,
                "polity_score": polity,
                "structural_risk": _compute_structural_risk(row),
            }
        return result
    except Exception as e:
        logger.warning(f"Panel econ load failed: {e}")
        return {}


def _load_from_db() -> tuple[list[dict], dict]:
    """
    TimescaleDB から最新予測と前週の予測を取得。
    Returns (latest_rows, prev_risk_by_code)
    """
    try:
        import sqlalchemy as sa
        engine = _get_db()
        with engine.connect() as conn:
            rows = conn.execute(sa.text("""
                SELECT DISTINCT ON (country_code)
                    country_code,
                    conflict_probability,
                    regime_change_probability,
                    risk_score,
                    top_features,
                    model_version,
                    time
                FROM risk_predictions
                ORDER BY country_code, time DESC
            """)).fetchall()

            # 前週のスコアを取得（トレンド計算用）
            prev_rows = conn.execute(sa.text("""
                SELECT DISTINCT ON (country_code)
                    country_code,
                    risk_score
                FROM risk_predictions
                WHERE time < NOW() - INTERVAL '3 days'
                ORDER BY country_code, time DESC
            """)).fetchall()

        if rows:
            logger.info(f"Loaded {len(rows)} predictions from DB")
            latest = [dict(r._mapping) for r in rows]
            prev_map = {r.country_code: r.risk_score for r in prev_rows}
            return latest, prev_map
    except Exception as e:
        logger.warning(f"DB load failed: {e}")
    return [], {}


def _calc_trend(current: float, prev: Optional[float]) -> str:
    if prev is None:
        return "stable"
    delta = current - prev
    if delta > 0.05:
        return "up"
    if delta < -0.05:
        return "down"
    return "stable"


def _build_country_list(db_rows: list[dict], prev_map: dict, econ_map: dict) -> list[CountryRisk]:
    """DB予測 + パネル経済指標をマージしてCountryRiskリストを返す"""
    results = []
    for db in db_rows:
        code = db["country_code"]
        if code in _WB_AGGREGATES:
            continue
        econ = econ_map.get(code, {})
        current_risk = float(db["risk_score"])
        trend = _calc_trend(current_risk, prev_map.get(code))

        # top_features: DB の jsonb フィールド
        top_feats = db.get("top_features")
        if isinstance(top_feats, list):
            top_labels = [str(f) for f in top_feats]
        elif isinstance(top_feats, str):
            import json
            try:
                top_labels = json.loads(top_feats)
            except Exception:
                top_labels = ["Limited data"]
        else:
            top_labels = ["Limited data"]

        results.append(CountryRisk(
            country_code=code,
            country_name=_country_name(code),
            conflict_probability_1y=float(db["conflict_probability"]),
            regime_change_probability_1y=float(db["regime_change_probability"] or 0),
            risk_score=current_risk,
            risk_trend=trend,
            top_features=top_labels,
            gdp_growth=econ.get("gdp_growth"),
            inflation=econ.get("inflation"),
            polity_score=econ.get("polity_score"),
            structural_risk=econ.get("structural_risk"),
        ))

    return sorted(results, key=lambda c: c.risk_score, reverse=True)


@app.get("/health")
def health():
    return {"status": "ok", "service": "earth-twin-api"}


# 世界銀行データに含まれない重要国のスタブ予測
_HARDCODED_STUBS: dict[str, dict] = {
    "TWN": {
        "country_name": "Taiwan",
        "conflict_probability_1y": 0.018,
        "regime_change_probability_1y": 0.0009,
        "risk_score": 0.018 * 0.6 + 0.0009 * 0.4,
        "structural_risk": 0.22,
        "top_features": ["Cross-strait tension", "Strong institutions", "High income"],
        "gdp_growth": 3.1,
        "inflation": 2.5,
        "polity_score": 8,
    },
    "XKX": {
        "country_name": "Kosovo",
        "conflict_probability_1y": 0.04,
        "regime_change_probability_1y": 0.005,
        "risk_score": 0.04 * 0.6 + 0.005 * 0.4,
        "structural_risk": 0.52,
        "top_features": ["Regional instability", "Weak institutions", "Economic fragility"],
        "gdp_growth": 3.5,
        "inflation": 4.0,
        "polity_score": 4,
    },
    "PSE": {
        "country_name": "Palestine",
        "conflict_probability_1y": 0.85,
        "regime_change_probability_1y": 0.12,
        "risk_score": 0.85 * 0.6 + 0.12 * 0.4,
        "structural_risk": 0.88,
        "top_features": ["Active conflict", "Political instability", "Humanitarian crisis"],
        "gdp_growth": -8.0,
        "inflation": 8.0,
        "polity_score": -4,
    },
    "ESH": {
        "country_name": "Western Sahara",
        "conflict_probability_1y": 0.12,
        "regime_change_probability_1y": 0.02,
        "risk_score": 0.12 * 0.6 + 0.02 * 0.4,
        "structural_risk": 0.68,
        "top_features": ["Territorial dispute", "Political instability", "Conflict spillover"],
        "gdp_growth": None,
        "inflation": None,
        "polity_score": -7,
    },
    "VAT": {
        "country_name": "Vatican City",
        "conflict_probability_1y": 0.001,
        "regime_change_probability_1y": 0.0001,
        "risk_score": 0.001 * 0.6 + 0.0001 * 0.4,
        "structural_risk": 0.10,
        "top_features": ["Stable governance", "Strong institutions"],
        "gdp_growth": None,
        "inflation": None,
        "polity_score": None,
    },
    "COK": {
        "country_name": "Cook Islands",
        "conflict_probability_1y": 0.002,
        "regime_change_probability_1y": 0.0002,
        "risk_score": 0.002,
        "structural_risk": 0.18,
        "top_features": ["Small island state", "Limited data"],
        "gdp_growth": None,
        "inflation": None,
        "polity_score": 9,
    },
    "NIU": {
        "country_name": "Niue",
        "conflict_probability_1y": 0.001,
        "regime_change_probability_1y": 0.0001,
        "risk_score": 0.001,
        "structural_risk": 0.12,
        "top_features": ["Pacific territory", "Limited data"],
        "gdp_growth": None,
        "inflation": None,
        "polity_score": None,
    },
}


@app.get("/global_map", response_model=GlobalMapResponse)
def global_map():
    db_rows, prev_map = _load_from_db()
    econ_map = _load_panel_econ()

    if db_rows:
        countries = _build_country_list(db_rows, prev_map, econ_map)
        model_version = db_rows[0]["model_version"]
        updated_at = str(db_rows[0]["time"])
    else:
        from api.mock_data import MOCK_COUNTRIES
        countries = MOCK_COUNTRIES
        model_version = "mock-v0.1"
        updated_at = "2025-06-01T00:00:00Z"

    # WBデータにない重要国をスタブとして追加
    existing = {c.country_code for c in countries}
    for code, stub in _HARDCODED_STUBS.items():
        if code not in existing:
            countries.append(CountryRisk(
                country_code=code,
                country_name=stub["country_name"],
                conflict_probability_1y=stub["conflict_probability_1y"],
                regime_change_probability_1y=stub["regime_change_probability_1y"],
                risk_score=stub["risk_score"],
                risk_trend="stable",
                top_features=stub["top_features"],
                structural_risk=stub.get("structural_risk"),
                gdp_growth=stub.get("gdp_growth"),
                inflation=stub.get("inflation"),
                polity_score=stub.get("polity_score"),
            ))

    # パネルデータの基準年を取得
    data_year = None
    try:
        from pathlib import Path
        import pandas as pd
        panel_path = Path("/app/data/processed/panel_latest.parquet")
        if panel_path.exists():
            panel = pd.read_parquet(panel_path, columns=["year"])
            data_year = int(panel["year"].max())
    except Exception:
        pass

    # 紛争データソースを確認 (ACLED vs UCDP)
    acled_path = Path("/app/data/processed/acled_panel.parquet")
    conflict_def = (
        "ACLED: Countries with 25+ battle-related deaths per year (weekly updates, current)"
        if acled_path.exists()
        else "UCDP GED: Countries with 25+ battle-related deaths per year (interstate, civil, and non-state violence)"
    )

    # クーデターデータソースを確認
    coup_path = Path("/app/data/processed/coup_panel.parquet")
    regime_def = (
        "Powell-Thyne: Coup attempts against the incumbent head of state (successful or failed, 1950–present)"
        if coup_path.exists()
        else "WGI proxy: Sharp drop in political stability score (Powell-Thyne data unavailable)"
    )

    from datetime import date, timedelta
    today = date.today()
    one_year_later = today + timedelta(days=365)

    return GlobalMapResponse(
        countries=countries,
        updated_at=updated_at,
        model_version=model_version,
        data_year=data_year,
        prediction_from=today.strftime("%Y/%m/%d"),
        prediction_to=one_year_later.strftime("%Y/%m/%d"),
        conflict_definition=conflict_def,
        regime_change_definition=regime_def,
    )


@app.get("/country/{country_code}", response_model=CountryRisk)
def get_country(country_code: str):
    db_rows, prev_map = _load_from_db()
    econ_map = _load_panel_econ()

    if db_rows:
        countries = _build_country_list(db_rows, prev_map, econ_map)
    else:
        from api.mock_data import MOCK_COUNTRIES
        countries = MOCK_COUNTRIES

    found = next((c for c in countries if c.country_code == country_code.upper()), None)
    if not found:
        raise HTTPException(status_code=404, detail=f"Country {country_code} not found")
    return found


@app.get("/history/{country_code}")
def get_history(country_code: str):
    try:
        import sqlalchemy as sa
        engine = _get_db()
        with engine.connect() as conn:
            rows = conn.execute(sa.text("""
                SELECT time, conflict_probability, regime_change_probability, risk_score
                FROM risk_predictions
                WHERE country_code = :code
                ORDER BY time ASC
            """), {"code": country_code.upper()}).fetchall()
        return {
            "country_code": country_code.upper(),
            "history": [dict(r._mapping) for r in rows],
        }
    except Exception as e:
        return {"country_code": country_code.upper(), "history": [], "error": str(e)}
