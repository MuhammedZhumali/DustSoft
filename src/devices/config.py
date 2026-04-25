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
    active_level: int = 0
    safe_level: int = 1


@dataclass(frozen=True, slots=True)
class GpioInputConfig:
    pin_bcm: int
    active_level: int = 0
    pull: str = "up"


@dataclass(frozen=True, slots=True)
class ReferenceMeterConfig:
    mode: str = "dusttrak_ethernet"
    host: str = "192.168.1.50"
    port: int = 3602
    command: str = "READ"
    url: str = "http://192.168.1.50/"
    timeout_seconds: float = 2.0
    analog_channel: int = 0
    analog_signal: str = "voltage_0_5"
    analog_min_value: float = 0.0
    analog_max_value: float = 100.0


@dataclass(frozen=True, slots=True)
class PressureInputConfig:
    mode: str = "mock"
    high_channel: int = 0
    low_channel: int = 1
    signal: str = "voltage_0_5"
    high_min_bar: float = 0.0
    high_max_bar: float = 1.5
    low_min_bar: float = 0.0
    low_max_bar: float = 0.5


@dataclass(frozen=True, slots=True)
class HardwareConfig:
    schema_version: int = HARDWARE_SCHEMA_VERSION
    mode: str = "mock"
    dry_run: bool = True
    notes: str = "Temporary pin mapping; verify against real hardware before live operation."
    compressor_enable: GpioOutputConfig = GpioOutputConfig(pin_bcm=17)
    injection_valve: GpioOutputConfig = GpioOutputConfig(pin_bcm=27)
    emergency_input: GpioInputConfig = GpioInputConfig(pin_bcm=22)
    pressure_inputs: PressureInputConfig = PressureInputConfig()
    reference_meter: ReferenceMeterConfig = ReferenceMeterConfig()

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "HardwareConfig":
        gpio = payload.get("gpio", {})
        pressure_inputs = payload.get("pressure_inputs", {})
        reference_meter = payload.get("reference_meter", {})
        config = cls(
            schema_version=int(payload.get("schema_version", HARDWARE_SCHEMA_VERSION)),
            mode=str(payload.get("mode", "mock")),
            dry_run=bool(payload.get("dry_run", True)),
            notes=str(payload.get("notes", "")),
            compressor_enable=GpioOutputConfig(
                **gpio.get(
                    "compressor_enable",
                    {"pin_bcm": 17, "active_level": 0, "safe_level": 1},
                )
            ),
            injection_valve=GpioOutputConfig(
                **gpio.get(
                    "injection_valve",
                    {"pin_bcm": 27, "active_level": 0, "safe_level": 1},
                )
            ),
            emergency_input=GpioInputConfig(**gpio.get("emergency_input", {"pin_bcm": 22})),
            pressure_inputs=PressureInputConfig(**pressure_inputs),
            reference_meter=ReferenceMeterConfig(**reference_meter),
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
            if output.active_level == output.safe_level:
                raise ValueError(f"{name} active and safe levels must differ")
        if self.emergency_input.pin_bcm < 0:
            raise ValueError("Emergency input pin must be a non-negative BCM number")
        if self.emergency_input.active_level not in {0, 1}:
            raise ValueError("Emergency input active level must be 0 or 1")
        if self.emergency_input.pull not in {"up", "down"}:
            raise ValueError("Emergency input pull must be 'up' or 'down'")
        if self.reference_meter.mode not in {
            "mock",
            "dusttrak_ethernet",
            "dusttrak_http",
            "dusttrak_analog",
        }:
            raise ValueError(
                "Reference meter mode must be 'mock', 'dusttrak_ethernet', "
                "'dusttrak_http', or 'dusttrak_analog'"
            )
        if self.reference_meter.port <= 0:
            raise ValueError("Reference meter port must be positive")
        if self.reference_meter.timeout_seconds <= 0:
            raise ValueError("Reference meter timeout must be positive")
        if self.reference_meter.analog_channel < 0:
            raise ValueError("Reference meter analog channel must be non-negative")
        if self.reference_meter.analog_signal not in {"voltage_0_5", "current_4_20"}:
            raise ValueError("Reference meter analog signal must be 'voltage_0_5' or 'current_4_20'")
        if self.reference_meter.analog_max_value <= self.reference_meter.analog_min_value:
            raise ValueError("Reference meter analog range must be increasing")
        if self.pressure_inputs.mode not in {"mock", "analog_adc", "i2c", "spi"}:
            raise ValueError("Pressure input mode must be 'mock', 'analog_adc', 'i2c', or 'spi'")
        if self.pressure_inputs.high_channel < 0 or self.pressure_inputs.low_channel < 0:
            raise ValueError("Pressure input channels must be non-negative")
        if self.pressure_inputs.signal not in {"voltage_0_5", "current_4_20"}:
            raise ValueError("Pressure input signal must be 'voltage_0_5' or 'current_4_20'")

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
