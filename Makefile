.PHONY: help build up down init deps trigger dbt-run dbt-test dbt-freshness dbt-docs logs clean

# ClickHouse credentials every dbt command needs (consumed by dbt/profiles.yml).
# Single-quoted in the recipe, so $$VAR is expanded by the container shell.
DBT_ENV := DBT_CLICKHOUSE_HOST=$$CLICKHOUSE_HOST DBT_CLICKHOUSE_PORT=$$CLICKHOUSE_HTTP_PORT \
 DBT_CLICKHOUSE_USER=$$CLICKHOUSE_USER DBT_CLICKHOUSE_PASSWORD=$$CLICKHOUSE_PASSWORD \
 DBT_CLICKHOUSE_SCHEMA=$$CLICKHOUSE_DB

define dbt
docker compose exec airflow-scheduler bash -lc 'cd /opt/dbt && $(DBT_ENV) dbt $(1) --profiles-dir /opt/dbt'
endef

help:  ## show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	 awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n",$$1,$$2}'

build:  ## build the airflow image (with dbt baked in)
	docker compose build

up:  ## start the whole stack
	docker compose up -d
	@echo "Airflow  -> http://localhost:8080  (admin/admin)"
	@echo "MinIO    -> http://localhost:9001  (minio/minio12345)"
	@echo "ClickHouse HTTP -> http://localhost:8123"

init: up  ## first run: start the stack, wait for airflow, install dbt packages
	@echo "waiting for airflow-scheduler ..."
	@until docker compose exec -T airflow-scheduler airflow version >/dev/null 2>&1; do sleep 3; done
	@$(MAKE) deps

deps:  ## install dbt packages (dbt_utils)
	docker compose exec airflow-scheduler bash -lc 'cd /opt/dbt && dbt deps'

down:  ## stop the stack (keep volumes)
	docker compose down

trigger:  ## manually run the ELT DAG once
	docker compose exec airflow-scheduler airflow dags trigger reddit_elt

dbt-run:  ## build staging + marts
	$(call dbt,run)

dbt-test:  ## data-quality gate: not_null / unique / accepted_range
	$(call dbt,test)

dbt-freshness:  ## warn when raw_posts is older than 26h
	$(call dbt,source freshness)

dbt-docs:  ## generate the lineage graph into dbt/target/
	$(call dbt,docs generate)

logs:  ## tail scheduler logs
	docker compose logs -f airflow-scheduler

clean:  ## stop and DELETE all volumes (fresh start)
	docker compose down -v
