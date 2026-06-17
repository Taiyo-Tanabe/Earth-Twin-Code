"""
日次パイプライン DAG
スケジュール: 毎日 07:30 UTC (GDELT は前日データを当日公開)

処理:
- GDELT v2 前日分の紛争シグナルを取得
- 速報リスクスコアを更新 (学習済みモデルを使用、再学習なし)
"""
from datetime import datetime, timedelta
import sys

sys.path.insert(0, "/opt/airflow/backend")

from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "earth-twin",
    "depends_on_past": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=10),
    "email_on_failure": False,
}

with DAG(
    dag_id="daily_signal_pipeline",
    default_args=default_args,
    description="日次 GDELT 紛争シグナル収集と速報スコア更新",
    schedule_interval="30 7 * * *",  # 毎日 07:30 UTC
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["daily", "gdelt"],
) as dag:

    def task_fetch_gdelt(**ctx):
        from ingestion.gdelt import get_latest_gdelt_day
        df = get_latest_gdelt_day()
        ctx["ti"].xcom_push("gdelt_rows", len(df))

    def task_update_daily_scores(**ctx):
        """
        GDELT の最新シグナルを使って速報リスクスコアを更新。
        フルモデルの再予測ではなく、GDELT シグナルで補正。
        """
        import pandas as pd
        import os
        import sqlalchemy as sa
        from datetime import date
        from pathlib import Path

        PROCESSED = Path("/app/data/processed")
        gdelt_monthly = PROCESSED / "gdelt_monthly.parquet"
        if not gdelt_monthly.exists():
            return

        df = pd.read_parquet(gdelt_monthly)
        today = date.today()
        today_df = df[df["date"].astype(str) >= str(today - timedelta(days=2))]
        if today_df.empty:
            return

        # 最新シグナルを daily_signals テーブルに保存
        db_url = os.environ.get("TIMESCALE_URL", "postgresql://earthtwin:earthtwin123@timescaledb:5432/earthtwin")
        engine = sa.create_engine(db_url)
        try:
            with engine.begin() as conn:
                conn.execute(sa.text("""
                    CREATE TABLE IF NOT EXISTS daily_signals (
                        time TIMESTAMPTZ NOT NULL,
                        country_code TEXT,
                        gdelt_conflict_events FLOAT,
                        gdelt_tone_avg FLOAT,
                        gdelt_goldstein_avg FLOAT
                    )
                """))
                for _, row in today_df.iterrows():
                    conn.execute(sa.text("""
                        INSERT INTO daily_signals
                            (time, country_code, gdelt_conflict_events, gdelt_tone_avg, gdelt_goldstein_avg)
                        VALUES
                            (NOW(), :cc, :events, :tone, :goldstein)
                        ON CONFLICT DO NOTHING
                    """), {
                        "cc": row["country_code"],
                        "events": float(row.get("conflict_events", 0)),
                        "tone": float(row.get("tone_avg", 0)),
                        "goldstein": float(row.get("goldstein_avg", 0)),
                    })
        except Exception as e:
            print(f"DB write failed: {e}")

        ctx["ti"].xcom_push("updated_countries", len(today_df))

    t1 = PythonOperator(task_id="fetch_gdelt_daily", python_callable=task_fetch_gdelt)
    t2 = PythonOperator(task_id="update_daily_scores", python_callable=task_update_daily_scores)

    t1 >> t2
