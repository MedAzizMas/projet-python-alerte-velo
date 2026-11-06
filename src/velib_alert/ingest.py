"""Ingestion : API (httpx) -> validation (Pydantic) -> nettoyage (Polars) -> Parquet."""

import logging
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, TypeVar

import httpx
import polars as pl
from pydantic import BaseModel, ValidationError

from velib_alert.config import Settings
from velib_alert.schemas import StationInfo, StationStatus

log = logging.getLogger(__name__)

M = TypeVar("M", bound=BaseModel)

SNAPSHOT_PREFIX = "snapshot_"
SNAPSHOT_TIME_FORMAT = "%Y%m%d_%H%M%S"


def fetch_stations(client: httpx.Client, url: str, retries: int) -> list[dict[str, Any]]:
    """Télécharge un flux GBFS et renvoie la liste data.stations (avec nouvelles tentatives)."""
    for attempt in range(1, retries + 1):
        try:
            response = client.get(url)
            response.raise_for_status()
            stations: list[dict[str, Any]] = response.json()["data"]["stations"]
            return stations
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            log.error("Échec %d/%d sur %s : %s", attempt, retries, url, exc)
            if attempt == retries:
                raise
            time.sleep(2 * attempt)
    raise RuntimeError("nombre de tentatives invalide")


def validate(raw: list[dict[str, Any]], model: type[M]) -> list[M]:
    """Garde les enregistrements conformes au schéma et journalise les rejets."""
    valid: list[M] = []
    reasons: Counter[str] = Counter()
    for record in raw:
        try:
            valid.append(model.model_validate(record))
        except ValidationError as exc:
            first = exc.errors()[0]
            field = ".".join(str(p) for p in first["loc"]) or "station"
            reasons[f"{field}: {first['msg']}"] += 1
    log.info("%s : %d valides, %d rejetées", model.__name__, len(valid), sum(reasons.values()))
    for reason, n in reasons.most_common():
        log.warning("%s rejetée(s) x%d -> %s", model.__name__, n, reason)
    return valid


def to_frame(rows: list[M], model: type[M]) -> pl.DataFrame:
    if not rows:
        return pl.DataFrame(schema=list(model.model_fields))
    return pl.DataFrame([r.model_dump() for r in rows])


def clean_status(status: pl.DataFrame, snapshot_at: datetime, max_age_minutes: int) -> pl.DataFrame:
    """Supprime doublons, stations hors service et remontées trop anciennes."""
    before = status.height
    df = status.unique(subset="station_id", keep="first").filter(
        pl.col("is_installed") & (pl.col("is_renting") | pl.col("is_returning"))
    )
    min_epoch = int(snapshot_at.timestamp()) - max_age_minutes * 60
    fresh = df.filter(pl.col("last_reported") >= min_epoch)
    log.info(
        "Nettoyage : %d doublons/hors service, %d remontées trop anciennes (> %d min)",
        before - df.height, df.height - fresh.height, max_age_minutes,
    )
    return fresh.with_columns(pl.from_epoch("last_reported", time_unit="s"))


def enrich(status: pl.DataFrame, info: pl.DataFrame, capacity_tolerance: int) -> pl.DataFrame:
    """Jointure status + information, puis contrôle de cohérence avec la capacité."""
    info = info.unique(subset="station_id", keep="first")
    joined = status.join(info, on="station_id", how="inner")
    log.info("Jointure status/information : %d station(s) sans fiche descriptive", status.height - joined.height)
    coherent = joined.filter(
        pl.col("num_bikes_available") + pl.col("num_docks_available")
        <= pl.col("capacity") + capacity_tolerance
    )
    if coherent.height < joined.height:
        log.warning("%d station(s) rejetée(s) : vélos + places > capacité", joined.height - coherent.height)
    return coherent


def build_snapshot(
    raw_status: list[dict[str, Any]],
    raw_info: list[dict[str, Any]],
    snapshot_at: datetime,
    settings: Settings,
) -> pl.DataFrame:
    """Pipeline de préparation complet, sans réseau (donc testable)."""
    status = to_frame(validate(raw_status, StationStatus), StationStatus)
    info = to_frame(validate(raw_info, StationInfo), StationInfo)
    status = clean_status(status, snapshot_at, settings.cleaning.max_age_minutes)
    df = enrich(status, info, settings.cleaning.capacity_tolerance)
    return (
        df.with_columns(pl.lit(snapshot_at).alias("snapshot_at"))
        .select(
            "station_id", "name", "lat", "lon", "capacity",
            "num_bikes_available", "mechanical", "ebike", "num_docks_available",
            "is_renting", "is_returning", "last_reported", "snapshot_at",
        )
        .sort("station_id")
    )


def take_snapshot(settings: Settings) -> Path:
    """Télécharge les deux flux, prépare les données et écrit un fichier Parquet horodaté."""
    snapshot_at = datetime.now().replace(microsecond=0)
    with httpx.Client(timeout=settings.api.timeout_s) as client:
        raw_status = fetch_stations(client, str(settings.api.status_url), settings.api.retries)
        raw_info = fetch_stations(client, str(settings.api.information_url), settings.api.retries)

    df = build_snapshot(raw_status, raw_info, snapshot_at, settings)
    out_dir = settings.paths.snapshots_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{SNAPSHOT_PREFIX}{snapshot_at:{SNAPSHOT_TIME_FORMAT}}.parquet"
    df.write_parquet(path)
    log.info("Snapshot écrit : %s (%d stations)", path, df.height)
    return path


def list_snapshots(snapshots_dir: Path) -> list[Path]:
    """Snapshots triés du plus ancien au plus récent (l'horodatage du nom est triable)."""
    return sorted(snapshots_dir.glob(f"{SNAPSHOT_PREFIX}*.parquet"))
