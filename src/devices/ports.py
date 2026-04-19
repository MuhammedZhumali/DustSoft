"""Hardware abstraction ports.

Defines interfaces that decouple business logic from concrete device drivers.
"""

from __future__ import annotations

from typing import Protocol


class ActuatorPort(Protocol):
    """Command interface for an actuator device."""

    def start(self) -> None:
        """Start actuator operation."""

    def stop(self) -> None:
        """Stop actuator operation."""

    def set_power(self, value: float) -> None:
        """Set output level in the range accepted by implementation."""


class PressureSensorPort(Protocol):
    """Read-only interface for pressure sensing hardware."""

    def read_pressure(self) -> float:
        """Return current pressure value in bar."""


class ReferenceMeterPort(Protocol):
    """Reference meter used for calibration and validation routines."""

    def read_reference_value(self) -> float:
        """Return current reference measurement."""
