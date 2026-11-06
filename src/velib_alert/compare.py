"""Comparaison de deux snapshots : jointure temporelle + comparaison de colonnes."""

from dataclasses import dataclass
from pathlib import Path

import polars as pl

KEY = "station_id"
NEW = "_apres"

REPORT_COLUMNS = [
    KEY, f"name{NEW}",
    "num_bikes_available", f"num_bikes_available{NEW}",
    "num_docks_available", f"num_docks_available{NEW}",
    "snapshot_at", f"snapshot_at{NEW}",
]


@dataclass(frozen=True)
class Changes:
    emptied: pl.DataFrame  # stations passées à 0 vélo
    filled: pl.DataFrame   # stations devenues pleines (bonus)
    compared: int          # stations présentes dans les deux relevés


def join_snapshots(old: pl.LazyFrame, new: pl.LazyFrame) -> pl.LazyFrame:
    """Une ligne par station : colonnes « avant » (sans suffixe) et « après » (suffixe _apres)."""
    return old.join(new, on=KEY, how="inner", suffix=NEW)


def detect_changes(old: pl.LazyFrame, new: pl.LazyFrame) -> Changes:
    joined = join_snapshots(old, new)

    emptied = joined.filter(
        (pl.col("num_bikes_available") > 0) & (pl.col(f"num_bikes_available{NEW}") == 0)
    )
    filled = joined.filter(
        (pl.col("num_docks_available") > 0) & (pl.col(f"num_docks_available{NEW}") == 0)
    )
    emptied_df, filled_df, count = pl.collect_all(
        [emptied.select(REPORT_COLUMNS), filled.select(REPORT_COLUMNS), joined.select(pl.len())]
    )
    return Changes(emptied=emptied_df, filled=filled_df, compared=int(count.item()))


def compare_files(old_path: Path, new_path: Path) -> Changes:
    return detect_changes(pl.scan_parquet(old_path), pl.scan_parquet(new_path))
