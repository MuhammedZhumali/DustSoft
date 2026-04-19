"""Application entry point."""

from __future__ import annotations

import typer

from core.application import Application
from devices.mocks import MockActuator, MockPressureSensor, MockReferenceMeter

cli = typer.Typer(help="DustSoft control app.")


@cli.command()
def run() -> None:
    """Start the application with mock dependencies."""
    app = Application(
        actuator=MockActuator(),
        pressure_sensor=MockPressureSensor(),
        reference_meter=MockReferenceMeter(),
    )
    app.bootstrap()
    result = app.run_once()
    typer.echo(f"Application finished cycle: {result}")


def main() -> None:
    """Console-script compatible launcher."""
    cli()


if __name__ == "__main__":
    main()
