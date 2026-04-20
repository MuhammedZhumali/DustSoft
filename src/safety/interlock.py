"""Safety interlocks for dust injection commands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.state_machine import AppState


class InterlockError(RuntimeError):
    """Raised when a safety interlock blocks an operation."""


@dataclass(frozen=True)
class Interlock:
    """Validate conditions that must be true before dust injection."""

    pressure_min: float
    pressure_max: float

    def ensure_injection_allowed(
        self,
        *,
        state: AppState,
        pressure: float,
        devices: dict[str, Any],
    ) -> None:
        """Raise with a clear reason if injection is unsafe."""
        reasons = self.injection_blockers(
            state=state,
            pressure=pressure,
            devices=devices,
        )
        if reasons:
            raise InterlockError("; ".join(reasons))

    def ensure_devices_connected(self, devices: dict[str, Any]) -> None:
        """Raise if any required device reports lost communication."""
        disconnected = self.disconnected_devices(devices)
        if disconnected:
            raise InterlockError(
                "device communication lost: " + ", ".join(sorted(disconnected))
            )

    def injection_blockers(
        self,
        *,
        state: AppState,
        pressure: float,
        devices: dict[str, Any],
    ) -> list[str]:
        """Return all current safety blockers for an injection command."""
        blockers: list[str] = []

        if state == AppState.EMERGENCY:
            blockers.append("injection is forbidden during emergency")

        if not self.is_pressure_allowed(pressure):
            blockers.append(
                f"pressure {pressure:.3f} is outside allowed range "
                f"{self.pressure_min:.3f}..{self.pressure_max:.3f}"
            )

        disconnected = self.disconnected_devices(devices)
        if disconnected:
            blockers.append(
                "device communication lost: " + ", ".join(sorted(disconnected))
            )

        return blockers

    def is_pressure_allowed(self, pressure: float) -> bool:
        """Return True when pressure is inside the configured safe range."""
        return self.pressure_min <= pressure <= self.pressure_max

    def disconnected_devices(self, devices: dict[str, Any]) -> list[str]:
        """Return names of devices that currently report disconnected state."""
        return [
            name for name, device in devices.items() if not self.is_device_connected(device)
        ]

    @staticmethod
    def is_device_connected(device: Any) -> bool:
        """Best-effort connectivity check supported by mocks and real adapters."""
        for attr_name in ("is_connected", "connected", "connection_ok", "is_available"):
            if hasattr(device, attr_name):
                value = getattr(device, attr_name)
                return bool(value() if callable(value) else value)

        if hasattr(device, "ping"):
            return bool(device.ping())

        return True
