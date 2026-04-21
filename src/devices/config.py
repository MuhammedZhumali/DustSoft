"""Hardware configuration for mock and Raspberry Pi runtime modes."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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
    mode: str = "mock"
    compressor_enable: GpioOutputConfig = GpioOutputConfig(pin_bcm=17)
    injection_valve: GpioOutputConfig = GpioOutputConfig(pin_bcm=27)
    emergency_input: GpioInputConfig = GpioInputConfig(pin_bcm=22)

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "HardwareConfig":
        gpio = payload.get("gpio", {})
        return cls(
            mode=str(payload.get("mode", "mock")),
            compressor_enable=GpioOutputConfig(**gpio.get("compressor_enable", {"pin_bcm": 17})),
            injection_valve=GpioOutputConfig(**gpio.get("injection_valve", {"pin_bcm": 27})),
            emergency_input=GpioInputConfig(**gpio.get("emergency_input", {"pin_bcm": 22})),
        )


def load_hardware_config(path: str | Path) -> HardwareConfig:
    config_path = Path(path)
    if not config_path.exists():
        return HardwareConfig()
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    return HardwareConfig.from_mapping(payload)
