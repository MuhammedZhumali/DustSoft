import logging
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.controller import Controller
from core.state_machine import AppState, StateTransitionError
from devices.mocks import MockActuator, MockPressureSensor
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


if __name__ == "__main__":
    unittest.main()
