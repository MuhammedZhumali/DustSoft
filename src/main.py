"""Application entry point."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from time import sleep

if __package__ == "src":
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.application import Application
from devices.config import HardwareConfig, load_hardware_config, save_hardware_config
from devices.mocks import (
    MockActuator,
    MockAnalogInput,
    MockEmergencyButton,
    MockPressureSensor,
)
from devices.raspberry_pi import RaspberryPiGpioError, RaspberryPiRelayActuator
from reference_meter.dusttrak import (
    DustTrakAnalogClient,
    DustTrakEthernetClient,
    DustTrakHttpClient,
)
from ui import launch_ui


def _hardware_mode() -> str:
    mode = os.environ.get("DUSTSOFT_HARDWARE", "auto").strip().lower()
    if mode not in {"auto", "mock", "raspberry-pi"}:
        raise ValueError(
            "DUSTSOFT_HARDWARE must be one of: auto, mock, raspberry-pi"
        )
    return mode


def _is_raspberry_pi_host() -> bool:
    try:
        model = Path("/proc/device-tree/model").read_text(
            encoding="utf-8",
            errors="ignore",
        ).lower()
    except OSError:
        return False
    return "raspberry pi" in model


def _build_relay_actuator(name: str, config, mode: str):
    if mode == "mock":
        return MockActuator()
    try:
        return RaspberryPiRelayActuator(config)
    except RaspberryPiGpioError:
        if mode == "raspberry-pi" or _is_raspberry_pi_host():
            raise
        print(f"{name}: GPIO unavailable; using mock relay output")
        return MockActuator()


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
    raise ValueError(f"Unsupported reference meter mode: {meter.mode}")


def _build_devices(config: HardwareConfig):
    mode = _hardware_mode()
    return {
        "compressor": _build_relay_actuator(
            "compressor",
            config.relay_outputs.compressor,
            mode,
        ),
        "valve": _build_relay_actuator(
            "valve",
            config.relay_outputs.valve,
            mode,
        ),
        "pressure_sensor": MockPressureSensor([config.pressure_inputs.high_default_bar]),
        "pressure_low_sensor": MockPressureSensor([config.pressure_inputs.low_default_bar]),
        "reference_meter": _build_reference_meter(config),
        "emergency_button": MockEmergencyButton(),
    }


def build_app(config_path: Path | None = None) -> Application:
    """Initialize application dependencies.

    Uses Raspberry Pi GPIO relays for outputs and built-in fallback pressure values.
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
    )


def run() -> None:
    """Start the application with Raspberry Pi GPIO."""
    app = build_app()
    app.bootstrap()
    result = app.run_once()
    print(f"Application finished cycle: {result}")


def run_gui() -> None:
    """Start the operator GUI with Raspberry Pi GPIO."""
    app = build_app()
    app.bootstrap()
    launch_ui(app)


def run_gpio_test(config_path: Path | None = None) -> None:
    """Drive relay GPIO pins through known physical levels for diagnostics."""
    try:
        from gpiozero import OutputDevice  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "gpiozero is not installed; install it with '.venv/bin/python -m pip install gpiozero lgpio'"
        ) from exc

    config = load_hardware_config(config_path or Path("data") / "hardware.json")
    outputs = {
        "compressor": config.relay_outputs.compressor,
        "valve": config.relay_outputs.valve,
    }
    devices = {
        name: OutputDevice(output.pin_bcm, active_high=True, initial_value=bool(output.safe_level))
        for name, output in outputs.items()
    }

    def set_level(name: str, level: int) -> None:
        devices[name].value = level
        print(f"{name} BCM{outputs[name].pin_bcm} = {'HIGH' if level else 'LOW'}")

    try:
        print("GPIO diagnostic test. Watch the relay IN LEDs.")
        print("Step 1: both SAFE for 5 seconds")
        set_level("compressor", outputs["compressor"].safe_level)
        set_level("valve", outputs["valve"].safe_level)
        sleep(5)

        print("Step 2: compressor ACTIVE, valve SAFE for 5 seconds")
        set_level("compressor", outputs["compressor"].active_level)
        set_level("valve", outputs["valve"].safe_level)
        sleep(5)

        print("Step 3: compressor ACTIVE, valve ACTIVE for 5 seconds")
        set_level("compressor", outputs["compressor"].active_level)
        set_level("valve", outputs["valve"].active_level)
        sleep(5)

        print("Step 4: both SAFE")
        set_level("compressor", outputs["compressor"].safe_level)
        set_level("valve", outputs["valve"].safe_level)
    finally:
        for name, device in devices.items():
            device.value = outputs[name].safe_level
            device.close()


def main() -> None:
    """Console-script compatible launcher."""
    parser = argparse.ArgumentParser(description="DustSoft control app")
    parser.add_argument(
        "command",
        nargs="?",
        default="run",
        choices=["run", "gui", "gpio-test"],
        help="Command to execute",
    )
    args = parser.parse_args()

    if args.command == "run":
        run()
    if args.command == "gui":
        run_gui()
    if args.command == "gpio-test":
        run_gpio_test()


if __name__ == "__main__":
    main()
