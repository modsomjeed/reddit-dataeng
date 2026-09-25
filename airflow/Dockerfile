FROM apache/airflow:3.3.2

# dbt gets its own virtualenv so its dependencies can't clash with Airflow's
RUN python -m venv /opt/airflow/dbt-venv \
    && /opt/airflow/dbt-venv/bin/pip install --no-cache-dir dbt-core==1.12.5 dbt-clickhouse==1.10.3
