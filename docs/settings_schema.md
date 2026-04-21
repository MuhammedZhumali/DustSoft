# Settings Schema

DustSoft stores persistent settings in `data/settings.json`.

## Structure

```json
{
  "injection": {
    "duration_seconds": 0.1,
    "interval_seconds": 5.0,
    "count": 1,
    "cycle_seconds": 30.0
  },
  "pressure": {
    "minimum_bar": 4.0,
    "maximum_bar": 8.0
  },
  "user_parameters": {
    "operator": "lab-01",
    "recipe": "calcite"
  }
}
```

## Fields

### `injection`

- `duration_seconds`: valve open time for one dust injection pulse.
- `interval_seconds`: waiting time between pulses.
- `count`: number of pulses in one operator-defined cycle.
- `cycle_seconds`: full cycle duration.

### `pressure`

- `minimum_bar`: lower allowed pressure limit used by the controller.
- `maximum_bar`: upper allowed pressure limit used by the controller.

### `user_parameters`

- free-form operator metadata stored as JSON key-value pairs;
- intended for recipe names, operator names, batch ids, and similar simplified runtime context.

## Validation

- injection timings must be positive;
- injection count must be greater than zero;
- pressure limits must be positive;
- `minimum_bar` must be lower than `maximum_bar`.

## Recovery Behavior

- settings are saved atomically;
- on restart the application loads the file before operator work begins;
- if the file does not exist, defaults are created from application bootstrap values.
