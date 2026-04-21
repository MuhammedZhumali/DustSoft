"""Unified device and safety error model for DustSoft v1."""

from __future__ import annotations


class DustSoftError(RuntimeError):
    """Base class for application-level failures."""


class DeviceError(DustSoftError):
    """Base class for device communication or runtime failures."""


class DeviceTimeout(DeviceError):
    """Raised when a device fails to respond within an expected timeout."""


class DeviceProtocolError(DeviceError):
    """Raised when a device responds with malformed or unexpected data."""


class SafetyViolation(DustSoftError):
    """Raised when a safety invariant is broken and emergency stop is required."""
