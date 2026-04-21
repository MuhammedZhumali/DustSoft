"""Raspberry Pi hardware adapters driven by configurable GPIO pins."""

from __future__ import annotations

from dataclasses import dataclass

from .config import GpioOutputConfig


class GpioBackendError(RuntimeError):
    """Raised when Raspberry Pi GPIO support is unavailable."""


class GpioBackend:
    """Best-effort GPIO backend that prefers RPi.GPIO when available."""

    OUT = "out"
    IN = "in"
    PUD_UP = "up"
    PUD_DOWN = "down"

    def setup_output(self, pin_bcm: int, *, initial: int) -> None:
        raise NotImplementedError

    def setup_input(self, pin_bcm: int, *, pull: str) -> None:
        raise NotImplementedError

    def write(self, pin_bcm: int, level: int) -> None:
        raise NotImplementedError

    def read(self, pin_bcm: int) -> int:
        raise NotImplementedError

    def cleanup(self) -> None:
        """Release resources if backend needs it."""


class MemoryGpioBackend(GpioBackend):
    """In-memory backend useful for development and dry runs."""

    def __init__(self) -> None:
        self.levels: dict[int, int] = {}

    def setup_output(self, pin_bcm: int, *, initial: int) -> None:
        self.levels[pin_bcm] = initial

    def setup_input(self, pin_bcm: int, *, pull: str) -> None:
        self.levels.setdefault(pin_bcm, 1 if pull == self.PUD_UP else 0)

    def write(self, pin_bcm: int, level: int) -> None:
        self.levels[pin_bcm] = level

    def read(self, pin_bcm: int) -> int:
        return self.levels.get(pin_bcm, 0)


class RPiGpioBackend(GpioBackend):
    """RPi.GPIO wrapper created only when library is available."""

    def __init__(self) -> None:
        try:
            import RPi.GPIO as gpio  # type: ignore[import-not-found]
        except ImportError as exc:
            raise GpioBackendError(
                "RPi.GPIO is not installed; use mock mode or install GPIO support on Raspberry Pi"
            ) from exc

        self.gpio = gpio
        self.gpio.setmode(self.gpio.BCM)
        self.gpio.setwarnings(False)

    def setup_output(self, pin_bcm: int, *, initial: int) -> None:
        self.gpio.setup(pin_bcm, self.gpio.OUT, initial=initial)

    def setup_input(self, pin_bcm: int, *, pull: str) -> None:
        pull_mode = self.gpio.PUD_UP if pull == self.PUD_UP else self.gpio.PUD_DOWN
        self.gpio.setup(pin_bcm, self.gpio.IN, pull_up_down=pull_mode)

    def write(self, pin_bcm: int, level: int) -> None:
        self.gpio.output(pin_bcm, level)

    def read(self, pin_bcm: int) -> int:
        return int(self.gpio.input(pin_bcm))

    def cleanup(self) -> None:
        self.gpio.cleanup()


@dataclass
class RaspberryPiActuator:
    """GPIO-driven actuator with configurable active and safe levels."""

    config: GpioOutputConfig
    backend: GpioBackend
    is_connected: bool = True
    is_running: bool = False

    def __post_init__(self) -> None:
        self.backend.setup_output(self.config.pin_bcm, initial=self.config.safe_level)

    def start(self) -> None:
        self.backend.write(self.config.pin_bcm, self.config.active_level)
        self.is_running = True

    def stop(self) -> None:
        self.backend.write(self.config.pin_bcm, self.config.safe_level)
        self.is_running = False

    def set_power(self, value: float) -> None:
        if value <= 0:
            self.stop()
            return
        self.start()
