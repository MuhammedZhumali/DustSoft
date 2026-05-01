"""Arduino USB serial telemetry adapters.

The Arduino is used only as an ADC: it reads analog inputs and periodically
sends lines such as ``A0:123 A4:456`` over USB serial.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from .config import ArduinoSerialConfig, PressureInputConfig


class ArduinoSerialError(RuntimeError):
    """Raised when Arduino serial support is unavailable or telemetry is invalid."""


_READING_PATTERN = re.compile(r"\b(A\d+):(\d+)\b")


class ArduinoAnalogTransport:
    """Small pyserial wrapper that keeps the latest Arduino analog readings."""

    def __init__(self, config: ArduinoSerialConfig) -> None:
        try:
            import serial  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ArduinoSerialError(
                "pyserial is not installed; install it with '.venv/bin/python -m pip install pyserial'"
            ) from exc

        self.config = config
        self.serial = serial.Serial(
            port=config.port,
            baudrate=config.baudrate,
            timeout=config.timeout_seconds,
            write_timeout=config.timeout_seconds,
        )
        if config.startup_delay_seconds:
            time.sleep(config.startup_delay_seconds)
        self.latest: dict[str, int] = {}

    def read_latest(self) -> dict[str, int]:
        line = self.serial.readline().decode("ascii", errors="ignore").strip()
        if not line:
            raise ArduinoSerialError("No Arduino telemetry received")
        values = {channel: int(value) for channel, value in _READING_PATTERN.findall(line)}
        if not values:
            raise ArduinoSerialError(f"Invalid Arduino telemetry line: {line!r}")
        self.latest.update(values)
        return dict(self.latest)

    def close(self) -> None:
        self.serial.close()


@dataclass
class ArduinoAnalogPressureSensor:
    """Pressure-like sensor value derived from an Arduino analog channel."""

    transport: ArduinoAnalogTransport
    channel: str
    config: PressureInputConfig
    kind: str = "high"
    is_connected: bool = True
    _last_value: float | None = field(default=None, init=False)

    def read_pressure(self) -> float:
        try:
            readings = self.transport.read_latest()
            raw_value = readings[self.channel]
        except Exception:
            self.is_connected = False
            if self._last_value is not None:
                return self._last_value
            raise

        self.is_connected = True
        pressure = self._scale_raw(raw_value)
        self._last_value = pressure
        return pressure

    def _scale_raw(self, raw_value: int) -> float:
        raw = max(0, min(raw_value, 1023))
        if self.kind == "low":
            minimum = self.config.low_min_bar
            maximum = self.config.low_max_bar
        else:
            minimum = self.config.high_min_bar
            maximum = self.config.high_max_bar
        return minimum + (raw / 1023.0) * (maximum - minimum)
