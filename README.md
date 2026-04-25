# DustSoft

DustSoft is the simplified software stack for the dust-air mixture chamber control block.  
Current scope matches the simplified software requirements from the technical specification:

- local operator GUI with main, injection settings, pressure settings, journal, and system info screens;
- manual dust injection, start, stop, and emergency stop commands;
- interval dust injection with fixed cycles or DustTrak target concentration control;
- dual pressure telemetry fields for D1 high pressure and D2 low pressure;
- DustTrak II Ethernet/HTTP text-frame adapters for reference concentration readings;
- CSV measurement archives under `data/measurements/`;
- persistent settings recovery after restart;
- structured event, alarm, and technical journals;
- remote monitoring and remote emergency stop over a protected channel;
- safe degradation when remote connectivity is lost.

## Quick Start

From the project folder run the console smoke test:

```powershell
.\dustsoft run
```

Start the operator GUI:

```powershell
.\dustsoft gui
```

Or run through the virtual environment directly:

```powershell
.\.venv\Scripts\python.exe -m src.main gui
```

## Tests

Run local checks without real hardware:

```powershell
.\dustsoft-test
```

## Data And Recovery

- Runtime data is stored in `data/`.
- Persistent settings are stored in `data/settings.json`.
- Optional hardware mapping can be provided in `data/hardware.json`.
- Stand configuration is stored in `data/config.json` and validated on startup.
- Journals are stored in `data/events.log.jsonl`, `data/alarms.log.jsonl`, and `data/technical.log.jsonl`.
- Measurement archives are stored in `data/measurements/<test_id>.csv`.
- Daily log history is stored in `data/history/<journal-name>/YYYY-MM-DD.jsonl`.
- Exported log bundles are stored in `data/exports/`.
- After restart, the application restores saved injection settings, pressure limits, and user parameters during bootstrap.

To prepare a Raspberry Pi mapping, copy [config/hardware.example.json](/c:/Users/Muhalek/DustSoft/DustSoft/config/hardware.example.json:1) to `data/hardware.json` and edit the GPIO assignments.

The Raspberry Pi GPIO pins do not drive the compressor, valve, or 220V circuits
directly. They only command the external control-board inputs through relays or
driver modules. The default mapping assumes inverted relay logic:
`active_level=0` means GPIO LOW commands the external line ON, and `safe_level=1`
means GPIO HIGH keeps the external line OFF at startup. If your relay or driver
is active HIGH, set `active_level=1` and `safe_level=0` for that channel.

In `raspberry_pi` mode the reference meter is built from `reference_meter` in
`data/hardware.json`. Supported modes are `dusttrak_ethernet`, `dusttrak_http`,
`dusttrak_analog`, and `mock`. The default is a DustTrak Ethernet text-frame
client at `192.168.1.50:3602` with command `READ`; change these values to match
the actual DustTrak connection before live use. Analog mode expects an ADC or
4-20 mA converter behind the configured channel.

The application also exposes an internal service API for UI and future remote transports. This API is not necessarily a network API; it is a shared command/query layer used by GUI, orchestration, and integration code.

## Raspberry Pi Autostart

An example `systemd` unit is included in [deploy/dustsoft.service](/c:/Users/Muhalek/DustSoft/DustSoft/deploy/dustsoft.service:1).

Typical installation steps on Raspberry Pi:

```bash
sudo cp deploy/dustsoft.service /etc/systemd/system/dustsoft.service
sudo systemctl daemon-reload
sudo systemctl enable dustsoft.service
sudo systemctl start dustsoft.service
sudo systemctl status dustsoft.service
```

## Documentation

- [docs/operator_manual.md](/c:/Users/Muhalek/DustSoft/DustSoft/docs/operator_manual.md:1)
- [docs/settings_schema.md](/c:/Users/Muhalek/DustSoft/DustSoft/docs/settings_schema.md:1)
- [docs/remote_access.md](/c:/Users/Muhalek/DustSoft/DustSoft/docs/remote_access.md:1)
- [docs/technical_spec.md](/c:/Users/Muhalek/DustSoft/DustSoft/docs/technical_spec.md:1)
