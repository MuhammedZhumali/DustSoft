"""Technological cycle orchestration and pulse planning."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from core.config_model import CalibrationConfig, InjectionProfile

if TYPE_CHECKING:
    from core.application import Application


class CycleStage(str, Enum):
    IDLE = "IDLE"
    PREPARING = "PREPARING"
    BUILD_UP = "BUILD_UP"
    CONTROL_POINT = "CONTROL_POINT"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class PulseCommand:
    index: int
    at_seconds: float
    duration_seconds: float


@dataclass(slots=True)
class TechnologyCycleState:
    stage: CycleStage = CycleStage.IDLE
    profile_name: str | None = None
    current_control_point: float | None = None
    completed_pulses: int = 0
    warnings: list[str] = field(default_factory=list)


class PulsePlanner:
    """Convert injection profiles into a deterministic pulse plan."""

    def plan(self, profile: InjectionProfile) -> list[PulseCommand]:
        return [
            PulseCommand(
                index=index + 1,
                at_seconds=index * profile.interval_seconds,
                duration_seconds=profile.duration_seconds,
            )
            for index in range(profile.count)
        ]


class TechnologyCycleService:
    """Run the simplified technological cycle over the application service layer."""

    def __init__(self, app: Application, *, planner: PulsePlanner | None = None) -> None:
        self.app = app
        self.planner = planner or PulsePlanner()
        self.state = TechnologyCycleState()

    def start_cycle(self, profile_name: str = "default") -> TechnologyCycleState:
        profile = self.app.stand_config.injection_profiles[profile_name]
        calibration = self.app.stand_config.calibration
        self.state = TechnologyCycleState(
            stage=CycleStage.PREPARING,
            profile_name=profile_name,
        )
        self.app.start()
        self.state.stage = CycleStage.BUILD_UP

        for pulse in self.planner.plan(profile):
            self.app.manual_injection()
            self.app.complete_injection()
            self.state.completed_pulses = pulse.index

        for control_point in calibration.control_points:
            self.state.stage = CycleStage.CONTROL_POINT
            self.state.current_control_point = control_point
            self.app.journal.log_event(
                event_type="cycle_control_point",
                description=f"Reached control point {control_point:.3f}",
                system_snapshot=self.app.snapshot_state(),
            )

        self.app.stop()
        self.state.stage = CycleStage.COMPLETED
        return self.state

    def abort_cycle(self, reason: str) -> TechnologyCycleState:
        self.app.stop()
        self.state.stage = CycleStage.ABORTED
        self.state.warnings.append(reason)
        return self.state

    def fail_cycle(self, reason: str) -> TechnologyCycleState:
        self.app.emergency_stop(f"cycle_failure:{reason}")
        self.state.stage = CycleStage.FAILED
        self.state.warnings.append(reason)
        return self.state
