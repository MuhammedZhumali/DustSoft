"""Mock implementations of hardware ports for local development."""

from __future__ import annotations

from dataclasses import dataclass, field

from .ports import ActuatorPort, PressureSensorPort, ReferenceMeterPort


@dataclass
class MockActuator(ActuatorPort):
    is_running: bool = False
    power: float = 0.0
    is_connected: bool = True

    def start(self) -> None:
        self.is_running = True

    def stop(self) -> None:
        self.is_running = False
        self.power = 0.0

    def set_power(self, value: float) -> None:
        self.power = max(0.0, min(value, 1.0))


@dataclass
class MockPressureSensor(PressureSensorPort):
    pressure_sequence: list[float] = field(default_factory=lambda: [1.0, 1.1, 1.2])
    is_connected: bool = True
    _index: int = 0

    def read_pressure(self) -> float:
        if not self.pressure_sequence:
            return 0.0
        value = self.pressure_sequence[self._index]
        self._index = (self._index + 1) % len(self.pressure_sequence)
        return value


@dataclass
class MockReferenceMeter(ReferenceMeterPort):
    value: float = 1.0
    is_connected: bool = True

    def read_reference_value(self) -> float:
        return self.value
