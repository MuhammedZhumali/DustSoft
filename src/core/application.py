"""Application orchestration layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.config_model import JsonStandConfigStorage, StandConfig
from core.cycle import TechnologyCycleService
from core.errors import DeviceProtocolError, DeviceTimeout, SafetyViolation
from core.service_api import ApplicationApi
from core.controller import Controller
from core.state_machine import AppState
from devices.config import HardwareConfig, save_hardware_config
from logging_system import JournalEntry, JsonLineJournal, JournalService
from devices.ports import ActuatorPort, EmergencyButtonPort, PressureSensorPort, ReferenceMeterPort
from remote import RemoteAccessPolicy, RemoteService
from services.injection_scheduler import InjectionRunResult, InjectionScheduler
from storage import (
    CsvMeasurementArchive,
    InjectionSettings,
    JsonSettingsStorage,
    MeasurementRecord,
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
    pressure_low_sensor: PressureSensorPort | None = None
    emergency_button: EmergencyButtonPort | None = None
    pressure_min: float = 0.8
    pressure_max: float = 1.5
    data_dir: Path = Path("data")
    settings_storage: JsonSettingsStorage | None = None
    config_storage: JsonStandConfigStorage | None = None
    journal: JournalService | None = None
    remote_access_policy: RemoteAccessPolicy = field(default_factory=RemoteAccessPolicy)
    hardware_config: HardwareConfig | None = None
    hardware_config_path: Path | None = None
    gpio_backend: object | None = None
    gpio_diagnostics: object | None = None

    def __post_init__(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.hardware_config_path = self.hardware_config_path or (self.data_dir / "hardware.json")
        self.software_version = _resolve_version()
        self.settings_storage = self.settings_storage or JsonSettingsStorage(
            self.data_dir / "settings.json"
        )
        self.config_storage = self.config_storage or JsonStandConfigStorage(
            self.data_dir / "config.json"
        )
        self.stand_config = self.config_storage.load()
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
            pressure_low_sensor=self.pressure_low_sensor,
            pressure_min=self.settings.pressure.minimum_bar or self.stand_config.pressure.minimum_bar,
            pressure_max=self.settings.pressure.maximum_bar or self.stand_config.pressure.maximum_bar,
            pressure_low_min=self.settings.pressure.low_minimum_bar,
            pressure_low_max=self.settings.pressure.low_maximum_bar,
        )
        self.injection_settings = self.settings.injection
        self.measurement_archive = CsvMeasurementArchive(self.data_dir / "measurements")
        self.current_test_id = uuid4().hex
        self.interval_stop_requested = False
        self.user_parameters = dict(self.settings.user_parameters)
        self.remote_service = RemoteService(self, access_policy=self.remote_access_policy)
        self.cycle_service = TechnologyCycleService(self)
        self.injection_scheduler = InjectionScheduler(
            self,
            should_stop=lambda: self.interval_stop_requested,
        )
        self.api = ApplicationApi(self, cycle_service=self.cycle_service)

    @property
    def state(self) -> AppState:
        """Current application state."""
        return self.controller.state

    def bootstrap(self) -> None:
        """Prepare dependencies before normal operation."""
        try:
            self.stand_config.validate()
            self.controller.state_machine.transition_to(AppState.READY)
        except ValueError as exc:
            self.controller.state_machine.enter_fault()
            self.journal.log_alarm(
                event_type="config_validation_failed",
                description=f"Некорректная конфигурация стенда: {exc}",
                system_snapshot=self.snapshot_state(),
            )
            raise
        self.journal.log_technical(
            event_type="application_bootstrap",
            description="Приложение запущено, сохраненные настройки восстановлены",
            system_snapshot=self.snapshot_state(),
        )

    def run_once(self) -> dict[str, float | str]:
        """Run one cycle of application logic for smoke testing."""
        self.start()
        self.manual_injection()
        reference = self.reference_meter.read_reference_value()
        self.archive_measurement()
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
            description="Выполнена локальная команда запуска",
            system_snapshot=self.snapshot_state(),
        )
        return next_state

    def stop(self) -> AppState:
        next_state = self.controller.stop()
        self.journal.log_event(
            event_type="stop",
            description="Выполнена локальная команда остановки",
            system_snapshot=self.snapshot_state(),
        )
        return next_state

    def manual_injection(self) -> AppState:
        next_state = self.controller.manual_injection()
        self.journal.log_event(
            event_type="manual_injection",
            description="Выполнена ручная подача пыли",
            system_snapshot=self.snapshot_state(),
        )
        return next_state

    def complete_injection(self) -> AppState:
        next_state = self.controller.complete_injection()
        self.journal.log_event(
            event_type="manual_injection_completed",
            description="Импульс ручной подачи пыли завершен",
            system_snapshot=self.snapshot_state(),
        )
        return next_state

    def emergency_stop(self, source: str) -> AppState:
        next_state = self.controller.emergency_stop(source)
        self.journal.log_alarm(
            event_type="emergency_stop",
            description=f"Аварийная остановка вызвана источником: {source}",
            system_snapshot=self.snapshot_state(),
        )
        return next_state

    def reset_emergency(self) -> AppState:
        next_state = self.controller.reset_emergency()
        self.journal.log_event(
            event_type="reset_emergency",
            description="Аварийное состояние сброшено локально",
            system_snapshot=self.snapshot_state(),
        )
        return next_state

    def configure_injection(self, **changes: Any) -> InjectionSettings:
        duration_seconds = changes.get(
            "duration_seconds",
            changes.get("on_duration_seconds", self.injection_settings.on_duration_seconds),
        )
        interval_seconds = changes.get(
            "interval_seconds",
            changes.get("off_duration_seconds", self.injection_settings.off_duration_seconds),
        )
        count = changes.get("count", changes.get("cycles", self.injection_settings.cycles))
        mode = changes.get("mode", self.injection_settings.mode)
        target_concentration = changes.get(
            "target_concentration_mg_m3",
            self.injection_settings.target_concentration_mg_m3,
        )
        cycle_seconds = changes.get("cycle_seconds", self.injection_settings.cycle_seconds)

        if duration_seconds <= 0 or interval_seconds <= 0 or cycle_seconds <= 0:
            raise ValueError("Injection timings must be positive")
        if count is not None and count <= 0:
            raise ValueError("Injection count must be positive")
        if mode not in {"fixed", "concentration"}:
            raise ValueError("Injection mode must be 'fixed' or 'concentration'")
        if mode == "concentration" and target_concentration is None:
            raise ValueError("Target concentration is required for concentration mode")

        self.injection_settings = InjectionSettings(
            on_duration_seconds=duration_seconds,
            off_duration_seconds=interval_seconds,
            cycles=count,
            mode=mode,
            target_concentration_mg_m3=target_concentration,
            cycle_seconds=cycle_seconds,
        )
        self._persist_settings()
        self.journal.log_event(
            event_type="settings_injection_updated",
            description="Настройки впрыска обновлены и сохранены",
            system_snapshot=self.snapshot_state(),
        )
        return self.injection_settings

    def configure_pressure(
        self,
        *,
        minimum_bar: float,
        maximum_bar: float,
        low_minimum_bar: float | None = None,
        low_maximum_bar: float | None = None,
    ) -> PressureSettings:
        low_minimum_bar = self.controller.pressure_low_min if low_minimum_bar is None else low_minimum_bar
        low_maximum_bar = self.controller.pressure_low_max if low_maximum_bar is None else low_maximum_bar
        if minimum_bar < 0 or maximum_bar <= 0:
            raise ValueError("Pressure limits must be positive")
        if minimum_bar >= maximum_bar:
            raise ValueError("Pressure minimum must be lower than pressure maximum")
        if low_minimum_bar < 0 or low_maximum_bar <= 0:
            raise ValueError("Low-pressure limits must be positive")
        if low_minimum_bar >= low_maximum_bar:
            raise ValueError("Low-pressure minimum must be lower than maximum")

        pressure_settings = PressureSettings(
            minimum_bar=minimum_bar,
            maximum_bar=maximum_bar,
            low_minimum_bar=low_minimum_bar,
            low_maximum_bar=low_maximum_bar,
        )
        self.controller.pressure_min = minimum_bar
        self.controller.pressure_max = maximum_bar
        self.controller.pressure_low_min = low_minimum_bar
        self.controller.pressure_low_max = low_maximum_bar
        self.settings.pressure = pressure_settings
        self._persist_settings()
        self.journal.log_event(
            event_type="settings_pressure_updated",
            description="Пределы давления обновлены и сохранены",
            system_snapshot=self.snapshot_state(),
        )
        return pressure_settings

    def update_user_parameters(self, **changes: Any) -> dict[str, Any]:
        self.user_parameters.update(changes)
        self._persist_settings()
        self.journal.log_event(
            event_type="settings_user_parameters_updated",
            description="Пользовательские параметры обновлены и сохранены",
            system_snapshot=self.snapshot_state(),
        )
        return dict(self.user_parameters)

    def read_telemetry(self) -> dict[str, Any]:
        pressure = self.controller.last_pressure
        pressure_low = self.controller.last_pressure_low
        reference = None

        try:
            pressure = self.pressure_sensor.read_pressure()
            self.controller.last_pressure = pressure
            if self.pressure_low_sensor is not None:
                pressure_low = self.pressure_low_sensor.read_pressure()
                self.controller.last_pressure_low = pressure_low
        except Exception as exc:
            self.journal.log_technical(
                event_type="pressure_read_failed",
                description=f"Не удалось прочитать датчик давления: {exc}",
                system_snapshot=self.snapshot_state(),
            )

        self._evaluate_emergency_inputs(pressure, pressure_low)

        try:
            reference = self.reference_meter.read_reference_value()
        except Exception as exc:
            self.journal.log_technical(
                event_type="reference_read_failed",
                description=f"Не удалось прочитать эталонный прибор: {exc}",
                system_snapshot=self.snapshot_state(),
            )

        snapshot = self.snapshot_state()
        snapshot["pressure"] = pressure
        snapshot["pressure_high"] = pressure
        snapshot["pressure_low"] = pressure_low
        snapshot["reference"] = reference
        snapshot["dust_concentration"] = reference
        return snapshot

    def run_interval_injection(self) -> InjectionRunResult:
        self.interval_stop_requested = False
        result = InjectionRunResult(completed_cycles=0, interrupted=True, reason="error")
        try:
            result = self.injection_scheduler.run(self.injection_settings)
        finally:
            self._stop_after_interval_if_needed()
        self.journal.log_event(
            event_type="interval_injection_completed",
            description=(
                f"Интервальная подача завершена: циклов={result.completed_cycles}, "
                f"прервана={result.interrupted}, причина={result.reason}"
            ),
            system_snapshot=self.snapshot_state(),
        )
        return result

    def interrupt_interval_injection(self, reason: str = "operator_request") -> InjectionRunResult:
        self.interval_stop_requested = True
        result = self.injection_scheduler.interrupt(reason)
        self._stop_after_interval_if_needed()
        self.journal.log_event(
            event_type="interval_injection_interrupted",
            description=f"Интервальная подача прервана, причина: {reason}",
            system_snapshot=self.snapshot_state(),
        )
        return result

    def _stop_after_interval_if_needed(self) -> None:
        if self.state == AppState.EMERGENCY:
            return
        if self.state in {
            AppState.IDLE,
            AppState.READY,
            AppState.RUNNING,
            AppState.INJECTION,
            AppState.FAULT,
            AppState.FINISHED,
        }:
            self.stop()

    def archive_measurement(
        self,
        *,
        injection_cycle_id: int | None = None,
        error_code: str | None = None,
    ) -> MeasurementRecord:
        telemetry = self.read_telemetry()
        devices = telemetry["devices"]
        record = MeasurementRecord(
            timestamp=CsvMeasurementArchive.now_iso(),
            test_id=self.current_test_id,
            pressure_high=telemetry.get("pressure_high"),
            pressure_low=telemetry.get("pressure_low"),
            dust_concentration=telemetry.get("dust_concentration"),
            compressor_state=bool(devices["compressor_running"]),
            valve_state=bool(devices["valve_running"]),
            injection_cycle_id=injection_cycle_id,
            system_state=telemetry["state"],
            error_code=error_code,
        )
        return self.measurement_archive.append(record)

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
            "hardware_config_file": str(self.hardware_config_path.resolve()),
            "config_file": str(self.config_storage.path.resolve()),
            "config_schema_version": self.stand_config.schema_version,
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
            "hardware": self.hardware_config.to_mapping() if self.hardware_config else {},
        }

    def update_hardware_config(self, config: HardwareConfig) -> HardwareConfig:
        save_hardware_config(self.hardware_config_path, config)
        self.hardware_config = config
        self.journal.log_technical(
            event_type="hardware_config_updated",
            description="Конфигурация оборудования обновлена и сохранена",
            system_snapshot=self.snapshot_state(),
        )
        return config

    def export_logs_archive(self) -> Path:
        archive_path = self.journal.export_archive(self.data_dir / "exports")
        self.journal.log_technical(
            event_type="logs_exported",
            description=f"Архив логов экспортирован в {archive_path.name}",
            system_snapshot=self.snapshot_state(),
        )
        return archive_path

    def snapshot_state(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "pressure": self.controller.last_pressure,
            "pressure_high": self.controller.last_pressure,
            "pressure_low": self.controller.last_pressure_low,
            "reference": None,
            "pressure_limits": {
                "minimum_bar": self.controller.pressure_min,
                "maximum_bar": self.controller.pressure_max,
                "low_minimum_bar": self.controller.pressure_low_min,
                "low_maximum_bar": self.controller.pressure_low_max,
            },
            "injection_settings": {
                "on_duration_seconds": self.injection_settings.on_duration_seconds,
                "off_duration_seconds": self.injection_settings.off_duration_seconds,
                "cycles": self.injection_settings.cycles,
                "mode": self.injection_settings.mode,
                "target_concentration_mg_m3": (
                    self.injection_settings.target_concentration_mg_m3
                ),
                "duration_seconds": self.injection_settings.duration_seconds,
                "interval_seconds": self.injection_settings.interval_seconds,
                "count": self.injection_settings.count,
                "cycle_seconds": self.injection_settings.cycle_seconds,
            },
            "test_id": self.current_test_id,
            "user_parameters": dict(self.user_parameters),
            "devices": {
                "compressor_connected": bool(getattr(self.compressor, "is_connected", True)),
                "valve_connected": bool(getattr(self.valve, "is_connected", True)),
                "pressure_sensor_connected": bool(
                    getattr(self.pressure_sensor, "is_connected", True)
                ),
                "pressure_low_sensor_connected": bool(
                    getattr(self.pressure_low_sensor, "is_connected", True)
                )
                if self.pressure_low_sensor is not None
                else True,
                "emergency_button_connected": bool(
                    getattr(self.emergency_button, "is_connected", True)
                )
                if self.emergency_button is not None
                else True,
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
                low_minimum_bar=self.controller.pressure_low_min,
                low_maximum_bar=self.controller.pressure_low_max,
            ),
            user_parameters=dict(self.user_parameters),
        )
        self.settings_storage.save(self.settings)

    def _evaluate_emergency_inputs(
        self,
        pressure_high: float | None,
        pressure_low: float | None,
    ) -> None:
        if self.state == AppState.EMERGENCY:
            return
        if self.emergency_button is not None and self.emergency_button.is_pressed():
            self.emergency_stop("emergency_button")
            return
        if pressure_high is not None and pressure_high > self.controller.pressure_max:
            self.emergency_stop("pressure_high_limit")
            return
        if (
            pressure_low is not None
            and (
                pressure_low < self.controller.pressure_low_min
                or pressure_low > self.controller.pressure_low_max
            )
        ):
            self.emergency_stop("pressure_low_limit")
