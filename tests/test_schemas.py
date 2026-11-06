import pytest
from pydantic import ValidationError

from velib_alert.schemas import StationInfo, StationStatus

GOOD_STATUS = {
    "station_id": 1,
    "num_bikes_available": 3,
    "num_bikes_available_types": [{"mechanical": 2}, {"ebike": 1}],
    "num_docks_available": 10,
    "is_installed": 1,
    "is_renting": 1,
    "is_returning": 1,
    "last_reported": 1_700_000_000,
}


def test_status_valide_et_aplati() -> None:
    s = StationStatus.model_validate(GOOD_STATUS)
    assert (s.mechanical, s.ebike) == (2, 1)


@pytest.mark.parametrize(
    "patch",
    [
        {"num_bikes_available": -1},
        {"num_docks_available": "beaucoup"},
        {"station_id": None},
        {"num_bikes_available_types": [{"mechanical": 5}, {"ebike": 5}]},  # 10 != 3
    ],
)
def test_status_corrompu_rejete(patch: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        StationStatus.model_validate(GOOD_STATUS | patch)


def test_info_hors_ile_de_france_rejetee() -> None:
    with pytest.raises(ValidationError):
        StationInfo.model_validate({"station_id": 1, "name": "X", "lat": 0.0, "lon": 0.0, "capacity": 20})
