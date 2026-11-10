"""Settings read from environment variables (.env in the repo root for local runs)."""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Local runs: load ../.env relative to data-pipeline/. In Docker the variables come from env_file.
load_dotenv(Path(__file__).resolve().parents[3] / ".env")


@dataclass(frozen=True)
class Settings:
    openaq_api_key: str
    station_ids: list[int]
    db_dsn: str


def load_settings() -> Settings:
    key = os.environ.get("OPENAQ_API_KEY", "")
    if not key:
        raise RuntimeError("OPENAQ_API_KEY is not set. Copy .env.example to .env and add your own key.")
    ids = [int(x) for x in os.environ.get("ACTIVE_STATION_IDS", "").split(",") if x.strip()]
    dsn = (
        f"host={os.environ.get('POSTGRES_HOST', 'localhost')} "
        f"port={os.environ.get('POSTGRES_PORT', '5432')} "
        f"dbname={os.environ.get('POSTGRES_DB', 'brweather')} "
        f"user={os.environ.get('POSTGRES_USER', 'brweather')} "
        f"password={os.environ.get('POSTGRES_PASSWORD', '')}"
    )
    return Settings(openaq_api_key=key, station_ids=ids, db_dsn=dsn)
