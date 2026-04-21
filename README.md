# DustSoft

DustSoft is the simplified software stack for the dust-air mixture chamber control block.  
Current scope matches the simplified software requirements from the technical specification:

- local operator GUI with main, injection settings, pressure settings, journal, and system info screens;
- manual dust injection, start, stop, and emergency stop commands;
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
- Journals are stored in `data/events.log.jsonl`, `data/alarms.log.jsonl`, and `data/technical.log.jsonl`.
- Daily log history is stored in `data/history/<journal-name>/YYYY-MM-DD.jsonl`.
- Exported log bundles are stored in `data/exports/`.
- After restart, the application restores saved injection settings, pressure limits, and user parameters during bootstrap.

To prepare a Raspberry Pi mapping, copy [config/hardware.example.json](/c:/Users/Muhalek/DustSoft/DustSoft/config/hardware.example.json:1) to `data/hardware.json` and edit the GPIO assignments.

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
