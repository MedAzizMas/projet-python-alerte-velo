"""Schémas Pydantic : toute station qui ne respecte pas ces règles est rejetée."""

from typing import Any

from pydantic import BaseModel, Field, model_validator

# Emprise large de l'Île-de-France
LAT_MIN, LAT_MAX = 48.1, 49.3
LON_MIN, LON_MAX = 1.4, 3.6


class StationStatus(BaseModel):
    station_id: int
    num_bikes_available: int = Field(ge=0)
    num_docks_available: int = Field(ge=0)
    mechanical: int = Field(ge=0)
    ebike: int = Field(ge=0)
    is_installed: bool
    is_renting: bool
    is_returning: bool
    last_reported: int = Field(gt=0)

    @model_validator(mode="before")
    @classmethod
    def flatten_bike_types(cls, data: Any) -> Any:
        """Aplatit [{"mechanical": n}, {"ebike": m}] en deux champs simples."""
        if isinstance(data, dict) and "num_bikes_available_types" in data:
            data = dict(data)
            types: dict[str, Any] = {}
            for item in data.pop("num_bikes_available_types") or []:
                types.update(item)
            data.setdefault("mechanical", types.get("mechanical", 0))
            data.setdefault("ebike", types.get("ebike", 0))
        return data

    @model_validator(mode="after")
    def bike_types_consistent(self) -> "StationStatus":
        if self.mechanical + self.ebike != self.num_bikes_available:
            raise ValueError("mécaniques + électriques != total vélos")
        return self


class StationInfo(BaseModel):
    station_id: int
    name: str = Field(min_length=1)
    lat: float = Field(ge=LAT_MIN, le=LAT_MAX)
    lon: float = Field(ge=LON_MIN, le=LON_MAX)
    capacity: int = Field(ge=0)
