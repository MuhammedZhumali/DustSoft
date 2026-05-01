"""Raspberry Pi GPIO relay adapters."""

from __future__ import annotations

from dataclasses import dataclass

from .config import RelayOutputConfig


class RaspberryPiGpioError(RuntimeError):
    """Raised when Raspberry Pi GPIO support is unavailable."""


@dataclass
class RaspberryPiRelayActuator:
    """Relay output controlled by a Raspberry Pi BCM GPIO pin."""

    config: RelayOutputConfig
    is_connected: bool = True
    is_running: bool = False

    def __post_init__(self) -> None:
        try:
            from gpiozero import OutputDevice  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RaspberryPiGpioError(
                "gpiozero is not installed; install it with '.venv/bin/python -m pip install gpiozero lgpio'"
            ) from exc

        active_high = self.config.active_level == 1
        initial_value = self.config.safe_level == self.config.active_level
        self.device = OutputDevice(
            self.config.pin_bcm,
            active_high=active_high,
            initial_value=initial_value,
        )

    def start(self) -> None:
        self.device.on()
        self.is_running = True

    def stop(self) -> None:
        self.device.off()
        self.is_running = False

    def set_power(self, value: float) -> None:
        if value <= 0:
            self.stop()
            return
        self.start()
