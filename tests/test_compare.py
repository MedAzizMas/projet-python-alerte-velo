from datetime import datetime

import polars as pl

from velib_alert.compare import detect_changes

T0 = datetime(2026, 10, 23, 8, 0)
T1 = datetime(2026, 10, 23, 8, 10)


def snap(rows: list[tuple[int, int, int]], at: datetime) -> pl.LazyFrame:
    """rows = (station_id, vélos, places)"""
    return pl.LazyFrame(
        {
            "station_id": [r[0] for r in rows],
            "name": [f"Station {r[0]}" for r in rows],
            "num_bikes_available": [r[1] for r in rows],
            "num_docks_available": [r[2] for r in rows],
            "snapshot_at": [at] * len(rows),
        }
    )


# Exemple utilisé dans le README
OLD = snap([(101, 5, 10), (102, 2, 0), (103, 0, 15), (104, 7, 3), (105, 4, 4)], T0)
NEW = snap([(104, 10, 0), (101, 0, 15), (102, 2, 0), (103, 4, 11)], T1)  # ordre différent, 105 absente


def test_stations_passees_a_zero_velo() -> None:
    changes = detect_changes(OLD, NEW)
    assert changes.emptied["station_id"].to_list() == [101]


def test_station_deja_vide_ignoree() -> None:
    assert 103 not in detect_changes(OLD, NEW).emptied["station_id"].to_list()


def test_bonus_stations_devenues_pleines() -> None:
    # 104 devient pleine ; 102 l'était déjà donc pas d'alerte
    assert detect_changes(OLD, NEW).filled["station_id"].to_list() == [104]


def test_jointure_interne_ignore_station_absente() -> None:
    assert detect_changes(OLD, NEW).compared == 4
