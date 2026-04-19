"""Application state machine primitives."""

from enum import Enum


class AppState(str, Enum):
    """Top-level runtime states for the application lifecycle."""

    IDLE = "IDLE"
    READY = "READY"
    RUNNING = "RUNNING"
    INJECTION = "INJECTION"
    STOPPED = "STOPPED"
    EMERGENCY = "EMERGENCY"
    FAULT = "FAULT"
