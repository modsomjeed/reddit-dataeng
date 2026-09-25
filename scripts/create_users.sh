#!/usr/bin/env bash
# ============================================================
# Access control — runs inside the ClickHouse container on first
# startup via /docker-entrypoint-initdb.d/ (safe to re-run).
# The analyst role can read the mart tables only; dbt grants it
# SELECT on each mart model after every build.
# ============================================================

set -e

clickhouse-client --user "$CLICKHOUSE_USER" --password "$CLICKHOUSE_PASSWORD" --multiquery <<EOSQL
CREATE ROLE IF NOT EXISTS analyst;
CREATE USER IF NOT EXISTS dashboard IDENTIFIED WITH sha256_password BY '${CLICKHOUSE_DASHBOARD_PASSWORD}' DEFAULT ROLE analyst;
GRANT analyst TO dashboard;
EOSQL

echo "[create_users] analyst role and dashboard user ready"
