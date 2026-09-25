DIAGRAMS_DIR := docs/architecture/diagrams
DBT_DIR      := dbt/reddit
DBT          := cd $(DBT_DIR) && uv run --env-file ../../.env dbt
START        ?= 2024-09-25
END          ?= 2026-09-24

.DEFAULT_GOAL := help
.PHONY: help setup up down ps logs backfill load dbt-build dbt-docs bootstrap airflow-test diagrams

help: ## Show every command and what it does
	@echo "Usage: make <command> [VAR=value]\n"
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup: ## Create .env from .env.example (never overwrites an existing .env)
	@if [ -f .env ]; then echo ".env already exists, leaving it alone"; \
	else cp .env.example .env && echo "created .env — set the passwords and PII_HASH_SALT before 'make up'"; fi

up: ## Build images and start every service (ClickHouse, RustFS, Airflow, dashboard)
	docker compose up -d --build
	@$(MAKE) --no-print-directory ps

down: ## Stop every service (data volumes are kept)
	docker compose down

ps: ## Show service status and URLs
	@docker compose ps --format 'table {{.Name}}\t{{.Status}}'
	@echo "\n  Dashboard       http://localhost:8501"
	@echo "  Airflow         http://localhost:8080  (airflow / airflow)"
	@echo "  RustFS console  http://localhost:9001/rustfs/console/"

logs: ## Follow logs, e.g. make logs SERVICE=airflow-scheduler
	docker compose logs -f $(SERVICE)

backfill: ## Extract posts from Arctic Shift to RustFS for START..END (skips days already there)
	uv run scripts/extract_reddit.py --start $(START) --end $(END)

load: ## Load every raw file from RustFS into ClickHouse (safe to rerun)
	uv run scripts/load_clickhouse.py

dbt-build: ## Build and test all dbt models
	$(DBT) build

dbt-docs: ## Generate dbt docs and serve them on http://localhost:8081
	$(DBT) docs generate
	$(DBT) docs serve --port 8081

bootstrap: setup up backfill load dbt-build ## First run: setup, up, backfill, load and dbt-build in one go

airflow-test: ## Run the whole reddit_daily DAG once for DAY, e.g. make airflow-test DAY=2026-09-24
	@test -n "$(DAY)" || (echo "set DAY=YYYY-MM-DD" && exit 1)
	docker exec airflow-scheduler airflow dags test reddit_daily $(DAY)

diagrams: ## Render every PlantUML diagram to SVG
	docker run --rm -v "$(CURDIR)/$(DIAGRAMS_DIR)":/data plantuml/plantuml:latest -tsvg "/data/*.puml"
