"""GTFS-ready adapter contract without claiming that a feed is loaded."""

from __future__ import annotations

from typing import Protocol

import pandas as pd

GTFS_REQUIRED_COLUMNS = {
    "stops": frozenset({"stop_id", "stop_name", "stop_lat", "stop_lon"}),
    "routes": frozenset({"route_id", "route_short_name", "route_long_name", "route_type"}),
    "trips": frozenset({"route_id", "service_id", "trip_id"}),
    "stop_times": frozenset(
        {"trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"}
    ),
    "calendar": frozenset(
        {
            "service_id",
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
            "start_date",
            "end_date",
        }
    ),
    "calendar_dates": frozenset({"service_id", "date", "exception_type"}),
}


class GtfsFeedAdapter(Protocol):
    @property
    def source_identifier(self) -> str: ...

    def table(self, name: str) -> pd.DataFrame: ...


def _seconds(value: str) -> int:
    parts = value.split(":")
    if len(parts) != 3:
        raise ValueError(f"Invalid GTFS time: {value}")
    hour, minute, second = (int(part) for part in parts)
    if hour < 0 or not 0 <= minute < 60 or not 0 <= second < 60:
        raise ValueError(f"Invalid GTFS time: {value}")
    return hour * 3600 + minute * 60 + second


def validate_gtfs_adapter(adapter: GtfsFeedAdapter) -> dict[str, int]:
    """Validate the minimum future feed boundary and referential integrity."""

    if not adapter.source_identifier.strip():
        raise ValueError("GTFS adapter requires a source identifier")
    tables = {name: adapter.table(name).copy() for name in GTFS_REQUIRED_COLUMNS}
    for name, required in GTFS_REQUIRED_COLUMNS.items():
        missing = required - set(tables[name].columns)
        if missing:
            raise ValueError(f"GTFS {name} is missing columns: {sorted(missing)}")

    for name, key in (
        ("stops", "stop_id"),
        ("routes", "route_id"),
        ("trips", "trip_id"),
        ("calendar", "service_id"),
    ):
        values = tables[name][key].astype(str)
        if values.eq("").any() or values.duplicated().any():
            raise ValueError(f"GTFS {name}.{key} must be non-empty and unique")
    if (
        not tables["calendar_dates"].empty
        and tables["calendar_dates"].duplicated(["service_id", "date"]).any()
    ):
        raise ValueError("GTFS calendar_dates service/date must be unique")

    stop_ids = set(tables["stops"].stop_id.astype(str))
    route_ids = set(tables["routes"].route_id.astype(str))
    trip_ids = set(tables["trips"].trip_id.astype(str))
    service_ids = set(tables["calendar"].service_id.astype(str)) | set(
        tables["calendar_dates"].service_id.astype(str)
    )
    if not set(tables["trips"].route_id.astype(str)) <= route_ids:
        raise ValueError("GTFS trips references an unknown route")
    if not set(tables["trips"].service_id.astype(str)) <= service_ids:
        raise ValueError("GTFS trips references an unknown service")
    if not set(tables["stop_times"].trip_id.astype(str)) <= trip_ids:
        raise ValueError("GTFS stop_times references an unknown trip")
    if not set(tables["stop_times"].stop_id.astype(str)) <= stop_ids:
        raise ValueError("GTFS stop_times references an unknown stop")

    latitudes = pd.to_numeric(tables["stops"].stop_lat, errors="coerce")
    longitudes = pd.to_numeric(tables["stops"].stop_lon, errors="coerce")
    if latitudes.isna().any() or not latitudes.between(-90, 90).all():
        raise ValueError("GTFS stop latitude is invalid")
    if longitudes.isna().any() or not longitudes.between(-180, 180).all():
        raise ValueError("GTFS stop longitude is invalid")

    sequences = pd.to_numeric(tables["stop_times"].stop_sequence, errors="coerce")
    if sequences.isna().any() or sequences.lt(0).any() or (sequences % 1).ne(0).any():
        raise ValueError("GTFS stop_sequence must be a non-negative integer")
    tables["stop_times"]["stop_sequence"] = sequences.astype(int)
    if tables["stop_times"].duplicated(["trip_id", "stop_sequence"]).any():
        raise ValueError("GTFS stop_sequence must be unique within a trip")
    stop_times = tables["stop_times"].sort_values(["trip_id", "stop_sequence"])
    for _, group in stop_times.groupby("trip_id"):
        previous = -1
        for row in group.itertuples(index=False):
            arrival = _seconds(str(row.arrival_time))
            departure = _seconds(str(row.departure_time))
            if arrival < previous or departure < arrival:
                raise ValueError("GTFS stop times must be non-decreasing within a trip")
            previous = departure
    return {name: len(table) for name, table in tables.items()}
