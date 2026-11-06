from datetime import datetime
from pathlib import Path

from velib_alert.config import load_settings
from velib_alert.ingest import build_snapshot

SETTINGS = load_settings(Path(__file__).parents[1] / "configs" / "config.yaml")
NOW = datetime(2026, 10, 23, 8, 0)
FRESH = int(NOW.timestamp()) - 60


def status(sid: int, bikes: int, docks: int, **extra: object) -> dict[str, object]:
    return {
        "station_id": sid, "num_bikes_available": bikes,
        "num_bikes_available_types": [{"mechanical": bikes}, {"ebike": 0}],
        "num_docks_available": docks, "is_installed": 1, "is_renting": 1,
        "is_returning": 1, "last_reported": FRESH, **extra,
    }


def info(sid: int, capacity: int = 20) -> dict[str, object]:
    return {"station_id": sid, "name": f"S{sid}", "lat": 48.85, "lon": 2.35, "capacity": capacity}


def test_preparation_complete() -> None:
    raw_status = [
        status(1, 5, 15),                                     # OK
        status(1, 5, 15),                                     # doublon
        status(2, -3, 10),                                    # corrompue
        status(3, 2, 2, is_renting=0, is_returning=0),        # hors service
        status(4, 2, 2, last_reported=FRESH - 10 * 3600),     # trop ancienne
        status(5, 30, 30),                                    # > capacité
        status(6, 1, 1),                                      # pas de fiche info
    ]
    raw_info = [info(1), info(2), info(3), info(4), info(5)]

    df = build_snapshot(raw_status, raw_info, NOW, SETTINGS)

    assert df["station_id"].to_list() == [1]
    assert df["name"].item() == "S1"
    assert df["snapshot_at"].item() == NOW
