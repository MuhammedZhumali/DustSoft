# Remote Access

## Scope In Simplified Version

The simplified software version supports:

- remote monitoring of current system state;
- remote emergency stop;
- audit logging for all remote actions;
- degraded behavior if remote connectivity is lost.

Full remote calibration workflows are intentionally out of scope for the simplified version.

## Security Model

Remote access is protected by:

- TLS-protected transport;
- authorization by token and/or trusted client certificate;
- audit records in structured journals.

The implementation stores and reports:

- whether TLS is mandatory;
- how many tokens are configured;
- how many trusted certificates are configured;
- whether the remote link is active or degraded.

## Logged Remote Actions

The system records:

- remote monitoring requests;
- remote emergency stop commands;
- remote link degradation events;
- remote link restoration events.

Each record includes:

- timestamp;
- event type;
- description;
- snapshot of the system state at the moment of the event.

Remote action logs are retained both in the current journal files and in daily historical journal files.

## Degraded Mode

If the remote link is lost:

- the event is written to the technical journal;
- local safety logic remains authoritative;
- operator commands continue to work locally;
- unsafe actions remain blocked by local interlocks.

Loss of remote connectivity does not disable local emergency stop and does not bypass local safety checks.

## Example Deployment Note

In production on Raspberry Pi, place the remote API behind:

- HTTPS with server certificate;
- token provisioning under OS-level secret storage or protected configuration;
- firewall rules exposing only the required port.
