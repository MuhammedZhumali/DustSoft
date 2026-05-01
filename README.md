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
.\.venv\Scripts\python.exe src\main.py gui
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

To prepare the hardware mapping, copy [config/hardware.example.json](/c:/Users/Muhalek/DustSoft/DustSoft/config/hardware.example.json:1) to `data/hardware.json`.

Raspberry Pi controls the relay board directly:

- relay IN1 / compressor: BCM GPIO17;
- relay IN2 / injection valve: BCM GPIO27 by default.

Arduino is used only as an analog reader. It sends values for `A0` and `A4` over
USB serial. Configure `arduino_serial.port` as `/dev/ttyACM0` or `/dev/ttyUSB0`.
If your second relay is physically wired to BCM GPIO18 instead of BCM GPIO27,
change `relay_outputs.valve.pin_bcm` in `data/hardware.json` from `27` to `18`.

Standalone hardware smoke test:

```bash
ls /dev/ttyACM* /dev/ttyUSB*
python3 -m pip install pyserial gpiozero lgpio
python3 scripts/raspberry_relay_from_arduino.py --port /dev/ttyACM0 --threshold-a0 512
```

Use `--relay2-gpio 18` if relay IN2 is wired to BCM GPIO18. Add `--active-low`
if the relay module turns on when the GPIO output is LOW.

The reference meter is built from `reference_meter` in `data/hardware.json`.
Supported modes are `dusttrak_ethernet`, `dusttrak_http`, and `dusttrak_analog`.
The default is a DustTrak Ethernet text-frame client at
`192.168.1.50:3602` with command `READ`; change these values to match the actual
DustTrak connection before live use. Analog mode expects an ADC or 4-20 mA
converter behind the configured channel.

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
