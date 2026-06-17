"""
AI Data Scout DAG
スケジュール: 毎月1日 04:00 UTC

Claude APIを使って新しいデータソースを自律発見・統合する。
発見したデータが品質基準を満たす場合、次回の年次パイプラインから自動で使用される。
"""
from datetime import datetime, timedelta
import sys

sys.path.insert(0, "/opt/airflow/backend")

from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "earth-twin",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(hours=1),
    "email_on_failure": False,
}

with DAG(
    dag_id="ai_data_scout",
    default_args=default_args,
    description="Claude AI による自律データソース発見・統合",
    schedule_interval="0 4 1 * *",  # 毎月1日 04:00 UTC
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["monthly", "ai", "data-scout"],
) as dag:

    def task_run_scout(**ctx):
        """Data Scout エージェントを実行 (既存ソース更新 + 新ソース発見)"""
        from agents.data_scout import run_data_scout
        result = run_data_scout()
        ctx["ti"].xcom_push("integrated", len(result.get("integrated", [])))
        ctx["ti"].xcom_push("rejected", len(result.get("rejected", [])))
        ctx["ti"].xcom_push("errors", len(result.get("errors", [])))

    def task_rebuild_if_new(**ctx):
        """新データが統合された場合のみパネルを再構築"""
        integrated = ctx["ti"].xcom_pull(task_ids="run_data_scout", key="integrated") or 0
        if integrated == 0:
            print("No new data sources integrated. Skipping rebuild.")
            return

        print(f"New sources integrated: {integrated}. Rebuilding panel...")
        from features.panel import build_panel
        df = build_panel()
        print(f"Panel rebuilt: {df.shape}")

    def task_notify(**ctx):
        """実行結果を DB に記録"""
        import os, json, sqlalchemy as sa
        from datetime import date

        integrated = ctx["ti"].xcom_pull(task_ids="run_data_scout", key="integrated") or 0
        rejected = ctx["ti"].xcom_pull(task_ids="run_data_scout", key="rejected") or 0
        errors = ctx["ti"].xcom_pull(task_ids="run_data_scout", key="errors") or 0

        print(f"Data Scout Summary [{date.today()}]:")
        print(f"  ✅ Integrated: {integrated} new sources")
        print(f"  ❌ Rejected:   {rejected}")
        print(f"  ⚠️  Errors:     {errors}")

        db_url = os.environ.get("TIMESCALE_URL", "postgresql://earthtwin:earthtwin123@timescaledb:5432/earthtwin")
        engine = sa.create_engine(db_url)
        try:
            with engine.begin() as conn:
                conn.execute(sa.text("""
                    CREATE TABLE IF NOT EXISTS scout_runs (
                        run_date DATE PRIMARY KEY,
                        integrated INT,
                        rejected INT,
                        errors INT
                    )
                """))
                conn.execute(sa.text("""
                    INSERT INTO scout_runs (run_date, integrated, rejected, errors)
                    VALUES (:d, :i, :r, :e)
                    ON CONFLICT (run_date) DO UPDATE SET
                        integrated = EXCLUDED.integrated,
                        rejected = EXCLUDED.rejected,
                        errors = EXCLUDED.errors
                """), {"d": str(date.today()), "i": integrated, "r": rejected, "e": errors})
        except Exception as e:
            print(f"DB write failed: {e}")

    t1 = PythonOperator(task_id="run_data_scout",    python_callable=task_run_scout)
    t2 = PythonOperator(task_id="rebuild_if_new",    python_callable=task_rebuild_if_new)
    t3 = PythonOperator(task_id="notify_results",    python_callable=task_notify)

    t1 >> t2 >> t3
