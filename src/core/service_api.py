"""Internal application API for UI, remote services, and future integrations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.cycle import TechnologyCycleService


@dataclass(frozen=True, slots=True)
class ApiEvent:
    name: str
    payload: dict[str, Any]


class ApplicationApi:
    """Facade exposing commands and event snapshots without binding to transport."""

    def __init__(self, app, *, cycle_service: TechnologyCycleService | None = None) -> None:
        self.app = app
        self.cycle_service = cycle_service or TechnologyCycleService(app)
        self._events: list[ApiEvent] = []

    def start_cycle(self, profile_name: str = "default") -> dict[str, Any]:
        state = self.cycle_service.start_cycle(profile_name)
        self._emit(
            "cycle_state_changed",
            {
                "stage": state.stage.value,
                "current_control_point": state.current_control_point,
                "completed_pulses": state.completed_pulses,
            },
        )
        return self.get_telemetry()

    def stop_cycle(self, reason: str = "operator_request") -> dict[str, Any]:
        state = self.cycle_service.abort_cycle(reason)
        self._emit("warning", {"message": reason, "stage": state.stage.value})
        return self.get_telemetry()

    def manual_injection(self) -> dict[str, Any]:
        self.app.manual_injection()
        self.app.complete_injection()
        telemetry = self.get_telemetry()
        self._emit("telemetry", telemetry)
        return telemetry

    def emergency_stop(self, source: str = "api") -> dict[str, Any]:
        self.app.emergency_stop(source)
        telemetry = self.get_telemetry()
        self._emit("warning", {"message": "Emergency stop triggered", "source": source})
        return telemetry

    def get_telemetry(self) -> dict[str, Any]:
        telemetry = self.app.read_telemetry()
        telemetry["cycle"] = {
            "stage": self.cycle_service.state.stage.value,
            "current_control_point": self.cycle_service.state.current_control_point,
            "completed_pulses": self.cycle_service.state.completed_pulses,
            "warnings": list(self.cycle_service.state.warnings),
        }
        return telemetry

    def poll_events(self) -> list[ApiEvent]:
        events = list(self._events)
        self._events.clear()
        return events

    def _emit(self, name: str, payload: dict[str, Any]) -> None:
        self._events.append(ApiEvent(name=name, payload=payload))
