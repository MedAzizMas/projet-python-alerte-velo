# velib-alert — L'Alerte

Outil en ligne de commande qui interroge l'API temps réel Vélib' Métropole, enregistre des relevés (snapshots)
et **signale en rouge les stations passées à 0 vélo** entre deux relevés. Chaque alerte est aussi écrite dans
`logs/alertes.log` au niveau **WARNING**.
**Bonus :** les stations **devenues pleines** (plus aucune place pour rendre un vélo) sont signalées en orange.

Source des données : [data.gouv.fr — Vélib' disponibilité temps réel](https://www.data.gouv.fr/datasets/velib-velos-et-bornes-disponibilite-temps-reel/) (flux GBFS, sans clé).

## Installation

```bash
uv sync
```

## Utilisation

```bash
uv run velib-alert snapshot            # prend un relevé -> data/snapshots/snapshot_AAAAMMJJ_HHMMSS.parquet
uv run velib-alert alert               # compare les deux derniers relevés
uv run velib-alert alert A.parquet B.parquet   # compare deux relevés précis
uv run velib-alert watch --interval 300        # relevé toutes les 5 min + alertes en continu
```

Astuce démo : lancer `watch` à une heure de pointe (8h–9h ou 18h–19h) pour voir des alertes.

## Avec Docker

```bash
docker build -t velib-alert .
docker run --rm -v ./data:/app/data -v ./logs:/app/logs velib-alert watch --interval 300
```

## Fonctionnement

```
API GBFS ──httpx──> JSON ──Pydantic──> stations valides ──Polars──> nettoyage ──> jointure status+information ──> snapshot .parquet
                                                                                                                       │
                                        snapshot A (avant) ──┐                                                         │
                                                             ├── jointure sur station_id ──> comparaison de colonnes ──> alertes (console rouge/orange + log WARNING)
                                        snapshot B (après) ──┘
```

1. **Ingestion** (`ingest.py`) : `station_status.json` et `station_information.json` sont téléchargés avec httpx (3 tentatives).
2. **Validation** (`schemas.py`) : chaque station passe par un schéma Pydantic ; les données corrompues
   (valeurs négatives, identifiant manquant, mécaniques + électriques ≠ total, coordonnées hors Île-de-France)
   sont rejetées et comptées dans les logs.
3. **Nettoyage** : doublons, stations hors service (ni location ni retour), remontées trop anciennes,
   incohérences vélos + places > capacité.
4. **Enrichissement** : jointure *status + information* sur `station_id` pour récupérer le nom, la position et la capacité.
5. **Comparaison** (`compare.py`) : jointure interne *snapshot A + snapshot B* sur `station_id` (Polars lazy), puis :
   - station vidée : `vélos_avant > 0` **et** `vélos_après == 0` ;
   - station remplie : `places_avant > 0` **et** `places_après == 0`.

   Une station déjà vide (ou déjà pleine) au premier relevé ne déclenche pas d'alerte : elle n'est pas « passée » à 0.
6. **Alertes** (`alerts.py`) : affichage coloré et `logging.warning`.

Exemple (repris dans `tests/test_compare.py`) :

| station | vélos 8h00 | vélos 8h10 | places 8h00 | places 8h10 | alerte |
|---|---|---|---|---|---|
| 101 | 5 | 0 | 10 | 15 | 🔴 vidée |
| 102 | 2 | 2 | 0 | 0 | — (déjà pleine) |
| 103 | 0 | 4 | 15 | 11 | — (déjà vide) |
| 104 | 7 | 10 | 3 | 0 | 🟠 devenue pleine |

## Arborescence

```
configs/config.yaml   # URLs, délais, seuils, intervalle de surveillance
src/velib_alert/      # cli, config, schemas, ingest, compare, alerts, logger
tests/                # pytest (sans réseau)
data/snapshots/       # relevés Parquet (ignorés par git)
logs/alertes.log      # journal (ignoré par git)
Dockerfile
```

## Qualité

```bash
uv run pytest
uv run mypy src
```
