"""
Earth Twin — AI Data Scout
Claude APIを使って、モデルの弱点を分析し、
改善に役立つ新しいデータソースを自律的に発見・統合するエージェント。

動作フロー:
  1. 現在のモデル性能と特徴量重要度を分析
  2. Claude に「何が不足しているか」を問い合わせ
  3. Claude が提案するデータソースのダウンロードコードを生成
  4. コードを実行・検証し、品質基準を満たせばパイプラインに統合
  5. 結果と実行ログをDBに記録

必要な環境変数:
  ANTHROPIC_API_KEY: Claude API キー

スケジュール: Airflow data_scout_dag で月次実行
"""
import os
import json
import logging
import subprocess
import tempfile
import traceback
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def _get_db():
    import sqlalchemy as sa
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        return None
    connect_args = {"sslmode": "require"} if "neon.tech" in url else {}
    return sa.create_engine(url, connect_args=connect_args)


PROCESSED_PATH = Path("/app/data/processed")
MODEL_PATH = Path("/app/data/models")
AGENTS_LOG_PATH = Path("/app/data/scout_logs")

ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
REGISTRY_PATH = AGENTS_LOG_PATH / "scout_registry.json"

CURRENT_SOURCES = [
    "UCDP GED v24.1 (武力衝突イベント, 1989-2023, 124カ国)",
    "World Bank WDI (GDP/インフレ/失業率/人口/軍事費, 1990-2023, 266カ国)",
    "World Governance Indicators WGI (統治指標6種, 1996-2023, 210カ国)",
    "UNHCR Population API (難民/国内避難民, 2000-2023, 200+カ国)",
    "GDELT v2 Events (紛争ニュースシグナル, 2000-現在, 日次)",
    "V-Dem Core v14 (民主主義指標, 1789-2023, 202カ国) [取得失敗時はスキップ]",
    "静的隣国リスト (150カ国, 隣国紛争平均特徴量)",
]

DATA_QUALITY_MIN_COUNTRIES = 50   # 最低カバー国数
DATA_QUALITY_MIN_YEARS = 5        # 最低カバー年数
DATA_QUALITY_MAX_NAN_RATE = 0.6   # 欠損率上限

TARGET_INTEGRATIONS = 5           # 月次で必ず統合する件数
MAX_SUGGESTIONS_PER_CALL = 10     # 1回のClaude呼び出しで要求する提案数


class DataScout:
    def __init__(self):
        self.api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not self.api_key:
            logger.error(
                "ANTHROPIC_API_KEY is not set! "
                "Data Scout cannot call Claude API — no new sources will be discovered. "
                "Set ANTHROPIC_API_KEY in Railway environment variables to enable AI discovery."
            )

        AGENTS_LOG_PATH.mkdir(parents=True, exist_ok=True)
        self._restore_from_neon()

    # ──────────────────────────────────────────────────
    # 1. モデル性能分析
    # ──────────────────────────────────────────────────
    def analyze_model_weaknesses(self) -> dict:
        """
        現在のモデルの弱点を定量的に分析する。
        - 特徴量重要度 (XGBoostから)
        - 国別誤差率
        - データ欠損状況
        """
        result = {
            "timestamp": datetime.utcnow().isoformat(),
            "feature_importance": {},
            "high_error_countries": [],
            "missing_data": {},
            "current_sources": CURRENT_SOURCES,
        }

        try:
            import joblib
            conflict_model_path = MODEL_PATH / "conflict_model_calibrated.pkl"
            if conflict_model_path.exists():
                model = joblib.load(conflict_model_path)
                # CalibratedClassifierCV の内部モデルから重要度取得
                if hasattr(model, "calibrated_classifiers_"):
                    base = model.calibrated_classifiers_[0].estimator
                elif hasattr(model, "estimator"):
                    base = model.estimator
                else:
                    base = model

                if hasattr(base, "feature_importances_"):
                    feature_cols = joblib.load(MODEL_PATH / "conflict_feature_cols.pkl")
                    importances = dict(zip(feature_cols, base.feature_importances_))
                    result["feature_importance"] = dict(
                        sorted(importances.items(), key=lambda x: -x[1])[:15]
                    )
        except Exception as e:
            logger.warning(f"Feature importance extraction failed: {e}")

        # パネルデータから欠損率を分析
        try:
            panel_path = PROCESSED_PATH / "panel_features.parquet"
            if panel_path.exists():
                panel = pd.read_parquet(panel_path)
                nan_rates = panel.isna().mean().sort_values(ascending=False)
                result["missing_data"] = {
                    col: round(float(rate), 3)
                    for col, rate in nan_rates.items()
                    if rate > 0.1
                }

                # 予測誤差の高い国を特定 (panel最新年)
                latest = panel[panel["year"] == panel["year"].max()]
                result["latest_year"] = int(panel["year"].max())
                result["n_countries"] = int(panel["country_code"].nunique())
                result["conflict_rate"] = float(panel["label_conflict"].mean())
        except Exception as e:
            logger.warning(f"Panel analysis failed: {e}")

        return result

    # ──────────────────────────────────────────────────
    # 2. Claude に新データソースを提案させる
    # ──────────────────────────────────────────────────
    def discover_new_sources(self, analysis: dict) -> list[dict]:
        """
        Claude に分析結果を送り、新しいデータソースを提案させる。
        返り値: [{name, url, description, columns, python_code}, ...]
        """
        if not self.api_key:
            logger.info("No API key. Returning built-in suggestions.")
            return self._builtin_suggestions()

        try:
            import anthropic
        except ImportError:
            logger.error("anthropic package not installed. pip install anthropic")
            return self._builtin_suggestions()

        client = anthropic.Anthropic(api_key=self.api_key)

        def _to_json_safe(obj):
            if isinstance(obj, dict):
                return {k: _to_json_safe(v) for k, v in obj.items()}
            try:
                return float(obj)
            except (TypeError, ValueError):
                return obj
        feature_str = json.dumps(_to_json_safe(analysis.get("feature_importance", {})), indent=2)
        missing_str = json.dumps(_to_json_safe(analysis.get("missing_data", {})), indent=2)

        prompt = f"""あなたは「Earth Twin」プロジェクトのデータサイエンティストです。
このプロジェクトは各国の武力紛争・政権崩壊リスクを予測するXGBoostモデルを運用しています。

【現在のデータソース】
{chr(10).join(f"- {s}" for s in CURRENT_SOURCES)}

【特徴量重要度 (上位)】
{feature_str}

【データ欠損率が高い特徴量】
{missing_str}

【現在の状況】
- 対象国数: {analysis.get('n_countries', '不明')}
- データ最新年: {analysis.get('latest_year', '不明')}
- 紛争率 (陽性比): {f"{analysis['conflict_rate']:.3f}" if 'conflict_rate' in analysis else '不明'}

【タスク】
上記の弱点を補う、**無料・APIキー不要・直接ダウンロード可能**な新しいデータソースを{MAX_SUGGESTIONS_PER_CALL}個提案してください。

各提案は以下のJSON形式で回答してください:
```json
[
  {{
    "name": "データセット名",
    "url": "直接ダウンロードURL (CSV/ZIP/JSON)",
    "description": "どんな情報か、なぜモデル改善に役立つか",
    "country_col": "国コード列名",
    "year_col": "年次列名",
    "value_cols": ["取得する列名1", "列名2"],
    "feature_col_name": "panelに追加する特徴量列名"
  }},
  ...
]
```

重要な制約:
- URLは実際にアクセス可能な直接ダウンロードリンクであること
- 認証・登録不要であること
- CSV, JSON, または ZIP形式であること
- country_code × year の形式に変換できること
- 紛争予測に実際に有益な情報であること (食料安全保障、民族的分断、資源紛争、気候変動脆弱性など)

JSONのみを返してください。説明は不要です。"""

        try:
            response = client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()

            # JSON部分を抽出
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            suggestions = json.loads(text)
            logger.info(f"Claude suggested {len(suggestions)} new data sources")
            return suggestions

        except Exception as e:
            logger.error(f"Claude API call failed: {e}")
            return self._builtin_suggestions()

    # ──────────────────────────────────────────────────
    # 3. データ取得コードを生成・実行
    # ──────────────────────────────────────────────────
    def generate_ingestion_code(self, suggestion: dict) -> str:
        """
        提案されたデータソースのPython取得コードをClaudeに生成させる。
        """
        if not self.api_key:
            return ""

        try:
            import anthropic
        except ImportError:
            return ""

        client = anthropic.Anthropic(api_key=self.api_key)

        prompt = f"""以下の仕様でPythonデータ取得スクリプトを書いてください。

データソース: {suggestion['name']}
URL: {suggestion['url']}
説明: {suggestion['description']}
国コード列: {suggestion.get('country_col', '?')}
年次列: {suggestion.get('year_col', '?')}
取得する列: {suggestion.get('value_cols', [])}
出力列名: {suggestion.get('feature_col_name', 'value')}

要件:
1. requests でダウンロード (タイムアウト=120秒)
2. 国コードをISO3 (alpha-3) に変換 (pycountry使用)
3. country_code, year, {suggestion.get('feature_col_name', 'value')} の3列のDataFrameを返す
4. 出力を /app/data/processed/{suggestion.get('feature_col_name', 'new_feature')}.parquet に保存
5. エラー時は空のDataFrameを返す (例外を外に投げない)

以下のテンプレートを使用してください:

```python
import requests, pandas as pd, pycountry, io
from pathlib import Path

DEST = Path("/app/data/processed/{suggestion.get('feature_col_name', 'new_feature')}.parquet")

def fetch():
    try:
        # ここにダウンロード・パース・変換処理を書く
        ...
        df = pd.DataFrame(...)  # country_code, year, {suggestion.get('feature_col_name')} 列
        DEST.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(DEST, index=False)
        return df
    except Exception as e:
        print(f"Error: {{e}}")
        return pd.DataFrame()

if __name__ == "__main__":
    df = fetch()
    print(df.head())
    print(f"Shape: {{df.shape}}")

result = fetch()
```

Pythonコードのみ返してください。説明不要。"""

        try:
            response = client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )
            code = response.content[0].text.strip()
            if "```python" in code:
                code = code.split("```python")[1].split("```")[0].strip()
            elif "```" in code:
                code = code.split("```")[1].split("```")[0].strip()
            return code
        except Exception as e:
            logger.error(f"Code generation failed: {e}")
            return ""

    # ──────────────────────────────────────────────────
    # 4. 生成コードを実行・検証
    # ──────────────────────────────────────────────────
    def execute_and_validate(self, code: str, feature_col: str) -> bool:
        """
        生成コードを一時ファイルで実行し、データ品質を検証する。
        返り値: True = 合格 (パイプラインに統合OK)
        """
        if not code:
            return False

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            tmp_path = f.name

        try:
            result = subprocess.run(
                ["python", tmp_path],
                capture_output=True,
                text=True,
                timeout=300,
                cwd="/app",
            )
            if result.returncode != 0:
                logger.warning(f"Script failed:\n{result.stderr[:500]}")
                return False

            # 出力ファイルを検証
            dest = PROCESSED_PATH / f"{feature_col}.parquet"
            if not dest.exists():
                logger.warning(f"Output file not created: {dest}")
                return False

            df = pd.read_parquet(dest)
            if len(df) == 0:
                logger.warning("Output is empty")
                return False

            n_countries = df["country_code"].nunique() if "country_code" in df.columns else 0
            n_years = df["year"].nunique() if "year" in df.columns else 0
            nan_rate = df[feature_col].isna().mean() if feature_col in df.columns else 1.0

            logger.info(f"Validation: countries={n_countries}, years={n_years}, nan_rate={nan_rate:.2f}")

            if n_countries < DATA_QUALITY_MIN_COUNTRIES:
                logger.warning(f"Too few countries: {n_countries} < {DATA_QUALITY_MIN_COUNTRIES}")
                return False
            if n_years < DATA_QUALITY_MIN_YEARS:
                logger.warning(f"Too few years: {n_years} < {DATA_QUALITY_MIN_YEARS}")
                return False
            if nan_rate > DATA_QUALITY_MAX_NAN_RATE:
                logger.warning(f"Too many NaN: {nan_rate:.2f} > {DATA_QUALITY_MAX_NAN_RATE}")
                return False

            logger.info(f"[OK] {feature_col}: validation passed")
            return True

        except subprocess.TimeoutExpired:
            logger.warning("Script timed out (300s)")
            return False
        except Exception as e:
            logger.error(f"Execution failed: {e}")
            return False
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    # ──────────────────────────────────────────────────
    # 5. レジストリ管理（Neon永続 + ローカルキャッシュ）
    # ──────────────────────────────────────────────────
    def _load_registry(self) -> dict:
        """Neon から統合済みソース一覧を読み込む。失敗時はローカルキャッシュを使用"""
        import sqlalchemy as sa
        engine = _get_db()
        if engine:
            try:
                with engine.connect() as conn:
                    rows = conn.execute(sa.text(
                        "SELECT feature_col, name, url, ingestion_code FROM scout_registry"
                    )).fetchall()
                return {
                    r[0]: {"name": r[1], "url": r[2], "ingestion_code": r[3], "feature_col": r[0]}
                    for r in rows
                }
            except Exception as e:
                logger.warning(f"Neon registry load failed, using local cache: {e}")
        if REGISTRY_PATH.exists():
            with open(REGISTRY_PATH) as f:
                return json.load(f)
        return {}

    def _save_to_registry(self, feature_col: str, name: str, url: str, code: str = ""):
        """統合成功したデータソースを Neon とローカルキャッシュに登録"""
        import sqlalchemy as sa
        engine = _get_db()
        if engine:
            try:
                with engine.begin() as conn:
                    conn.execute(sa.text("""
                        INSERT INTO scout_registry (feature_col, name, url, ingestion_code, last_refreshed)
                        VALUES (:fc, :name, :url, :code, NOW())
                        ON CONFLICT (feature_col) DO UPDATE
                            SET last_refreshed = NOW()
                    """), {"fc": feature_col, "name": name, "url": url, "code": code})
                logger.info(f"Registered in Neon: {feature_col}")
            except Exception as e:
                logger.warning(f"Neon registry save failed: {e}")

        registry = self._load_registry()
        registry[feature_col] = {
            "name": name, "feature_col": feature_col,
            "url": url, "integrated_at": datetime.utcnow().isoformat(),
        }
        REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(REGISTRY_PATH, "w") as f:
            json.dump(registry, f, indent=2, ensure_ascii=False)

    def _write_features_to_neon(self, feature_col: str):
        """検証済みの parquet データを Neon scout_features テーブルに書き込む"""
        import sqlalchemy as sa
        engine = _get_db()
        if not engine:
            return
        dest = PROCESSED_PATH / f"{feature_col}.parquet"
        if not dest.exists():
            return
        try:
            df = pd.read_parquet(dest)
            if "country_code" not in df.columns or "year" not in df.columns or feature_col not in df.columns:
                return
            rows = [
                {
                    "country_code": str(row["country_code"]),
                    "year": int(row["year"]),
                    "feature_col": feature_col,
                    "value": float(row[feature_col]) if pd.notna(row[feature_col]) else None,
                }
                for _, row in df[["country_code", "year", feature_col]].iterrows()
            ]
            with engine.begin() as conn:
                conn.execute(sa.text("""
                    INSERT INTO scout_features (country_code, year, feature_col, value)
                    VALUES (:country_code, :year, :feature_col, :value)
                    ON CONFLICT (country_code, year, feature_col)
                    DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
                """), rows)
            logger.info(f"[OK] Wrote {len(rows)} rows to scout_features ({feature_col})")
        except Exception as e:
            logger.warning(f"Neon feature write failed for {feature_col}: {e}")

    def _restore_from_neon(self):
        """コンテナ再起動後、Neon からローカル parquet ファイルを復元する"""
        import sqlalchemy as sa
        engine = _get_db()
        if not engine:
            return
        try:
            with engine.connect() as conn:
                feature_cols = [
                    r[0] for r in conn.execute(
                        sa.text("SELECT DISTINCT feature_col FROM scout_features")
                    ).fetchall()
                ]
            for feature_col in feature_cols:
                dest = PROCESSED_PATH / f"{feature_col}.parquet"
                if dest.exists():
                    continue
                with engine.connect() as conn:
                    rows = conn.execute(sa.text("""
                        SELECT country_code, year, value FROM scout_features
                        WHERE feature_col = :fc
                    """), {"fc": feature_col}).fetchall()
                if rows:
                    df = pd.DataFrame(rows, columns=["country_code", "year", feature_col])
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    df.to_parquet(dest, index=False)
                    logger.info(f"[OK] Restored {feature_col}.parquet from Neon ({len(df)} rows)")
        except Exception as e:
            logger.warning(f"Restore from Neon failed: {e}")

    def refresh_registered_sources(self) -> dict:
        """
        レジストリに登録済みの全データソースを再取得する。
        Scout が過去に発見・統合したデータを最新版に更新するために使用。
        """
        registry = self._load_registry()
        if not registry:
            logger.info("No registered Scout sources to refresh.")
            return {}

        logger.info(f"Refreshing {len(registry)} registered Scout sources...")
        results = {"refreshed": [], "failed": []}

        for feature_col, meta in registry.items():
            script_path = Path(meta.get("ingestion_script", ""))
            name = meta.get("name", feature_col)
            logger.info(f"  Refreshing: {name} ({feature_col})")

            if not script_path.exists():
                logger.warning(f"  Ingestion script not found: {script_path}")
                results["failed"].append(feature_col)
                continue

            try:
                result = subprocess.run(
                    ["python", str(script_path)],
                    capture_output=True,
                    text=True,
                    timeout=300,
                    cwd="/app",
                )
                if result.returncode == 0:
                    registry[feature_col]["last_updated"] = datetime.utcnow().isoformat()
                    self._write_features_to_neon(feature_col)
                    results["refreshed"].append(feature_col)
                    logger.info(f"  [OK] Refreshed: {name}")
                else:
                    logger.warning(f"  Failed: {result.stderr[:200]}")
                    results["failed"].append(feature_col)
            except Exception as e:
                logger.error(f"  Error refreshing {name}: {e}")
                results["failed"].append(feature_col)

        # レジストリの last_updated を保存
        with open(REGISTRY_PATH, "w") as f:
            json.dump(registry, f, indent=2, ensure_ascii=False)

        logger.info(f"Refresh complete: {len(results['refreshed'])} ok, {len(results['failed'])} failed")
        return results

    # ──────────────────────────────────────────────────
    # 6. メインループ
    # ──────────────────────────────────────────────────
    def run(self) -> dict:
        """
        データスカウトの全フローを実行する。
        返り値: 実行サマリー
        """
        logger.info("=" * 60)
        logger.info("Earth Twin Data Scout — Starting")
        logger.info("=" * 60)

        summary = {
            "timestamp": datetime.utcnow().isoformat(),
            "integrated": [],
            "rejected": [],
            "errors": [],
        }

        # 0. 既存ソースを更新 (レジストリ登録済みデータの再取得)
        logger.info("Step 0: Refreshing previously integrated sources...")
        self.refresh_registered_sources()

        # 1. モデル分析
        logger.info("Step 1: Analyzing model weaknesses...")
        analysis = self.analyze_model_weaknesses()
        logger.info(f"  Missing features: {list(analysis.get('missing_data', {}).keys())[:5]}")

        # 2. 必ず TARGET_INTEGRATIONS 件統合されるまでループ
        round_num = 0
        MAX_ROUNDS = 3  # 無限ループ防止
        suggestion_counter = 0

        while len(summary["integrated"]) < TARGET_INTEGRATIONS and round_num < MAX_ROUNDS:
            round_num += 1
            logger.info(f"Step 2 (round {round_num}): Discovering new data sources via Claude...")
            suggestions = self.discover_new_sources(analysis)
            logger.info(f"  Got {len(suggestions)} suggestions (need {TARGET_INTEGRATIONS - len(summary['integrated'])} more integrations)")

            for suggestion in suggestions:
                if len(summary["integrated"]) >= TARGET_INTEGRATIONS:
                    break

                suggestion_counter += 1
                name = suggestion.get("name", f"source_{suggestion_counter}")
                feature_col = suggestion.get("feature_col_name", f"feature_{suggestion_counter}")
                logger.info(f"\nStep 3.{suggestion_counter}: Evaluating '{name}'...")

                registry = self._load_registry()
                if feature_col in registry:
                    logger.info(f"  Already registered: {feature_col} — skipping")
                    continue

                try:
                    code = self.generate_ingestion_code(suggestion)
                    if not code:
                        summary["rejected"].append({"name": name, "reason": "code generation failed"})
                        continue

                    ingestion_file = Path(f"/app/ingestion/scout_{feature_col}.py")
                    ingestion_file.parent.mkdir(parents=True, exist_ok=True)
                    ingestion_file.write_text(code)

                    if self.execute_and_validate(code, feature_col):
                        self._write_features_to_neon(feature_col)
                        self._save_to_registry(
                            feature_col=feature_col,
                            name=name,
                            url=suggestion.get("url", ""),
                            code=code,
                        )
                        summary["integrated"].append({
                            "name": name,
                            "feature": feature_col,
                            "url": suggestion.get("url", ""),
                        })
                        logger.info(f"  [OK] Integrated: {name} -> {feature_col} ({len(summary['integrated'])}/{TARGET_INTEGRATIONS})")
                    else:
                        summary["rejected"].append({"name": name, "reason": "validation failed"})
                        (PROCESSED_PATH / f"{feature_col}.parquet").unlink(missing_ok=True)

                except Exception as e:
                    tb = traceback.format_exc()
                    logger.error(f"  Error evaluating {name}: {e}\n{tb}")
                    summary["errors"].append({"name": name, "error": str(e)})

        if len(summary["integrated"]) < TARGET_INTEGRATIONS:
            logger.warning(f"Could only integrate {len(summary['integrated'])}/{TARGET_INTEGRATIONS} sources after {round_num} rounds")

        # 4. ログ保存
        log_file = AGENTS_LOG_PATH / f"scout_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        with open(log_file, "w") as f:
            json.dump({**summary, "analysis": analysis}, f, indent=2, ensure_ascii=False)

        logger.info("\n" + "=" * 60)
        logger.info(f"Data Scout Complete:")
        logger.info(f"  Integrated: {len(summary['integrated'])} sources")
        logger.info(f"  Rejected:   {len(summary['rejected'])} sources")
        logger.info(f"  Errors:     {len(summary['errors'])}")
        logger.info("=" * 60)

        return summary

    # ──────────────────────────────────────────────────
    # フォールバック: APIキー不要の組み込み提案
    # ──────────────────────────────────────────────────
    def _builtin_suggestions(self) -> list[dict]:
        """
        APIキー不要の事前定義データソース提案。
        Claude APIが使えない場合でも有益なデータを取得する。
        """
        return [
            {
                "name": "Armed Conflict Dataset (PRIO/Uppsala)",
                "url": "https://ucdp.uu.se/downloads/ucdpprio/ucdp-prio-acd-241.xlsx",
                "description": "UCDP/PRIO Armed Conflict Dataset - 国家間・内戦の詳細分類",
                "country_col": "location_inc",
                "year_col": "year",
                "value_cols": ["type_of_conflict", "intensity_level"],
                "feature_col_name": "ucdp_conflict_type",
            },
            {
                "name": "Global Peace Index Component Data",
                "url": "https://visionofhumanity.org/wp-content/uploads/2024/06/GPI-2024-overall-scores-and-domains-2008-2024.xlsx",
                "description": "グローバル平和指数 - 社会安全、国内・国際紛争、軍事化の3ドメイン",
                "country_col": "Country",
                "year_col": "Year",
                "value_cols": ["Overall Score", "Safety and Security", "Ongoing Conflict"],
                "feature_col_name": "global_peace_index",
            },
            {
                "name": "World Bank Fragility Indicators",
                "url": "https://api.worldbank.org/v2/country/all/indicator/IQ.CPA.TRAN.XQ?format=json&per_page=10000&mrv=20",
                "description": "World Bank CPIA 透明性・腐敗指標 - 脆弱国家識別に有効",
                "country_col": "countryiso3code",
                "year_col": "date",
                "value_cols": ["value"],
                "feature_col_name": "wb_cpia_transparency",
            },
        ]


def run_data_scout() -> dict:
    """エントリーポイント (Airflow DAGから呼び出し)"""
    scout = DataScout()
    return scout.run()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run_data_scout()
    print(json.dumps(result, indent=2, ensure_ascii=False))
