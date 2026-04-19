"""Application orchestration layer."""

from __future__ import annotations

from dataclasses import dataclass

from core.state_machine import AppState
from devices.ports import ActuatorPort, PressureSensorPort, ReferenceMeterPort


@dataclass
class Application:
    actuator: ActuatorPort
    pressure_sensor: PressureSensorPort
    reference_meter: ReferenceMeterPort
    state: AppState = AppState.IDLE

    def bootstrap(self) -> None:
        """Prepare dependencies before normal operation."""
        self.state = AppState.READY

    def run_once(self) -> dict[str, float | str]:
        """Run one cycle of application logic for smoke testing."""
        self.state = AppState.RUNNING
        self.actuator.start()
        self.actuator.set_power(0.5)

        pressure = self.pressure_sensor.read_pressure()
        reference = self.reference_meter.read_reference_value()

        self.actuator.stop()
        self.state = AppState.STOPPED
        return {
            "state": self.state.value,
            "pressure": pressure,
            "reference": reference,
        }
