"""DustTrak II reference meter adapters.

DustTrak protocol details vary by firmware and selected interface. This module
keeps the integration explicit: a callable transport returns one raw text frame,
and the parser extracts the first numeric concentration value in mg/m3.
"""

from __future__ import annotations

import re
import socket
from dataclasses import dataclass
from typing import Literal
from urllib.request import urlopen


class DustTrakCommunicationError(RuntimeError):
    """Raised when the DustTrak reference meter cannot be read."""


_NUMBER_RE = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)")


def parse_concentration(frame: str) -> float:
    """Extract a concentration value from a DustTrak text frame."""
    matches = _NUMBER_RE.findall(frame)
    if not matches:
        raise DustTrakCommunicationError(f"No numeric concentration in frame: {frame!r}")
    return float(matches[-1])


@dataclass
class DustTrakEthernetClient:
    host: str
    port: int = 3602
    command: bytes = b"READ\n"
    timeout_seconds: float = 2.0
    is_connected: bool = True

    def read_reference_value(self) -> float:
        try:
            with socket.create_connection(
                (self.host, self.port),
                timeout=self.timeout_seconds,
            ) as connection:
                connection.sendall(self.command)
                payload = connection.recv(4096).decode("ascii", errors="ignore")
        except OSError as exc:
            self.is_connected = False
            raise DustTrakCommunicationError(str(exc)) from exc

        self.is_connected = True
        return parse_concentration(payload)


@dataclass
class DustTrakHttpClient:
    url: str
    timeout_seconds: float = 2.0
    is_connected: bool = True

    def read_reference_value(self) -> float:
        try:
            with urlopen(self.url, timeout=self.timeout_seconds) as response:
                payload = response.read().decode("utf-8", errors="ignore")
        except OSError as exc:
            self.is_connected = False
            raise DustTrakCommunicationError(str(exc)) from exc

        self.is_connected = True
        return parse_concentration(payload)


@dataclass
class DustTrakAnalogClient:
    """DustTrak analog output reader through an ADC/current converter."""

    analog_input: object
    channel: int = 0
    signal: Literal["voltage_0_5", "current_4_20"] = "voltage_0_5"
    min_value: float = 0.0
    max_value: float = 100.0
    is_connected: bool = True

    def read_reference_value(self) -> float:
        try:
            if self.signal == "current_4_20":
                raw = float(self.analog_input.read_current_ma(self.channel))
                fraction = (raw - 4.0) / 16.0
            else:
                raw = float(self.analog_input.read_voltage(self.channel))
                fraction = raw / 5.0
        except Exception as exc:
            self.is_connected = False
            raise DustTrakCommunicationError(str(exc)) from exc

        self.is_connected = True
        fraction = max(0.0, min(fraction, 1.0))
        return self.min_value + fraction * (self.max_value - self.min_value)
