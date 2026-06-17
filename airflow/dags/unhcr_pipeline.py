"""
UNHCR 年次更新パイプライン
スケジュール: 毎年 7/1 08:00 UTC (UNHCR Global Trends は6月公開)
- UNHCR 難民・避難民データ更新
- パネル再構築 + 予測更新 (再学習なし)
"""
from datetime import datetime, timedelta
import sys

sys.path.insert(0, "/opt/airflow/backend")

from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "earth-twin",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(hours=1),
    "email_on_failure": False,
}

with DAG(
    dag_id="unhcr_annual_update",
    default_args=default_args,
    description="UNHCR 難民データ更新 (毎年7/1)",
    schedule_interval="0 8 1 7 *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["annual", "unhcr"],
) as dag:

    def task_fetch_unhcr(**ctx):
        from ingestion.unhcr import fetch_unhcr
        df = fetch_unhcr(2000, 2024)
        ctx["ti"].xcom_push("unhcr_rows", len(df))

    def task_refresh_panel_and_predict(**ctx):
        from features.panel import build_panel
        from models.predict import predict_all_countries
        build_panel()
        predict_all_countries()

    t1 = PythonOperator(task_id="fetch_unhcr",                 python_callable=task_fetch_unhcr)
    t2 = PythonOperator(task_id="refresh_panel_and_predict",   python_callable=task_refresh_panel_and_predict)

    t1 >> t2
