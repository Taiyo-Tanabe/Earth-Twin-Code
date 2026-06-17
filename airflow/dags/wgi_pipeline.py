"""
WGI + モデル再学習パイプライン
スケジュール: 毎年 11/1 08:00 UTC (WGI は10月公開)
- World Governance Indicators 新版取得
- パネル再構築 + モデル再学習 + 全国予測
  ※ WGI は統治スコアの重要指標のため、更新後は再学習を行う
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
    "retry_delay": timedelta(minutes=30),
    "email_on_failure": False,
}

with DAG(
    dag_id="wgi_retrain_pipeline",
    default_args=default_args,
    description="WGI統治指標更新 + モデル再学習 (毎年11/1)",
    schedule_interval="0 8 1 11 *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["annual", "wgi", "training"],
) as dag:

    def task_fetch_wgi(**ctx):
        from ingestion.polity import download_powell_thyne_coups
        df = download_powell_thyne_coups()
        ctx["ti"].xcom_push("wgi_rows", len(df))

    def task_build_features(**ctx):
        from features.panel import build_panel
        df = build_panel()
        ctx["ti"].xcom_push("panel_rows", len(df))

    def task_train_and_predict(**ctx):
        from models.train import train_conflict_model, train_regime_model
        from models.predict import predict_all_countries
        c = train_conflict_model()
        r = train_regime_model()
        predict_all_countries()
        ctx["ti"].xcom_push("conflict_auc", c.get("roc_auc"))

    t1 = PythonOperator(task_id="fetch_wgi",           python_callable=task_fetch_wgi)
    t2 = PythonOperator(task_id="build_features",      python_callable=task_build_features)
    t3 = PythonOperator(task_id="train_and_predict",   python_callable=task_train_and_predict)

    t1 >> t2 >> t3
