"""High-level DustSoft process controller."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from core.state_machine import AppState, Operation, StateMachine
from devices.ports import ActuatorPort, PressureSensorPort
from safety.interlock import Interlock


LOGGER = logging.getLogger(__name__)


@dataclass
class Controller:
    """Execute operator commands with state and safety checks."""

    compressor: ActuatorPort
    valve: ActuatorPort
    pressure_sensor: PressureSensorPort
    pressure_min: float = 0.8
    pressure_max: float = 1.5
    logger: logging.Logger = LOGGER
    state_machine: StateMachine = field(default_factory=StateMachine)
    last_pressure: float | None = None

    @property
    def state(self) -> AppState:
        """Current controller state."""
        return self.state_machine.state

    def start(self) -> AppState:
        """Start normal operation."""
        next_state = self.state_machine.apply(Operation.START)
        self.compressor.start()
        self.logger.info("Controller started")
        return next_state

    def stop(self) -> AppState:
        """Stop normal operation and leave devices in a safe idle state."""
        next_state = self.state_machine.apply(Operation.STOP)
        self._safe_stop_devices()
        self.logger.info("Controller stopped")
        return next_state

    def manual_injection(self) -> AppState:
        """Perform a manual dust injection after all interlocks pass."""
        self.state_machine.assert_operation_allowed(Operation.MANUAL_INJECTION)
        interlock = self._interlock()
        interlock.ensure_devices_connected(self._devices())
        pressure = self.pressure_sensor.read_pressure()
        self.last_pressure = pressure
        interlock.ensure_injection_allowed(
            state=self.state,
            pressure=pressure,
            devices=self._devices(),
        )

        next_state = self.state_machine.apply(Operation.MANUAL_INJECTION)
        self.compressor.start()
        self.valve.start()
        self.logger.info("Manual injection started at pressure %.3f", pressure)
        return next_state

    def emergency_stop(self, source: str) -> AppState:
        """Enter emergency state and force devices to a safe state."""
        self._safe_stop_devices()
        next_state = self.state_machine.apply(Operation.EMERGENCY_STOP)
        self.logger.critical("Emergency stop from %s", source)
        return next_state

    def reset_emergency(self) -> AppState:
        """Reset an emergency after external causes have been cleared."""
        next_state = self.state_machine.apply(Operation.RESET_EMERGENCY)
        self._safe_stop_devices()
        self.logger.info("Emergency reset")
        return next_state

    def _interlock(self) -> Interlock:
        return Interlock(
            pressure_min=self.pressure_min,
            pressure_max=self.pressure_max,
        )

    def _devices(self) -> dict[str, object]:
        return {
            "compressor": self.compressor,
            "valve": self.valve,
            "pressure_sensor": self.pressure_sensor,
        }

    def _safe_stop_devices(self) -> None:
        """Close the injection path and stop pressure generation."""
        for name, stop in (
            ("valve", self.valve.stop),
            ("compressor", self.compressor.stop),
        ):
            try:
                stop()
            except Exception:
                self.logger.exception("Failed to stop %s during safe shutdown", name)
