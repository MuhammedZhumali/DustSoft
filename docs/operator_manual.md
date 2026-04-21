# Operator Manual

## Purpose

The simplified DustSoft operator interface supports:

- start and stop of the installation;
- emergency stop from the main screen;
- manual dust injection by operator command;
- setup of injection parameters and pressure limits;
- review of journals and system information;
- real-time telemetry for pressure, actuator state, and reference meter readings.

## Screens

### Main

The main screen contains:

- `Пуск`;
- `Стоп`;
- `Аварийная остановка`;
- `Подать пыль`;
- `Сброс аварии`;
- live indicators for application state, pressure, reference meter, compressor, injection valve, and remote link health.

### Injection Settings

The `Настройка впрыска` screen stores:

- injection duration;
- interval between injections;
- injection count;
- cycle duration;
- free-form user parameters in `key=value` format.

### Pressure Settings

The `Настройка давления` screen stores:

- lower pressure limit;
- upper pressure limit.

Recommended working range from the simplified technical specification is:

- high-pressure control: `4..8 bar`;
- low-pressure working range after reduction: chosen by operator according to target concentration.

### Journal

The journal screen shows event, alarm, and technical entries with:

- timestamp;
- journal channel;
- event type;
- description;
- system state snapshot.

The journal screen also provides `Экспорт логов`, which creates a zip archive with:

- current journal files;
- daily historical journal files;
- data suitable for transfer from Raspberry Pi for diagnostics.

### System Info

The `Об установке` screen shows:

- software version;
- runtime data path;
- settings file path;
- remote access policy summary;
- device connectivity summary.

## Normal Workflow

1. Start the application and wait for the GUI to appear.
2. Open `Настройка давления` and confirm the working limits.
3. Open `Настройка впрыска` and confirm injection timings.
4. Return to `Главный` and press `Пуск`.
5. Monitor live telemetry.
6. Press `Подать пыль` when manual injection is required.
7. Press `Стоп` after the working cycle is complete.

## Emergency Workflow

1. Press `Аварийная остановка` immediately if unsafe behavior is observed.
2. Confirm that the system enters `EMERGENCY`.
3. Check the alarm journal.
4. Eliminate the root cause.
5. Press `Сброс аварии`.
6. Restart the working cycle only after physical safety is confirmed.

## Recovery After Restart

After power restoration or software restart:

1. DustSoft restores settings from `data/settings.json`.
2. The application writes a technical journal record about bootstrap recovery.
3. The operator verifies pressure limits, injection settings, and device connectivity on screen.
4. The operator resumes work only after confirming safe state and readiness.

## Log Availability

- current logs are always available in `data/*.log.jsonl`;
- historical logs are retained by day in `data/history/`;
- logs are not limited to the current session;
- an operator can export accumulated logs from the journal screen at any time.
