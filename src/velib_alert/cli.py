"""Interface en ligne de commande : snapshot, alert, watch."""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

from velib_alert.alerts import report
from velib_alert.compare import compare_files
from velib_alert.config import Settings, load_settings
from velib_alert.ingest import list_snapshots, take_snapshot
from velib_alert.logger import setup_logging

log = logging.getLogger(__name__)


def cmd_snapshot(settings: Settings, args: argparse.Namespace) -> int:
    path = take_snapshot(settings)
    print(f"Snapshot enregistré : {path}")
    return 0


def cmd_alert(settings: Settings, args: argparse.Namespace) -> int:
    if args.old and args.new:
        old, new = Path(args.old), Path(args.new)
    else:
        snapshots = list_snapshots(settings.paths.snapshots_dir)
        if len(snapshots) < 2:
            print("Il faut au moins deux snapshots (lancez d'abord : velib-alert snapshot).", file=sys.stderr)
            return 1
        old, new = snapshots[-2], snapshots[-1]
    print(f"Comparaison : {old.name}  ->  {new.name}")
    log.info("Comparaison %s -> %s", old, new)
    report(compare_files(old, new))
    return 0


def cmd_watch(settings: Settings, args: argparse.Namespace) -> int:
    interval = args.interval or settings.watch.interval_s
    previous = take_snapshot(settings)
    print(f"Surveillance démarrée (un relevé toutes les {interval} s, Ctrl+C pour arrêter)")
    try:
        while True:
            time.sleep(interval)
            try:
                current = take_snapshot(settings)
            except Exception:
                log.exception("Relevé impossible, nouvelle tentative au prochain cycle")
                continue
            print(f"\n--- {current.name} ---")
            report(compare_files(previous, current))
            previous = current
    except KeyboardInterrupt:
        print("\nSurveillance arrêtée.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="velib-alert", description=__doc__)
    parser.add_argument(
        "--config", default=os.environ.get("VELIB_CONFIG", "configs/config.yaml"),
        help="chemin du fichier YAML de configuration",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("snapshot", help="prendre un relevé et l'enregistrer en Parquet").set_defaults(func=cmd_snapshot)

    alert = sub.add_parser("alert", help="comparer deux relevés (par défaut : les deux derniers)")
    alert.add_argument("old", nargs="?", help="snapshot le plus ancien")
    alert.add_argument("new", nargs="?", help="snapshot le plus récent")
    alert.set_defaults(func=cmd_alert)

    watch = sub.add_parser("watch", help="relevés périodiques et alertes en continu")
    watch.add_argument("--interval", type=int, help="secondes entre deux relevés (sinon : config)")
    watch.set_defaults(func=cmd_watch)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings(Path(args.config))
    setup_logging(settings.paths.log_file)
    if os.name == "nt":
        os.system("")  # active les couleurs ANSI dans la console Windows
    code: int = args.func(settings, args)
    return code


if __name__ == "__main__":
    sys.exit(main())
