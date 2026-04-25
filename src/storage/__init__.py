"""Persistent settings storage for DustSoft."""

from __future__ import annotations

import json
import csv
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


@dataclass(slots=True)
class InjectionSettings:
    on_duration_seconds: float = 1.0
    off_duration_seconds: float = 5.0
    cycles: int | None = 1
    mode: str = "fixed"
    target_concentration_mg_m3: float | None = None
    cycle_seconds: float = 5.0

    @property
    def duration_seconds(self) -> float:
        return self.on_duration_seconds

    @property
    def interval_seconds(self) -> float:
        return self.off_duration_seconds

    @property
    def count(self) -> int:
        return self.cycles or 0


@dataclass(slots=True)
class PressureSettings:
    minimum_bar: float = 0.0
    maximum_bar: float = 1.5
    low_minimum_bar: float = 0.0
    low_maximum_bar: float = 0.5


@dataclass(slots=True)
class SettingsBundle:
    injection: InjectionSettings = field(default_factory=InjectionSettings)
    pressure: PressureSettings = field(default_factory=PressureSettings)
    user_parameters: dict[str, Any] = field(default_factory=dict)


class JsonSettingsStorage:
    """Persist settings to a JSON file with atomic replacement."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> SettingsBundle:
        if not self.path.exists():
            return SettingsBundle()

        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return SettingsBundle(
            injection=InjectionSettings(**_migrate_injection(payload.get("injection", {}))),
            pressure=PressureSettings(**payload.get("pressure", {})),
            user_parameters=dict(payload.get("user_parameters", {})),
        )

    def save(self, settings: SettingsBundle) -> SettingsBundle:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(asdict(settings), ensure_ascii=True, indent=2, sort_keys=True)

        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            delete=False,
            dir=self.path.parent,
            prefix=f"{self.path.stem}-",
            suffix=".tmp",
        ) as handle:
            handle.write(serialized)
            temp_path = Path(handle.name)

        temp_path.replace(self.path)
        return settings


@dataclass(frozen=True, slots=True)
class MeasurementRecord:
    timestamp: str
    test_id: str
    pressure_high: float | None
    pressure_low: float | None
    dust_concentration: float | None
    compressor_state: bool
    valve_state: bool
    injection_cycle_id: int | None
    system_state: str
    error_code: str | None = None


class CsvMeasurementArchive:
    """Append measurement snapshots to a test CSV archive."""

    fieldnames = [
        "timestamp",
        "test_id",
        "pressure_high",
        "pressure_low",
        "dust_concentration",
        "compressor_state",
        "valve_state",
        "injection_cycle_id",
        "system_state",
        "error_code",
    ]

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)

    def append(self, record: MeasurementRecord) -> MeasurementRecord:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.path_for_test(record.test_id)
        is_new = not path.exists()
        with path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.fieldnames)
            if is_new:
                writer.writeheader()
            writer.writerow(asdict(record))
        return record

    def path_for_test(self, test_id: str) -> Path:
        return self.directory / f"{test_id}.csv"

    def list_tests(self) -> list[Path]:
        return sorted(self.directory.glob("*.csv"), reverse=True)

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()


def _migrate_injection(payload: dict[str, Any]) -> dict[str, Any]:
    migrated = dict(payload)
    if "duration_seconds" in migrated and "on_duration_seconds" not in migrated:
        migrated["on_duration_seconds"] = migrated.pop("duration_seconds")
    if "interval_seconds" in migrated and "off_duration_seconds" not in migrated:
        migrated["off_duration_seconds"] = migrated.pop("interval_seconds")
    if "count" in migrated and "cycles" not in migrated:
        migrated["cycles"] = migrated.pop("count")
    return migrated
