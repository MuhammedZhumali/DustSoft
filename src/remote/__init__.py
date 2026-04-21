"""Remote monitoring and emergency stop service with auth and audit."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.application import Application


class RemoteSecurityError(RuntimeError):
    """Raised when a remote call does not satisfy the security policy."""


@dataclass(frozen=True, slots=True)
class RemoteAccessPolicy:
    """Authorization and transport requirements for remote access."""

    require_tls: bool = True
    allowed_tokens: frozenset[str] = field(default_factory=frozenset)
    allowed_client_certificates: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True, slots=True)
class RemoteRequestContext:
    """Remote caller identity and transport metadata."""

    client_id: str
    secure_channel: bool
    token: str | None = None
    client_certificate_subject: str | None = None


class RemoteService:
    """Expose monitoring and emergency stop over a protected remote boundary."""

    def __init__(self, app: Application, *, access_policy: RemoteAccessPolicy) -> None:
        self.app = app
        self.access_policy = access_policy
        self.link_connected = True

    def monitor(self, context: RemoteRequestContext) -> dict[str, object]:
        principal = self._authorize(context)
        snapshot = self.app.snapshot_state()
        self.app.journal.log_event(
            event_type="remote_monitor",
            description=f"Remote monitor by {principal} ({context.client_id})",
            system_snapshot=snapshot,
        )
        return snapshot

    def emergency_stop(self, context: RemoteRequestContext, *, reason: str) -> dict[str, object]:
        principal = self._authorize(context)
        self.app.emergency_stop(f"remote:{principal}:{reason}")
        snapshot = self.app.snapshot_state()
        self.app.journal.log_alarm(
            event_type="remote_emergency_stop",
            description=f"Remote emergency stop by {principal} ({context.client_id}): {reason}",
            system_snapshot=snapshot,
        )
        return snapshot

    def mark_link_degraded(self, reason: str) -> None:
        self.link_connected = False
        self.app.remote_link_active = False
        self.app.journal.log_technical(
            event_type="remote_link_degraded",
            description=(
                "Remote connection lost; local safety controls remain authoritative. "
                f"Reason: {reason}"
            ),
            system_snapshot=self.app.snapshot_state(),
        )

    def restore_link(self, reason: str) -> None:
        self.link_connected = True
        self.app.remote_link_active = True
        self.app.journal.log_technical(
            event_type="remote_link_restored",
            description=f"Remote connection restored: {reason}",
            system_snapshot=self.app.snapshot_state(),
        )

    def _authorize(self, context: RemoteRequestContext) -> str:
        if self.access_policy.require_tls and not context.secure_channel:
            raise RemoteSecurityError("remote access requires a TLS-protected channel")

        if context.token and context.token in self.access_policy.allowed_tokens:
            return f"token:{context.client_id}"

        if (
            context.client_certificate_subject
            and context.client_certificate_subject in self.access_policy.allowed_client_certificates
        ):
            return f"certificate:{context.client_certificate_subject}"

        raise RemoteSecurityError("remote access denied: invalid token or client certificate")
