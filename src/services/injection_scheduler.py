"""Interval and concentration-controlled dust injection scheduler."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from core.state_machine import AppState
from storage import InjectionSettings


class InjectionSchedulerError(RuntimeError):
    """Raised when interval injection cannot be executed safely."""


@dataclass(slots=True)
class InjectionRunResult:
    completed_cycles: int
    interrupted: bool = False
    reason: str = ""


class InjectionScheduler:
    """Run valve pulses while respecting compressor and emergency conditions."""

    def __init__(
        self,
        app,
        *,
        sleep: Callable[[float], None] = time.sleep,
        should_stop: Callable[[], bool] | None = None,
    ) -> None:
        self.app = app
        self.sleep = sleep
        self.should_stop = should_stop or (lambda: False)
        self.current_cycle_id: int | None = None

    def run(self, settings: InjectionSettings | None = None) -> InjectionRunResult:
        settings = settings or self.app.injection_settings
        if settings.mode == "concentration":
            return self.run_to_target(settings)
        return self.run_fixed(settings)

    def run_fixed(self, settings: InjectionSettings) -> InjectionRunResult:
        completed = 0
        while settings.cycles is None or completed < settings.cycles:
            if self._must_stop():
                return InjectionRunResult(
                    completed_cycles=completed,
                    interrupted=True,
                    reason="stopped",
                )

            self.current_cycle_id = completed + 1
            self._open_valve()
            if self._sleep_interruptibly(settings.on_duration_seconds):
                self._close_valve()
                return InjectionRunResult(
                    completed_cycles=completed,
                    interrupted=True,
                    reason="stopped",
                )
            self._close_valve()
            completed += 1
            self.app.archive_measurement(injection_cycle_id=self.current_cycle_id)

            if settings.cycles is not None and completed >= settings.cycles:
                break
            if self._sleep_interruptibly(settings.off_duration_seconds):
                return InjectionRunResult(
                    completed_cycles=completed,
                    interrupted=True,
                    reason="stopped",
                )

        self.current_cycle_id = None
        return InjectionRunResult(completed_cycles=completed)

    def run_to_target(self, settings: InjectionSettings) -> InjectionRunResult:
        if settings.target_concentration_mg_m3 is None:
            raise InjectionSchedulerError("Target concentration is required")

        completed = 0
        while settings.cycles is None or completed < settings.cycles:
            if self._must_stop():
                return InjectionRunResult(
                    completed_cycles=completed,
                    interrupted=True,
                    reason="stopped",
                )

            telemetry = self.app.read_telemetry()
            concentration = telemetry.get("reference")
            self.current_cycle_id = completed + 1

            if concentration is None or concentration < settings.target_concentration_mg_m3:
                self._open_valve()
                if self._sleep_interruptibly(settings.on_duration_seconds):
                    self._close_valve()
                    return InjectionRunResult(
                        completed_cycles=completed,
                        interrupted=True,
                        reason="stopped",
                    )
                self._close_valve()
                completed += 1
                self.app.archive_measurement(injection_cycle_id=self.current_cycle_id)
            else:
                self._close_valve()
                if self._sleep_interruptibly(settings.off_duration_seconds):
                    return InjectionRunResult(
                        completed_cycles=completed,
                        interrupted=True,
                        reason="stopped",
                    )

        self.current_cycle_id = None
        return InjectionRunResult(completed_cycles=completed)

    def interrupt(self, reason: str = "operator_request") -> InjectionRunResult:
        self._close_valve()
        return InjectionRunResult(
            completed_cycles=self.current_cycle_id or 0,
            interrupted=True,
            reason=reason,
        )

    def _open_valve(self) -> None:
        if self.app.state == AppState.EMERGENCY:
            raise InjectionSchedulerError("Cannot inject during emergency")
        if not bool(getattr(self.app.compressor, "is_running", False)):
            raise InjectionSchedulerError("Compressor must be running before valve opens")
        self.app.manual_injection()

    def _close_valve(self) -> None:
        if bool(getattr(self.app.valve, "is_running", False)):
            self.app.complete_injection()

    def _must_stop(self) -> bool:
        return self.should_stop() or self.app.state == AppState.EMERGENCY

    def _sleep_interruptibly(self, duration_seconds: float) -> bool:
        remaining = max(0.0, duration_seconds)
        while remaining > 0:
            if self._must_stop():
                return True
            step = min(remaining, 0.1)
            self.sleep(step)
            remaining -= step
        return self._must_stop()
