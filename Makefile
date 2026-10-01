DIAGRAMS_DIR := docs/architecture/diagrams
PLANTUML     := plantuml/plantuml:1.2026.8
PLAYWRIGHT   := mcr.microsoft.com/playwright/python:v1.63.0-noble
DBT_DIR      := dbt/reddit
DBT          := cd $(DBT_DIR) && uv run --env-file ../../.env dbt
START        ?= 2024-09-25
END          ?= 2026-09-24
KIND         ?= posts

# ports and credentials for the URLs printed by `make ps`
-include .env
AIRFLOW_PORT ?= 8082
MAILPIT_PORT ?= 8025

.DEFAULT_GOAL := help
.PHONY: help setup up down ps logs backfill load backup-raw restore-raw lint test dbt-build dbt-docs bootstrap ingest-test dbt-test alert-test digest-test screenshots diagrams

help: ## Show every command and what it does
	@echo "Usage: make <command> [VAR=value]\n"
	@grep -hE '^[a-zA-Z_-]+:.*?## ' Makefile | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup: ## Create .env from .env.example (never overwrites an existing .env)
	@if [ -f .env ]; then echo ".env already exists, leaving it alone"; \
	else cp .env.example .env && echo "created .env — set the passwords and PII_HASH_SALT before 'make up'"; fi

up: ## Build images and start every service (ClickHouse, RustFS, Airflow, dashboard, Mailpit)
	docker compose up -d --build
	@$(MAKE) --no-print-directory ps

down: ## Stop every service (data volumes are kept)
	docker compose down

ps: ## Show service status and URLs
	@docker compose ps --format 'table {{.Name}}\t{{.Status}}'
	@echo "\n  Dashboard       http://localhost:8501"
	@echo "  Airflow         http://localhost:$(AIRFLOW_PORT)  (airflow / airflow)"
	@echo "  RustFS console  http://localhost:9001/rustfs/console/"
	@echo "  Mailpit         http://localhost:$(MAILPIT_PORT)  (failure alerts)"

logs: ## Follow logs, e.g. make logs SERVICE=airflow-scheduler
	docker compose logs -f $(SERVICE)

backfill: ## Extract KIND=posts|comments from Arctic Shift to RustFS for START..END (skips days already there)
	uv run scripts/extract_reddit.py --kind $(KIND) --start $(START) --end $(END)

load: ## Load every raw KIND=posts|comments file from RustFS into ClickHouse (safe to rerun)
	uv run scripts/load_clickhouse.py --kind $(KIND)

backup-raw: ## Copy the raw bucket (posts + comments JSON) to data/backup/ — rerun to pick up new days
	uv run scripts/backup_raw.py backup

restore-raw: ## Upload files from data/backup/ that the raw bucket is missing (e.g. after losing Docker volumes)
	uv run scripts/backup_raw.py restore

lint: ## Lint the Python code with ruff
	uv run ruff check .

test: ## Run the unit tests (the end-to-end checks run in CI)
	uv run pytest

dbt-build: ## Build and test all dbt models
	$(DBT) build

dbt-docs: ## Generate dbt docs and serve them on http://localhost:8081
	$(DBT) docs generate
	$(DBT) docs serve --port 8081

bootstrap: setup up ## First run: setup, up, then backfill and load posts and comments, then dbt-build
	$(MAKE) backfill KIND=posts
	$(MAKE) backfill KIND=comments
	$(MAKE) load KIND=posts
	$(MAKE) load KIND=comments
	$(MAKE) dbt-build

ingest-test: ## Run the reddit_ingest DAG once for DAY (extract + load only), e.g. make ingest-test DAY=2026-09-24
	@test -n "$(DAY)" || (echo "set DAY=YYYY-MM-DD" && exit 1)
	docker exec airflow-scheduler airflow dags test reddit_ingest $(DAY)

dbt-test: ## Run the reddit_dbt DAG once (source freshness, then dbt build) inside Airflow
	docker exec airflow-scheduler airflow dags test reddit_dbt

alert-test: ## Run the alert_check DAG once; a failure email should appear in Mailpit
	-docker exec airflow-scheduler airflow dags test alert_check
	@echo "\nCheck the inbox at http://localhost:$(MAILPIT_PORT)"

digest-test: ## Run the reddit_digest DAG once (reverse ETL); the digest email should appear in Mailpit
	docker exec airflow-scheduler airflow dags test reddit_digest
	@echo "\nCheck the inbox at http://localhost:$(MAILPIT_PORT)"

screenshots: ## Capture README screenshots of the running dashboard, Airflow, RustFS and Mailpit into docs/images/ (SHOTS=… for a subset)
	docker run --rm --env-file .env -v "$(CURDIR)":/work -w /work $(PLAYWRIGHT) \
		bash -c "pip install -q playwright==1.63.0 && python scripts/screenshots.py $(SHOTS)"

diagrams: ## Render every PlantUML diagram to SVG
	docker run --rm -v "$(CURDIR)/$(DIAGRAMS_DIR)":/data $(PLANTUML) -tsvg "/data/*.puml"
