"""Affichage coloré des alertes et écriture dans les logs (niveau WARNING)."""

import logging
from typing import Any

from velib_alert.compare import NEW, Changes

log = logging.getLogger("velib_alert.alerte")

RED = "\033[91m"
ORANGE = "\033[38;5;208m"
GREEN = "\033[92m"
RESET = "\033[0m"


def _period(row: dict[str, Any]) -> str:
    return f"entre {row['snapshot_at']:%H:%M:%S} et {row[f'snapshot_at{NEW}']:%H:%M:%S}"


def report(changes: Changes) -> int:
    """Affiche et journalise chaque alerte ; renvoie le nombre total d'alertes."""
    for row in changes.emptied.iter_rows(named=True):
        msg = (
            f"STATION VIDE   | {row[f'name{NEW}']} ({row['station_id']}) : "
            f"{row['num_bikes_available']} -> 0 vélo {_period(row)}"
        )
        print(f"{RED}{msg}{RESET}")
        log.warning(msg)

    for row in changes.filled.iter_rows(named=True):
        msg = (
            f"STATION PLEINE | {row[f'name{NEW}']} ({row['station_id']}) : "
            f"{row['num_docks_available']} -> 0 place libre {_period(row)}"
        )
        print(f"{ORANGE}{msg}{RESET}")
        log.warning(msg)

    total = changes.emptied.height + changes.filled.height
    summary = (
        f"{changes.compared} stations comparées : "
        f"{changes.emptied.height} vidée(s), {changes.filled.height} devenue(s) pleine(s)"
    )
    print(f"{GREEN}{summary}{RESET}")
    log.info(summary)
    return total
