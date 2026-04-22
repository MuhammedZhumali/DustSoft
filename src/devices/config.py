"""Hardware configuration for mock and Raspberry Pi runtime modes."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

HARDWARE_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class GpioOutputConfig:
    pin_bcm: int
    active_level: int = 1
    safe_level: int = 0


@dataclass(frozen=True, slots=True)
class GpioInputConfig:
    pin_bcm: int
    active_level: int = 0
    pull: str = "up"


@dataclass(frozen=True, slots=True)
class HardwareConfig:
    schema_version: int = HARDWARE_SCHEMA_VERSION
    mode: str = "mock"
    dry_run: bool = True
    notes: str = "Temporary pin mapping; verify against real hardware before live operation."
    compressor_enable: GpioOutputConfig = GpioOutputConfig(pin_bcm=17)
    injection_valve: GpioOutputConfig = GpioOutputConfig(pin_bcm=27)
    emergency_input: GpioInputConfig = GpioInputConfig(pin_bcm=22)

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "HardwareConfig":
        gpio = payload.get("gpio", {})
        config = cls(
            schema_version=int(payload.get("schema_version", HARDWARE_SCHEMA_VERSION)),
            mode=str(payload.get("mode", "mock")),
            dry_run=bool(payload.get("dry_run", True)),
            notes=str(payload.get("notes", "")),
            compressor_enable=GpioOutputConfig(**gpio.get("compressor_enable", {"pin_bcm": 17})),
            injection_valve=GpioOutputConfig(**gpio.get("injection_valve", {"pin_bcm": 27})),
            emergency_input=GpioInputConfig(**gpio.get("emergency_input", {"pin_bcm": 22})),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if self.schema_version != HARDWARE_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported hardware schema version {self.schema_version}; "
                f"expected {HARDWARE_SCHEMA_VERSION}"
            )
        if self.mode not in {"mock", "raspberry_pi"}:
            raise ValueError("Hardware mode must be 'mock' or 'raspberry_pi'")
        for name, output in (
            ("compressor_enable", self.compressor_enable),
            ("injection_valve", self.injection_valve),
        ):
            if output.pin_bcm < 0:
                raise ValueError(f"{name} pin must be a non-negative BCM number")
            if output.active_level not in {0, 1} or output.safe_level not in {0, 1}:
                raise ValueError(f"{name} levels must be 0 or 1")
        if self.emergency_input.pin_bcm < 0:
            raise ValueError("Emergency input pin must be a non-negative BCM number")
        if self.emergency_input.active_level not in {0, 1}:
            raise ValueError("Emergency input active level must be 0 or 1")
        if self.emergency_input.pull not in {"up", "down"}:
            raise ValueError("Emergency input pull must be 'up' or 'down'")

    def to_mapping(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["gpio"] = {
            "compressor_enable": payload.pop("compressor_enable"),
            "injection_valve": payload.pop("injection_valve"),
            "emergency_input": payload.pop("emergency_input"),
        }
        return payload


def load_hardware_config(path: str | Path) -> HardwareConfig:
    config_path = Path(path)
    if not config_path.exists():
        return HardwareConfig()
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    return HardwareConfig.from_mapping(payload)


def save_hardware_config(path: str | Path, config: HardwareConfig) -> HardwareConfig:
    config.validate()
    config_path = Path(path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(config.to_mapping(), ensure_ascii=True, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return config
