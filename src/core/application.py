"""Application orchestration layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from core.controller import Controller
from core.state_machine import AppState
from logging_system import JournalEntry, JsonLineJournal, JournalService
from devices.ports import ActuatorPort, PressureSensorPort, ReferenceMeterPort
from remote import RemoteAccessPolicy, RemoteService
from storage import (
    InjectionSettings,
    JsonSettingsStorage,
    PressureSettings,
    SettingsBundle,
)


def _resolve_version() -> str:
    try:
        return version("dustsoft")
    except PackageNotFoundError:
        return "0.1.0-dev"


@dataclass
class Application:
    compressor: ActuatorPort
    valve: ActuatorPort
    pressure_sensor: PressureSensorPort
    reference_meter: ReferenceMeterPort
    pressure_min: float = 0.8
    pressure_max: float = 1.5
    data_dir: Path = Path("data")
    settings_storage: JsonSettingsStorage | None = None
    journal: JournalService | None = None
    remote_access_policy: RemoteAccessPolicy = field(default_factory=RemoteAccessPolicy)

    def __post_init__(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.software_version = _resolve_version()
        self.settings_storage = self.settings_storage or JsonSettingsStorage(
            self.data_dir / "settings.json"
        )
        self.journal = self.journal or JournalService(
            event_journal=JsonLineJournal(self.data_dir / "events.log.jsonl"),
            alarm_journal=JsonLineJournal(self.data_dir / "alarms.log.jsonl"),
            technical_journal=JsonLineJournal(self.data_dir / "technical.log.jsonl"),
        )
        storage_exists = self.settings_storage.path.exists()
        self.settings = self.settings_storage.load()
        if not storage_exists:
            self.settings.pressure = PressureSettings(
                minimum_bar=self.pressure_min,
                maximum_bar=self.pressure_max,
            )
        self.remote_link_active = True
        self.controller = Controller(
            compressor=self.compressor,
            valve=self.valve,
            pressure_sensor=self.pressure_sensor,
            pressure_min=self.settings.pressure.minimum_bar,
            pressure_max=self.settings.pressure.maximum_bar,
        )
        self.injection_settings = self.settings.injection
        self.user_parameters = dict(self.settings.user_parameters)
        self.remote_service = RemoteService(self, access_policy=self.remote_access_policy)

    @property
    def state(self) -> AppState:
        """Current application state."""
        return self.controller.state

    def bootstrap(self) -> None:
        """Prepare dependencies before normal operation."""
        self.controller.state_machine.transition_to(AppState.READY)
        self.journal.log_technical(
            event_type="application_bootstrap",
            description="Application bootstrapped and restored persisted settings",
            system_snapshot=self.snapshot_state(),
        )

    def run_once(self) -> dict[str, float | str]:
        """Run one cycle of application logic for smoke testing."""
        self.start()
        self.manual_injection()
        reference = self.reference_meter.read_reference_value()
        self.stop()

        return {
            "state": self.state.value,
            "pressure": self.controller.last_pressure or 0.0,
            "reference": reference,
        }

    def start(self) -> AppState:
        next_state = self.controller.start()
        self.journal.log_event(
            event_type="start",
            description="Local start command executed",
            system_snapshot=self.snapshot_state(),
        )
        return next_state

    def stop(self) -> AppState:
        next_state = self.controller.stop()
        self.journal.log_event(
            event_type="stop",
            description="Local stop command executed",
            system_snapshot=self.snapshot_state(),
        )
        return next_state

    def manual_injection(self) -> AppState:
        next_state = self.controller.manual_injection()
        self.journal.log_event(
            event_type="manual_injection",
            description="Manual injection executed",
            system_snapshot=self.snapshot_state(),
        )
        return next_state

    def emergency_stop(self, source: str) -> AppState:
        next_state = self.controller.emergency_stop(source)
        self.journal.log_alarm(
            event_type="emergency_stop",
            description=f"Emergency stop triggered by {source}",
            system_snapshot=self.snapshot_state(),
        )
        return next_state

    def reset_emergency(self) -> AppState:
        next_state = self.controller.reset_emergency()
        self.journal.log_event(
            event_type="reset_emergency",
            description="Emergency state reset locally",
            system_snapshot=self.snapshot_state(),
        )
        return next_state

    def configure_injection(self, **changes: Any) -> InjectionSettings:
        duration_seconds = changes.get(
            "duration_seconds", self.injection_settings.duration_seconds
        )
        interval_seconds = changes.get(
            "interval_seconds", self.injection_settings.interval_seconds
        )
        count = changes.get("count", self.injection_settings.count)
        cycle_seconds = changes.get("cycle_seconds", self.injection_settings.cycle_seconds)

        if duration_seconds <= 0 or interval_seconds <= 0 or cycle_seconds <= 0:
            raise ValueError("Injection timings must be positive")
        if count <= 0:
            raise ValueError("Injection count must be positive")

        self.injection_settings = InjectionSettings(
            duration_seconds=duration_seconds,
            interval_seconds=interval_seconds,
            count=count,
            cycle_seconds=cycle_seconds,
        )
        self._persist_settings()
        self.journal.log_event(
            event_type="settings_injection_updated",
            description="Injection settings updated and persisted",
            system_snapshot=self.snapshot_state(),
        )
        return self.injection_settings

    def configure_pressure(self, *, minimum_bar: float, maximum_bar: float) -> PressureSettings:
        if minimum_bar <= 0 or maximum_bar <= 0:
            raise ValueError("Pressure limits must be positive")
        if minimum_bar >= maximum_bar:
            raise ValueError("Pressure minimum must be lower than pressure maximum")

        pressure_settings = PressureSettings(minimum_bar=minimum_bar, maximum_bar=maximum_bar)
        self.controller.pressure_min = minimum_bar
        self.controller.pressure_max = maximum_bar
        self.settings.pressure = pressure_settings
        self._persist_settings()
        self.journal.log_event(
            event_type="settings_pressure_updated",
            description="Pressure limits updated and persisted",
            system_snapshot=self.snapshot_state(),
        )
        return pressure_settings

    def update_user_parameters(self, **changes: Any) -> dict[str, Any]:
        self.user_parameters.update(changes)
        self._persist_settings()
        self.journal.log_event(
            event_type="settings_user_parameters_updated",
            description="User parameters updated and persisted",
            system_snapshot=self.snapshot_state(),
        )
        return dict(self.user_parameters)

    def read_telemetry(self) -> dict[str, Any]:
        pressure = self.controller.last_pressure
        reference = None

        try:
            pressure = self.pressure_sensor.read_pressure()
            self.controller.last_pressure = pressure
        except Exception as exc:
            self.journal.log_technical(
                event_type="pressure_read_failed",
                description=f"Failed to read pressure sensor: {exc}",
                system_snapshot=self.snapshot_state(),
            )

        try:
            reference = self.reference_meter.read_reference_value()
        except Exception as exc:
            self.journal.log_technical(
                event_type="reference_read_failed",
                description=f"Failed to read reference meter: {exc}",
                system_snapshot=self.snapshot_state(),
            )

        snapshot = self.snapshot_state()
        snapshot["pressure"] = pressure
        snapshot["reference"] = reference
        return snapshot

    def get_journal_entries(self, channel: str = "all") -> list[tuple[str, JournalEntry]]:
        journals: list[tuple[str, list[JournalEntry]]] = []
        if channel in {"all", "event"}:
            journals.append(("event", self.journal.event_journal.read_all()))
        if channel in {"all", "alarm"}:
            journals.append(("alarm", self.journal.alarm_journal.read_all()))
        if channel in {"all", "technical"}:
            journals.append(("technical", self.journal.technical_journal.read_all()))

        entries = [
            (journal_name, entry)
            for journal_name, journal_entries in journals
            for entry in journal_entries
        ]
        return sorted(entries, key=lambda item: item[1].timestamp, reverse=True)

    def build_system_info(self) -> dict[str, Any]:
        return {
            "software_version": self.software_version,
            "data_directory": str(self.data_dir.resolve()),
            "settings_file": str(self.settings_storage.path.resolve()),
            "log_export_directory": str((self.data_dir / "exports").resolve()),
            "remote_access": {
                "tls_required": self.remote_access_policy.require_tls,
                "token_count": len(self.remote_access_policy.allowed_tokens),
                "certificate_count": len(
                    self.remote_access_policy.allowed_client_certificates
                ),
                "link_active": self.remote_link_active,
            },
            "devices": self.snapshot_state()["devices"],
        }

    def export_logs_archive(self) -> Path:
        archive_path = self.journal.export_archive(self.data_dir / "exports")
        self.journal.log_technical(
            event_type="logs_exported",
            description=f"Log archive exported to {archive_path.name}",
            system_snapshot=self.snapshot_state(),
        )
        return archive_path

    def snapshot_state(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "pressure": self.controller.last_pressure,
            "reference": None,
            "pressure_limits": {
                "minimum_bar": self.controller.pressure_min,
                "maximum_bar": self.controller.pressure_max,
            },
            "injection_settings": {
                "duration_seconds": self.injection_settings.duration_seconds,
                "interval_seconds": self.injection_settings.interval_seconds,
                "count": self.injection_settings.count,
                "cycle_seconds": self.injection_settings.cycle_seconds,
            },
            "user_parameters": dict(self.user_parameters),
            "devices": {
                "compressor_connected": bool(getattr(self.compressor, "is_connected", True)),
                "valve_connected": bool(getattr(self.valve, "is_connected", True)),
                "pressure_sensor_connected": bool(
                    getattr(self.pressure_sensor, "is_connected", True)
                ),
                "reference_meter_connected": bool(
                    getattr(self.reference_meter, "is_connected", True)
                ),
                "compressor_running": bool(getattr(self.compressor, "is_running", False)),
                "valve_running": bool(getattr(self.valve, "is_running", False)),
            },
            "remote": {
                "link_active": self.remote_link_active,
                "tls_required": self.remote_access_policy.require_tls,
            },
        }

    def _persist_settings(self) -> None:
        self.settings = SettingsBundle(
            injection=self.injection_settings,
            pressure=PressureSettings(
                minimum_bar=self.controller.pressure_min,
                maximum_bar=self.controller.pressure_max,
            ),
            user_parameters=dict(self.user_parameters),
        )
        self.settings_storage.save(self.settings)
