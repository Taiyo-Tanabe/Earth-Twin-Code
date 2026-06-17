"""
UCDP GED 年次パイプライン
スケジュール: 毎年 1/15 08:00 UTC
- UCDP GED 新版（前年分、1月公開）取得 / ACLED (API key設定時は優先)
- World Bank WDI 更新
- Powell-Thyne クーデターデータ更新 (政権崩壊ラベル)
- 隣国リスト再生成
- モデル再学習 + 全国予測
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
    dag_id="annual_ucdp_pipeline",
    default_args=default_args,
    description="UCDP GED新版取得 + World Bank更新 + モデル再学習 (毎年1/15)",
    schedule_interval="0 8 15 1 *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["annual", "ucdp", "training"],
) as dag:

    def task_download_conflict(**ctx):
        """ACLED優先、なければUCDP GED"""
        import datetime
        current_year = datetime.date.today().year
        from ingestion.acled import fetch_acled_country_year
        df = fetch_acled_country_year(1997, current_year)
        if df is not None and not df.empty:
            ctx["ti"].xcom_push("conflict_source", "acled")
            ctx["ti"].xcom_push("conflict_rows", len(df))
            return
        from ingestion.ucdp import build_conflict_panel
        df = build_conflict_panel(1989, current_year)
        ctx["ti"].xcom_push("conflict_source", "ucdp")
        ctx["ti"].xcom_push("conflict_rows", len(df))

    def task_fetch_worldbank(**ctx):
        from ingestion.worldbank import fetch_worldbank
        df = fetch_worldbank()
        ctx["ti"].xcom_push("wb_rows", len(df))

    def task_update_coups(**ctx):
        """Powell-Thyne クーデターデータ更新"""
        import datetime
        current_year = datetime.date.today().year
        from ingestion.powell_thyne import build_coup_panel
        df = build_coup_panel(1950, current_year)
        ctx["ti"].xcom_push("coup_rows", len(df))

    def task_build_adjacency(**ctx):
        from ingestion.adjacency import build_adjacency
        df = build_adjacency()
        ctx["ti"].xcom_push("adj_pairs", len(df))

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

    t1 = PythonOperator(task_id="download_conflict",   python_callable=task_download_conflict)
    t2 = PythonOperator(task_id="fetch_worldbank",     python_callable=task_fetch_worldbank)
    t2b = PythonOperator(task_id="update_coups",       python_callable=task_update_coups)
    t3 = PythonOperator(task_id="build_adjacency",     python_callable=task_build_adjacency)
    t4 = PythonOperator(task_id="build_features",      python_callable=task_build_features)
    t5 = PythonOperator(task_id="train_and_predict",   python_callable=task_train_and_predict)

    [t1, t2, t2b, t3] >> t4 >> t5
