"""Chargement et validation de la configuration YAML."""

from pathlib import Path

import yaml
from pydantic import BaseModel, HttpUrl, PositiveInt


class ApiConfig(BaseModel):
    status_url: HttpUrl
    information_url: HttpUrl
    timeout_s: PositiveInt = 10
    retries: PositiveInt = 3


class PathsConfig(BaseModel):
    snapshots_dir: Path = Path("data/snapshots")
    log_file: Path = Path("logs/alertes.log")


class CleaningConfig(BaseModel):
    max_age_minutes: PositiveInt = 120
    capacity_tolerance: int = 2


class WatchConfig(BaseModel):
    interval_s: PositiveInt = 300


class Settings(BaseModel):
    api: ApiConfig
    paths: PathsConfig = PathsConfig()
    cleaning: CleaningConfig = CleaningConfig()
    watch: WatchConfig = WatchConfig()


def load_settings(path: Path) -> Settings:
    with path.open(encoding="utf-8") as f:
        return Settings.model_validate(yaml.safe_load(f))
