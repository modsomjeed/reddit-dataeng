.PHONY: help up down build init logs trigger dbt-run dbt-test dbt-docs clean

help:  ## show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	 awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n",$$1,$$2}'

build:  ## build the airflow image (with dbt baked in)
	docker compose build

up:  ## start the whole stack
	docker compose up -d
	@echo "Airflow  -> http://localhost:8080  (admin/admin)"
	@echo "MinIO    -> http://localhost:9001  (minio/minio12345)"
	@echo "ClickHouse HTTP -> http://localhost:8123"

down:  ## stop the stack (keep volumes)
	docker compose down

trigger:  ## manually run the ELT DAG once
	docker compose exec airflow-scheduler airflow dags trigger reddit_elt

dbt-run:  ## run dbt models manually inside the airflow container
	docker compose exec airflow-scheduler bash -lc \
	 'cd /opt/dbt && DBT_CLICKHOUSE_HOST=$$CLICKHOUSE_HOST DBT_CLICKHOUSE_PORT=$$CLICKHOUSE_HTTP_PORT \
	  DBT_CLICKHOUSE_USER=$$CLICKHOUSE_USER DBT_CLICKHOUSE_PASSWORD=$$CLICKHOUSE_PASSWORD \
	  DBT_CLICKHOUSE_SCHEMA=$$CLICKHOUSE_DB dbt run --profiles-dir /opt/dbt'

dbt-test:  ## run dbt tests (data governance / quality)
	docker compose exec airflow-scheduler bash -lc \
	 'cd /opt/dbt && DBT_CLICKHOUSE_HOST=$$CLICKHOUSE_HOST DBT_CLICKHOUSE_PORT=$$CLICKHOUSE_HTTP_PORT \
	  DBT_CLICKHOUSE_USER=$$CLICKHOUSE_USER DBT_CLICKHOUSE_PASSWORD=$$CLICKHOUSE_PASSWORD \
	  DBT_CLICKHOUSE_SCHEMA=$$CLICKHOUSE_DB dbt test --profiles-dir /opt/dbt'

deps:  ## install dbt packages (dbt_utils)
	docker compose exec airflow-scheduler bash -lc 'cd /opt/dbt && dbt deps'

logs:  ## tail scheduler logs
	docker compose logs -f airflow-scheduler

clean:  ## stop and DELETE all volumes (fresh start)
	docker compose down -v
