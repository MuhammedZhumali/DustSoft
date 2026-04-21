import logging
import shutil
import unittest
from pathlib import Path
import sys
from uuid import uuid4
from zipfile import ZipFile
import json
from core.config_model import InjectionProfile, JsonStandConfigStorage, StandConfig
from core.cycle import CycleStage, PulsePlanner
from core.errors import DeviceProtocolError
from core.service_api import ApplicationApi

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.application import Application
from core.controller import Controller
from devices.config import load_hardware_config
from core.state_machine import AppState, StateTransitionError
from devices.mocks import MockActuator, MockPressureSensor, MockReferenceMeter
from remote import RemoteAccessPolicy, RemoteRequestContext, RemoteSecurityError
from safety.interlock import InterlockError


class ControllerSafetyTests(unittest.TestCase):
    def build_controller(self, pressure: float = 1.0) -> Controller:
        logger = logging.getLogger("controller-test")
        logger.disabled = True
        controller = Controller(
            compressor=MockActuator(),
            valve=MockActuator(),
            pressure_sensor=MockPressureSensor([pressure]),
            pressure_min=0.8,
            pressure_max=1.5,
            logger=logger,
        )
        controller.state_machine.transition_to(AppState.READY)
        controller.start()
        return controller

    def test_manual_injection_requires_allowed_pressure(self) -> None:
        controller = self.build_controller(pressure=2.0)

        with self.assertRaises(InterlockError):
            controller.manual_injection()

        self.assertFalse(controller.valve.is_running)
        self.assertEqual(controller.state, AppState.RUNNING)

    def test_manual_injection_requires_device_communication(self) -> None:
        controller = self.build_controller(pressure=1.0)
        controller.valve.is_connected = False

        with self.assertRaises(InterlockError):
            controller.manual_injection()

        self.assertFalse(controller.valve.is_running)
        self.assertEqual(controller.state, AppState.RUNNING)

    def test_emergency_stop_closes_valve_stops_compressor_and_blocks_commands(self) -> None:
        controller = self.build_controller(pressure=1.0)
        controller.manual_injection()

        controller.emergency_stop("test")

        self.assertEqual(controller.state, AppState.EMERGENCY)
        self.assertFalse(controller.valve.is_running)
        self.assertFalse(controller.compressor.is_running)

        with self.assertRaises(StateTransitionError):
            controller.manual_injection()

    def test_reset_emergency_returns_to_stopped(self) -> None:
        controller = self.build_controller(pressure=1.0)
        controller.emergency_stop("test")

        controller.reset_emergency()

        self.assertEqual(controller.state, AppState.STOPPED)

    def test_device_protocol_error_transitions_to_fault(self) -> None:
        class BrokenPressureSensor(MockPressureSensor):
            def read_pressure(self) -> float:
                raise DeviceProtocolError("bad frame")

        logger = logging.getLogger("controller-test-error")
        logger.disabled = True
        controller = Controller(
            compressor=MockActuator(),
            valve=MockActuator(),
            pressure_sensor=BrokenPressureSensor([1.0]),
            pressure_min=0.8,
            pressure_max=1.5,
            logger=logger,
        )
        controller.state_machine.transition_to(AppState.READY)
        controller.start()

        state = controller.manual_injection()

        self.assertEqual(state, AppState.FAULT)


class ApplicationInfrastructureTests(unittest.TestCase):
    def make_data_dir(self) -> Path:
        root = Path(__file__).resolve().parents[1] / ".testdata"
        root.mkdir(exist_ok=True)
        path = root / f"case-{uuid4().hex}"
        path.mkdir()
        return path

    def build_app(self, data_dir: Path, pressure: float = 1.0) -> Application:
        return Application(
            compressor=MockActuator(),
            valve=MockActuator(),
            pressure_sensor=MockPressureSensor([pressure]),
            reference_meter=MockReferenceMeter(),
            data_dir=data_dir,
            remote_access_policy=RemoteAccessPolicy(
                require_tls=True,
                allowed_tokens=frozenset({"secret-token"}),
                allowed_client_certificates=frozenset({"CN=trusted-client"}),
            ),
        )

    def test_settings_persist_and_restore_after_restart(self) -> None:
        data_dir = self.make_data_dir()
        try:
            app = self.build_app(data_dir)
            app.bootstrap()
            app.configure_injection(duration_seconds=2.5, count=3)
            app.configure_pressure(minimum_bar=0.9, maximum_bar=1.3)
            app.update_user_parameters(operator="alice", recipe="dust-A")

            restored = self.build_app(data_dir)
            restored.bootstrap()

            self.assertEqual(restored.injection_settings.duration_seconds, 2.5)
            self.assertEqual(restored.injection_settings.count, 3)
            self.assertEqual(restored.controller.pressure_min, 0.9)
            self.assertEqual(restored.controller.pressure_max, 1.3)
            self.assertEqual(restored.user_parameters["operator"], "alice")
            self.assertEqual(restored.user_parameters["recipe"], "dust-A")
        finally:
            shutil.rmtree(data_dir, ignore_errors=True)

    def test_journals_store_timestamp_type_description_and_snapshot(self) -> None:
        data_dir = self.make_data_dir()
        try:
            app = self.build_app(data_dir)
            app.bootstrap()
            app.start()

            entry = app.journal.event_journal.read_all()[-1]
            history_files = app.journal.event_journal.list_files()

            self.assertTrue(entry.timestamp)
            self.assertEqual(entry.event_type, "start")
            self.assertIn("Local start", entry.description)
            self.assertIn("state", entry.system_snapshot)
            self.assertIn("devices", entry.system_snapshot)
            self.assertTrue(history_files)
        finally:
            shutil.rmtree(data_dir, ignore_errors=True)

    def test_telemetry_reads_pressure_and_reference_values(self) -> None:
        data_dir = self.make_data_dir()
        try:
            app = self.build_app(data_dir, pressure=1.25)
            app.bootstrap()

            telemetry = app.read_telemetry()

            self.assertEqual(telemetry["pressure"], 1.25)
            self.assertEqual(telemetry["reference"], 1.0)
            self.assertIn("remote", telemetry)
        finally:
            shutil.rmtree(data_dir, ignore_errors=True)

    def test_remote_service_requires_secure_channel_and_logs_actions(self) -> None:
        data_dir = self.make_data_dir()
        try:
            app = self.build_app(data_dir)
            app.bootstrap()

            with self.assertRaises(RemoteSecurityError):
                app.remote_service.monitor(
                    RemoteRequestContext(
                        client_id="client-1",
                        secure_channel=False,
                        token="secret-token",
                    )
                )

            snapshot = app.remote_service.monitor(
                RemoteRequestContext(
                    client_id="client-1",
                    secure_channel=True,
                    token="secret-token",
                )
            )

            self.assertEqual(snapshot["remote"]["tls_required"], True)
            self.assertEqual(app.journal.event_journal.read_all()[-1].event_type, "remote_monitor")
        finally:
            shutil.rmtree(data_dir, ignore_errors=True)

    def test_remote_link_degradation_preserves_local_safety(self) -> None:
        data_dir = self.make_data_dir()
        try:
            app = self.build_app(data_dir, pressure=2.0)
            app.bootstrap()
            app.start()
            app.remote_service.mark_link_degraded("LTE timeout")

            with self.assertRaises(InterlockError):
                app.manual_injection()

            app.emergency_stop("local_button")

            self.assertFalse(app.remote_link_active)
            self.assertEqual(app.state, AppState.EMERGENCY)
            self.assertEqual(
                app.get_journal_entries("technical")[0][1].event_type,
                "remote_link_degraded",
            )
        finally:
            shutil.rmtree(data_dir, ignore_errors=True)

    def test_log_export_contains_current_and_historical_files(self) -> None:
        data_dir = self.make_data_dir()
        try:
            app = self.build_app(data_dir)
            app.bootstrap()
            app.start()
            app.emergency_stop("test_export")

            archive_path = app.export_logs_archive()

            self.assertTrue(archive_path.exists())
            with ZipFile(archive_path) as zip_file:
                names = set(zip_file.namelist())

            self.assertIn("events.log.jsonl", names)
            self.assertIn("alarms.log.jsonl", names)
            self.assertTrue(
                any(name.startswith("history/events.log/") for name in names),
                msg=f"Missing daily event history in archive: {sorted(names)}",
            )
            self.assertTrue(
                any(name.startswith("history/alarms.log/") for name in names),
                msg=f"Missing daily alarm history in archive: {sorted(names)}",
            )
        finally:
            shutil.rmtree(data_dir, ignore_errors=True)

    def test_hardware_config_loads_gpio_mapping(self) -> None:
        data_dir = self.make_data_dir()
        try:
            config_path = data_dir / "hardware.json"
            config_path.write_text(
                json.dumps(
                    {
                        "mode": "raspberry_pi",
                        "gpio": {
                            "compressor_enable": {"pin_bcm": 17, "active_level": 1, "safe_level": 0},
                            "injection_valve": {"pin_bcm": 27, "active_level": 1, "safe_level": 0},
                            "emergency_input": {"pin_bcm": 22, "active_level": 0, "pull": "up"},
                        },
                    }
                ),
                encoding="utf-8",
            )

            config = load_hardware_config(config_path)

            self.assertEqual(config.mode, "raspberry_pi")
            self.assertEqual(config.compressor_enable.pin_bcm, 17)
            self.assertEqual(config.injection_valve.pin_bcm, 27)
            self.assertEqual(config.emergency_input.pin_bcm, 22)
        finally:
            shutil.rmtree(data_dir, ignore_errors=True)

    def test_stand_config_validates_and_loads_defaults(self) -> None:
        data_dir = self.make_data_dir()
        try:
            storage = JsonStandConfigStorage(data_dir / "config.json")
            config = storage.load()

            self.assertEqual(config.schema_version, 1)
            self.assertIn("default", config.injection_profiles)
            self.assertTrue(config.calibration.control_points)
        finally:
            shutil.rmtree(data_dir, ignore_errors=True)

    def test_pulse_planner_builds_expected_schedule(self) -> None:
        planner = PulsePlanner()
        profile = InjectionProfile(
            name="fast",
            duration_seconds=0.2,
            interval_seconds=1.5,
            count=3,
            cycle_seconds=6.0,
        )

        plan = planner.plan(profile)

        self.assertEqual([pulse.index for pulse in plan], [1, 2, 3])
        self.assertEqual([pulse.at_seconds for pulse in plan], [0.0, 1.5, 3.0])

    def test_internal_api_exposes_cycle_and_events(self) -> None:
        data_dir = self.make_data_dir()
        try:
            app = self.build_app(data_dir, pressure=1.0)
            app.bootstrap()
            api = ApplicationApi(app)

            telemetry = api.start_cycle()
            events = api.poll_events()

            self.assertEqual(telemetry["cycle"]["stage"], CycleStage.COMPLETED.value)
            self.assertTrue(events)
            self.assertEqual(events[0].name, "cycle_state_changed")
        finally:
            shutil.rmtree(data_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
