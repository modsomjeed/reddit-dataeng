"""Connection settings and logging shared by the pipeline scripts."""

import logging
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read_env() -> dict[str, str]:
    # .env is for running on the host; inside Airflow the values come from the environment
    env = {
        "CLICKHOUSE_HOST": "localhost",
        "S3_ENDPOINT": "http://localhost:9002",
    }
    env_file = ROOT / ".env"
    lines = env_file.read_text().splitlines() if env_file.exists() else []
    for line in lines:
        if line.strip() and not line.startswith("#"):
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return {**env, **os.environ}


def setup_logging() -> None:
    # timestamps and levels, so Airflow task logs and terminal runs read the same way
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
