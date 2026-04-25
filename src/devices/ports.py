"""Hardware abstraction ports.

Defines interfaces that decouple business logic from concrete device drivers.
"""

from __future__ import annotations

from typing import Protocol


class ActuatorPort(Protocol):
    """Command interface for an actuator device."""

    is_connected: bool

    def start(self) -> None:
        """Start actuator operation."""

    def stop(self) -> None:
        """Stop actuator operation."""

    def set_power(self, value: float) -> None:
        """Set output level in the range accepted by implementation."""


class PressureSensorPort(Protocol):
    """Read-only interface for pressure sensing hardware."""

    is_connected: bool

    def read_pressure(self) -> float:
        """Return current pressure value in bar."""


class DualPressureSensorPort(Protocol):
    """Read both chamber pressure channels in bar."""

    is_connected: bool

    def read_pressure_high(self) -> float:
        """Return high-pressure channel D1 in bar."""

    def read_pressure_low(self) -> float:
        """Return low-pressure channel D2 in bar."""


class ReferenceMeterPort(Protocol):
    """Reference meter used for calibration and validation routines."""

    is_connected: bool

    def read_reference_value(self) -> float:
        """Return current reference measurement in mg/m3."""


class EmergencyButtonPort(Protocol):
    """Read an emergency button or hardware interlock input."""

    is_connected: bool

    def is_pressed(self) -> bool:
        """Return True when the emergency input is active."""
