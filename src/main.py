"""Application entry point."""

from __future__ import annotations

import argparse

from core.application import Application
from devices.mocks import MockActuator, MockPressureSensor, MockReferenceMeter


def build_app() -> Application:
    """Initialize application dependencies.

    Uses mock adapters by default so the app can run without real hardware.
    """
    return Application(
        compressor=MockActuator(),
        valve=MockActuator(),
        pressure_sensor=MockPressureSensor(),
        reference_meter=MockReferenceMeter(),
    )


def run() -> None:
    """Start the application with mock dependencies."""
    app = build_app()
    app.bootstrap()
    result = app.run_once()
    print(f"Application finished cycle: {result}")


def main() -> None:
    """Console-script compatible launcher."""
    parser = argparse.ArgumentParser(description="DustSoft control app")
    parser.add_argument(
        "command",
        nargs="?",
        default="run",
        choices=["run"],
        help="Command to execute",
    )
    args = parser.parse_args()

    if args.command == "run":
        run()


if __name__ == "__main__":
    main()
