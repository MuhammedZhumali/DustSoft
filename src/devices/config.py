"""Hardware configuration for Raspberry Pi relays and Arduino ADC telemetry."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

HARDWARE_SCHEMA_VERSION = 1


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
    high_channel: int = 0
    low_channel: int = 1
    signal: str = "voltage_0_5"
    high_min_bar: float = 0.0
    high_max_bar: float = 1.5
    low_min_bar: float = 0.0
    low_max_bar: float = 0.5


@dataclass(frozen=True, slots=True)
class ArduinoSerialConfig:
    port: str = "/dev/ttyACM0"
    baudrate: int = 9600
    timeout_seconds: float = 1.0
    startup_delay_seconds: float = 2.0
    main_channel: str = "A0"
    second_channel: str = "A4"


@dataclass(frozen=True, slots=True)
class RelayOutputConfig:
    pin_bcm: int
    active_level: int = 1
    safe_level: int = 0


@dataclass(frozen=True, slots=True)
class RelayOutputsConfig:
    compressor: RelayOutputConfig = RelayOutputConfig(pin_bcm=17)
    valve: RelayOutputConfig = RelayOutputConfig(pin_bcm=27)


@dataclass(frozen=True, slots=True)
class HardwareConfig:
    schema_version: int = HARDWARE_SCHEMA_VERSION
    notes: str = "Raspberry Pi GPIO controls relays; Arduino sends analog sensor values over USB."
    arduino_serial: ArduinoSerialConfig = ArduinoSerialConfig()
    relay_outputs: RelayOutputsConfig = RelayOutputsConfig()
    pressure_inputs: PressureInputConfig = PressureInputConfig()
    reference_meter: ReferenceMeterConfig = ReferenceMeterConfig()

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "HardwareConfig":
        arduino_serial = payload.get("arduino_serial", {})
        relay_outputs = payload.get("relay_outputs", {})
        pressure_inputs = payload.get("pressure_inputs", {})
        reference_meter = payload.get("reference_meter", {})
        config = cls(
            schema_version=int(payload.get("schema_version", HARDWARE_SCHEMA_VERSION)),
            notes=str(payload.get("notes", "")),
            arduino_serial=ArduinoSerialConfig(**arduino_serial),
            relay_outputs=RelayOutputsConfig(
                compressor=RelayOutputConfig(
                    **relay_outputs.get("compressor", {"pin_bcm": 17})
                ),
                valve=RelayOutputConfig(**relay_outputs.get("valve", {"pin_bcm": 27})),
            ),
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
        if not self.arduino_serial.port.strip():
            raise ValueError("Arduino serial port must not be empty")
        if self.arduino_serial.baudrate <= 0:
            raise ValueError("Arduino baudrate must be positive")
        if self.arduino_serial.timeout_seconds <= 0:
            raise ValueError("Arduino timeout must be positive")
        if self.arduino_serial.startup_delay_seconds < 0:
            raise ValueError("Arduino startup delay must be non-negative")
        for name, output in (
            ("compressor", self.relay_outputs.compressor),
            ("valve", self.relay_outputs.valve),
        ):
            if output.pin_bcm < 0:
                raise ValueError(f"{name} relay pin must be a non-negative BCM number")
            if output.active_level not in {0, 1} or output.safe_level not in {0, 1}:
                raise ValueError(f"{name} relay levels must be 0 or 1")
            if output.active_level == output.safe_level:
                raise ValueError(f"{name} relay active and safe levels must differ")
        if self.reference_meter.mode not in {"dusttrak_ethernet", "dusttrak_http", "dusttrak_analog"}:
            raise ValueError(
                "Reference meter mode must be 'dusttrak_ethernet', 'dusttrak_http', "
                "or 'dusttrak_analog'"
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
        if self.pressure_inputs.high_channel < 0 or self.pressure_inputs.low_channel < 0:
            raise ValueError("Pressure input channels must be non-negative")
        if self.pressure_inputs.signal not in {"voltage_0_5", "current_4_20"}:
            raise ValueError("Pressure input signal must be 'voltage_0_5' or 'current_4_20'")

    def to_mapping(self) -> dict[str, Any]:
        return asdict(self)


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
