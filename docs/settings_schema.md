# Settings Schema

DustSoft stores persistent settings in `data/settings.json`.

## Structure

```json
{
  "injection": {
    "on_duration_seconds": 0.1,
    "off_duration_seconds": 5.0,
    "cycles": 1,
    "mode": "fixed",
    "target_concentration_mg_m3": null,
    "cycle_seconds": 30.0
  },
  "pressure": {
    "minimum_bar": 0.0,
    "maximum_bar": 1.5,
    "low_minimum_bar": 0.0,
    "low_maximum_bar": 0.5
  },
  "user_parameters": {
    "operator": "lab-01",
    "recipe": "calcite"
  }
}
```

## Fields

### `injection`

- `on_duration_seconds`: valve open time for one dust injection pulse.
- `off_duration_seconds`: waiting time between pulses.
- `cycles`: number of pulses in one operator-defined cycle; `null` means unlimited until interrupted.
- `mode`: `fixed` for interval injection or `concentration` for target DustTrak control.
- `target_concentration_mg_m3`: target concentration used by concentration mode.
- `cycle_seconds`: full cycle duration.

Legacy keys `duration_seconds`, `interval_seconds`, and `count` are still accepted
and migrated in memory for compatibility with older files.

### `pressure`

- `minimum_bar`: lower allowed pressure limit used by the controller.
- `maximum_bar`: upper allowed pressure limit used by the controller.
- `low_minimum_bar`: lower allowed D2 low-pressure limit.
- `low_maximum_bar`: upper allowed D2 low-pressure limit.

### `user_parameters`

- free-form operator metadata stored as JSON key-value pairs;
- intended for recipe names, operator names, batch ids, and similar simplified runtime context.

## Validation

- injection timings must be positive;
- injection cycles must be greater than zero when provided;
- pressure limits must be non-negative where applicable;
- each minimum pressure limit must be lower than its matching maximum.

## Measurement Archive

Measurement snapshots are appended to `data/measurements/<test_id>.csv` with:

`timestamp`, `test_id`, `pressure_high`, `pressure_low`, `dust_concentration`,
`compressor_state`, `valve_state`, `injection_cycle_id`, `system_state`,
`error_code`.

## Recovery Behavior

- settings are saved atomically;
- on restart the application loads the file before operator work begins;
- if the file does not exist, defaults are created from application bootstrap values.
