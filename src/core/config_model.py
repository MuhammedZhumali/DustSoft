"""Validated stand configuration model for DustSoft v1."""

from __future__ import annotations

import json
from dataclasses import InitVar, asdict, dataclass, field
from pathlib import Path


CONFIG_SCHEMA_VERSION = 1


@dataclass(slots=True)
class PressureConfig:
    minimum_bar: float = 0.0
    maximum_bar: float = 1.5
    low_minimum_bar: float = 0.0
    low_maximum_bar: float = 0.5


@dataclass(slots=True)
class InjectionProfile:
    name: str = "default"
    on_duration_seconds: float = 0.1
    off_duration_seconds: float = 5.0
    cycles: int | None = 1
    mode: str = "fixed"
    target_concentration_mg_m3: float | None = None
    cycle_seconds: float = 10.0
    duration_seconds: InitVar[float | None] = None
    interval_seconds: InitVar[float | None] = None
    count: InitVar[int | None] = None

    def __post_init__(
        self,
        duration_seconds: float | None,
        interval_seconds: float | None,
        count: int | None,
    ) -> None:
        if duration_seconds is not None:
            self.on_duration_seconds = duration_seconds
        if interval_seconds is not None:
            self.off_duration_seconds = interval_seconds
        if count is not None:
            self.cycles = count


@dataclass(slots=True)
class CalibrationConfig:
    duration_seconds: float = 60.0
    range_min: float = 0.0
    range_max: float = 100.0
    max_deviation_percent: float = 10.0
    control_points: list[float] = field(default_factory=lambda: [25.0, 50.0, 75.0, 100.0])
    calibrated_meter_ip: str = ""
    reference_archive_directory: str = ""


@dataclass(slots=True)
class StandConfig:
    schema_version: int = CONFIG_SCHEMA_VERSION
    pressure: PressureConfig = field(default_factory=PressureConfig)
    injection_profiles: dict[str, InjectionProfile] = field(
        default_factory=lambda: {"default": InjectionProfile()}
    )
    calibration: CalibrationConfig = field(default_factory=CalibrationConfig)

    def validate(self) -> None:
        if self.schema_version != CONFIG_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported config schema version {self.schema_version}; "
                f"expected {CONFIG_SCHEMA_VERSION}"
            )

        if self.pressure.minimum_bar < 0 or self.pressure.maximum_bar <= 0:
            raise ValueError("Pressure limits must be positive")
        if self.pressure.minimum_bar >= self.pressure.maximum_bar:
            raise ValueError("Pressure minimum must be lower than pressure maximum")
        if self.pressure.low_minimum_bar < 0 or self.pressure.low_maximum_bar <= 0:
            raise ValueError("Low-pressure limits must be positive")
        if self.pressure.low_minimum_bar >= self.pressure.low_maximum_bar:
            raise ValueError("Low-pressure minimum must be lower than maximum")

        if not self.injection_profiles:
            raise ValueError("At least one injection profile must be configured")

        for profile_name, profile in self.injection_profiles.items():
            if profile.on_duration_seconds <= 0:
                raise ValueError(f"Injection profile {profile_name} has invalid duration")
            if profile.off_duration_seconds <= 0:
                raise ValueError(f"Injection profile {profile_name} has invalid interval")
            if profile.cycles is not None and profile.cycles <= 0:
                raise ValueError(f"Injection profile {profile_name} must have positive cycles")
            if profile.mode not in {"fixed", "concentration"}:
                raise ValueError(f"Injection profile {profile_name} has unsupported mode")
            if profile.mode == "concentration" and profile.target_concentration_mg_m3 is None:
                raise ValueError(f"Injection profile {profile_name} requires target concentration")
            if profile.cycle_seconds <= 0:
                raise ValueError(f"Injection profile {profile_name} has invalid cycle duration")

        calibration = self.calibration
        if calibration.duration_seconds <= 0:
            raise ValueError("Calibration duration must be positive")
        if calibration.range_min < 0 or calibration.range_max <= calibration.range_min:
            raise ValueError("Calibration range must be non-negative and increasing")
        if calibration.max_deviation_percent <= 0:
            raise ValueError("Maximum deviation percent must be positive")
        if not calibration.control_points:
            raise ValueError("Calibration control points must not be empty")
        if any(point <= 0 for point in calibration.control_points):
            raise ValueError("Calibration control points must be positive")


class JsonStandConfigStorage:
    """Load and save stand configuration from JSON files."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> StandConfig:
        if not self.path.exists():
            config = StandConfig()
            config.validate()
            return config

        payload = json.loads(self.path.read_text(encoding="utf-8"))
        config = StandConfig(
            schema_version=int(payload.get("schema_version", CONFIG_SCHEMA_VERSION)),
            pressure=PressureConfig(**payload.get("pressure", {})),
            injection_profiles={
                name: _load_injection_profile(name, profile_payload)
                for name, profile_payload in payload.get("injection_profiles", {}).items()
            }
            or {"default": InjectionProfile()},
            calibration=CalibrationConfig(**payload.get("calibration", {})),
        )
        config.validate()
        return config


def _load_injection_profile(name: str, payload: dict[str, object]) -> InjectionProfile:
    migrated = dict(payload)
    if "duration_seconds" in migrated and "on_duration_seconds" not in migrated:
        migrated["on_duration_seconds"] = migrated.pop("duration_seconds")
    if "interval_seconds" in migrated and "off_duration_seconds" not in migrated:
        migrated["off_duration_seconds"] = migrated.pop("interval_seconds")
    if "count" in migrated and "cycles" not in migrated:
        migrated["cycles"] = migrated.pop("count")
    migrated.setdefault("name", name)
    return InjectionProfile(**migrated)

    def save(self, config: StandConfig) -> StandConfig:
        config.validate()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(asdict(config), ensure_ascii=True, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return config
