"""Driver contracts for the DustSoft hardware stack."""

from __future__ import annotations

from typing import Protocol


class CompressorDriver(Protocol):
    is_connected: bool
    is_running: bool

    def start(self) -> None:
        """Start compressor operation."""

    def stop(self) -> None:
        """Stop compressor operation."""

    def set_power(self, value: float) -> None:
        """Adjust output power when supported by implementation."""


class InjectionValveDriver(Protocol):
    is_connected: bool
    is_running: bool

    def start(self) -> None:
        """Open the injection valve."""

    def stop(self) -> None:
        """Close the injection valve."""

    def set_power(self, value: float) -> None:
        """Adjust valve power or duty cycle when supported."""


class PressureDriver(Protocol):
    is_connected: bool

    def read_pressure(self) -> float:
        """Return current pressure in bar."""


class ReferenceMeterDriver(Protocol):
    is_connected: bool

    def read_reference_value(self) -> float:
        """Return current reference measurement."""


class CalibratedMeterDriver(Protocol):
    is_connected: bool

    def read_calibrated_value(self) -> float:
        """Return current value from the meter under calibration."""
