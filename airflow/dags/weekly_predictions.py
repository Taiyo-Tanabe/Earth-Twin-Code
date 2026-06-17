"""
週次予測更新 DAG
スケジュール: 毎週月曜 06:00 UTC

処理:
- World Bank から最新四半期データを取得
- UNHCR から最新難民数を取得
- 既存モデルで全国リスクスコアを再計算 (再学習なし)
- TimescaleDB に書き込み
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
    "retry_delay": timedelta(minutes=20),
    "email_on_failure": False,
}

with DAG(
    dag_id="weekly_predictions",
    default_args=default_args,
    description="週次リスクスコア再計算",
    schedule_interval="0 6 * * 1",  # 毎週月曜 06:00 UTC
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["weekly", "predictions"],
) as dag:

    def task_refresh_acled(**ctx):
        """ACLED直近データを更新 (API key設定時のみ)"""
        import datetime
        current_year = datetime.date.today().year
        from ingestion.acled import fetch_acled_country_year
        df = fetch_acled_country_year(current_year - 1, current_year)
        if df is not None:
            ctx["ti"].xcom_push("acled_rows", len(df))

    def task_refresh_panel(**ctx):
        """最新データでパネルを更新"""
        from features.panel import build_panel
        df = build_panel()
        ctx["ti"].xcom_push("panel_rows", len(df))

    def task_run_predictions(**ctx):
        """全国リスクスコアを再計算"""
        from models.predict import predict_all_countries
        df = predict_all_countries()
        ctx["ti"].xcom_push("predicted_countries", len(df))

        # 上位10か国をログ
        top = df.nlargest(10, "conflict_probability")
        for _, row in top.iterrows():
            print(f"  {row['country_code']}: {row['conflict_probability']:.3f}")

    def task_check_anomalies(**ctx):
        """
        先週比で大幅に変化した国をフラグ立て。
        異常検知: 確率が ±20% 以上変化した国をアラート。
        """
        import os, sqlalchemy as sa, pandas as pd
        db_url = os.environ.get("TIMESCALE_URL", "postgresql://earthtwin:earthtwin123@timescaledb:5432/earthtwin")
        engine = sa.create_engine(db_url)
        try:
            with engine.connect() as conn:
                df = pd.read_sql("""
                    SELECT country_code, conflict_probability, time
                    FROM risk_predictions
                    WHERE time >= NOW() - INTERVAL '14 days'
                    ORDER BY time DESC
                """, conn)

            if df.empty:
                return

            latest = df.groupby("country_code").first().reset_index()
            prev = df[df["time"] < df["time"].max() - pd.Timedelta(days=7)]
            prev = prev.groupby("country_code").first().reset_index()

            merged = latest.merge(prev, on="country_code", suffixes=("_now", "_prev"))
            merged["delta"] = merged["conflict_probability_now"] - merged["conflict_probability_prev"]
            anomalies = merged[merged["delta"].abs() > 0.2]

            if not anomalies.empty:
                print(f"⚠️  {len(anomalies)} countries with large probability changes:")
                for _, row in anomalies.iterrows():
                    print(f"  {row['country_code']}: {row['conflict_probability_prev']:.3f} → {row['conflict_probability_now']:.3f} (Δ{row['delta']:+.3f})")

            ctx["ti"].xcom_push("n_anomalies", len(anomalies))
        except Exception as e:
            print(f"Anomaly check failed: {e}")

    t0 = PythonOperator(task_id="refresh_acled",    python_callable=task_refresh_acled)
    t1 = PythonOperator(task_id="refresh_panel",   python_callable=task_refresh_panel)
    t2 = PythonOperator(task_id="run_predictions", python_callable=task_run_predictions)
    t3 = PythonOperator(task_id="check_anomalies", python_callable=task_check_anomalies)

    t0 >> t1 >> t2 >> t3
