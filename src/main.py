"""Application entry point."""

from __future__ import annotations

import argparse
from pathlib import Path

from core.application import Application
from devices.config import HardwareConfig, load_hardware_config, save_hardware_config
from devices.mocks import (
    MockActuator,
    MockAnalogInput,
    MockEmergencyButton,
    MockPressureSensor,
    MockReferenceMeter,
)
from devices.raspberry_pi import (
    GpioDiagnosticService,
    MemoryGpioBackend,
    RPiGpioBackend,
    RaspberryPiActuator,
    RaspberryPiEmergencyButton,
)
from reference_meter.dusttrak import (
    DustTrakAnalogClient,
    DustTrakEthernetClient,
    DustTrakHttpClient,
)
from ui import launch_ui


def _build_reference_meter(config: HardwareConfig):
    meter = config.reference_meter
    if meter.mode == "dusttrak_ethernet":
        command = meter.command.encode("ascii", errors="ignore")
        if not command.endswith(b"\n"):
            command += b"\n"
        return DustTrakEthernetClient(
            host=meter.host,
            port=meter.port,
            command=command,
            timeout_seconds=meter.timeout_seconds,
        )
    if meter.mode == "dusttrak_http":
        return DustTrakHttpClient(
            url=meter.url,
            timeout_seconds=meter.timeout_seconds,
        )
    if meter.mode == "dusttrak_analog":
        return DustTrakAnalogClient(
            analog_input=MockAnalogInput(),
            channel=meter.analog_channel,
            signal=meter.analog_signal,
            min_value=meter.analog_min_value,
            max_value=meter.analog_max_value,
        )
    return MockReferenceMeter()


def _build_devices(config: HardwareConfig):
    backend = None
    if config.mode == "raspberry_pi":
        if config.dry_run:
            backend = MemoryGpioBackend()
        else:
            try:
                backend = RPiGpioBackend()
            except Exception:
                backend = MemoryGpioBackend()

        return {
            "compressor": RaspberryPiActuator(config.compressor_enable, backend),
            "valve": RaspberryPiActuator(config.injection_valve, backend),
            "pressure_sensor": MockPressureSensor(),
            "pressure_low_sensor": MockPressureSensor([0.2]),
            "reference_meter": _build_reference_meter(config),
            "emergency_button": RaspberryPiEmergencyButton(config.emergency_input, backend),
            "gpio_backend": backend,
        }

    return {
        "compressor": MockActuator(),
        "valve": MockActuator(),
        "pressure_sensor": MockPressureSensor(),
        "pressure_low_sensor": MockPressureSensor([0.2]),
        "reference_meter": MockReferenceMeter(),
        "emergency_button": MockEmergencyButton(),
        "gpio_backend": MemoryGpioBackend(),
    }


def build_app(config_path: Path | None = None) -> Application:
    """Initialize application dependencies.

    Uses mock adapters by default so the app can run without real hardware.
    """
    config_path = config_path or Path("data") / "hardware.json"
    if not config_path.exists():
        save_hardware_config(config_path, HardwareConfig())
    config = load_hardware_config(config_path)
    devices = _build_devices(config)
    return Application(
        compressor=devices["compressor"],
        valve=devices["valve"],
        pressure_sensor=devices["pressure_sensor"],
        pressure_low_sensor=devices["pressure_low_sensor"],
        reference_meter=devices["reference_meter"],
        emergency_button=devices["emergency_button"],
        data_dir=Path("data"),
        hardware_config=config,
        hardware_config_path=config_path,
        gpio_backend=devices["gpio_backend"],
        gpio_diagnostics=GpioDiagnosticService(devices["gpio_backend"]),
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
