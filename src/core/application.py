"""Application orchestration layer."""

from __future__ import annotations

from dataclasses import dataclass

from core.controller import Controller
from core.state_machine import AppState
from devices.ports import ActuatorPort, PressureSensorPort, ReferenceMeterPort


@dataclass
class Application:
    compressor: ActuatorPort
    valve: ActuatorPort
    pressure_sensor: PressureSensorPort
    reference_meter: ReferenceMeterPort
    pressure_min: float = 0.8
    pressure_max: float = 1.5

    def __post_init__(self) -> None:
        self.controller = Controller(
            compressor=self.compressor,
            valve=self.valve,
            pressure_sensor=self.pressure_sensor,
            pressure_min=self.pressure_min,
            pressure_max=self.pressure_max,
        )

    @property
    def state(self) -> AppState:
        """Current application state."""
        return self.controller.state

    def bootstrap(self) -> None:
        """Prepare dependencies before normal operation."""
        self.controller.state_machine.transition_to(AppState.READY)

    def run_once(self) -> dict[str, float | str]:
        """Run one cycle of application logic for smoke testing."""
        self.controller.start()
        self.controller.manual_injection()
        reference = self.reference_meter.read_reference_value()
        self.controller.stop()

        return {
            "state": self.state.value,
            "pressure": self.controller.last_pressure or 0.0,
            "reference": reference,
        }
