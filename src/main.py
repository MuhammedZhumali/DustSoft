"""Application entry point."""

from __future__ import annotations

import argparse
from pathlib import Path

from core.application import Application
from devices.config import HardwareConfig, load_hardware_config
from devices.mocks import MockActuator, MockPressureSensor, MockReferenceMeter
from devices.raspberry_pi import MemoryGpioBackend, RPiGpioBackend, RaspberryPiActuator
from ui import launch_ui


def _build_devices(config: HardwareConfig):
    if config.mode == "raspberry_pi":
        try:
            backend = RPiGpioBackend()
        except Exception:
            backend = MemoryGpioBackend()

        return {
            "compressor": RaspberryPiActuator(config.compressor_enable, backend),
            "valve": RaspberryPiActuator(config.injection_valve, backend),
            "pressure_sensor": MockPressureSensor(),
            "reference_meter": MockReferenceMeter(),
        }

    return {
        "compressor": MockActuator(),
        "valve": MockActuator(),
        "pressure_sensor": MockPressureSensor(),
        "reference_meter": MockReferenceMeter(),
    }


def build_app(config_path: Path | None = None) -> Application:
    """Initialize application dependencies.

    Uses mock adapters by default so the app can run without real hardware.
    """
    config = load_hardware_config(config_path or Path("data") / "hardware.json")
    devices = _build_devices(config)
    return Application(
        compressor=devices["compressor"],
        valve=devices["valve"],
        pressure_sensor=devices["pressure_sensor"],
        reference_meter=devices["reference_meter"],
        data_dir=Path("data"),
    )


def run() -> None:
    """Start the application with mock dependencies."""
    app = build_app()
    app.bootstrap()
    result = app.run_once()
    print(f"Application finished cycle: {result}")


def run_gui() -> None:
    """Start the operator GUI with mock dependencies."""
    app = build_app()
    app.bootstrap()
    launch_ui(app)


def main() -> None:
    """Console-script compatible launcher."""
    parser = argparse.ArgumentParser(description="DustSoft control app")
    parser.add_argument(
        "command",
        nargs="?",
        default="run",
        choices=["run", "gui"],
        help="Command to execute",
    )
    args = parser.parse_args()

    if args.command == "run":
        run()
    if args.command == "gui":
        run_gui()


if __name__ == "__main__":
    main()
