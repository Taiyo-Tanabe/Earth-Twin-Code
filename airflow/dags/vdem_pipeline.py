"""
V-Dem 年次更新パイプライン
スケジュール: 毎年 3/1 08:00 UTC (V-Dem は2月末〜3月初に公開)
- V-Dem Core 新版取得
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
    "retries": 1,
    "retry_delay": timedelta(hours=1),
    "email_on_failure": False,
}

with DAG(
    dag_id="vdem_annual_update",
    default_args=default_args,
    description="V-Dem 民主主義指標更新 (毎年3/1)",
    schedule_interval="0 8 1 3 *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["annual", "vdem"],
) as dag:

    def task_fetch_vdem(**ctx):
        from ingestion.vdem import fetch_vdem
        df = fetch_vdem(1990, 2024)
        ctx["ti"].xcom_push("vdem_rows", len(df))

    def task_refresh_panel_and_predict(**ctx):
        from features.panel import build_panel
        from models.predict import predict_all_countries
        build_panel()
        predict_all_countries()

    t1 = PythonOperator(task_id="fetch_vdem",                  python_callable=task_fetch_vdem)
    t2 = PythonOperator(task_id="refresh_panel_and_predict",   python_callable=task_refresh_panel_and_predict)

    t1 >> t2
