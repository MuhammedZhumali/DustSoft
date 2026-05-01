#!/usr/bin/env python3
"""Read Arduino analog telemetry and control Raspberry Pi relay GPIO outputs."""

from __future__ import annotations

import argparse
import re
import sys
import time

READING_PATTERN = re.compile(r"\b(A\d+):(\d+)\b")


def parse_readings(line: str) -> dict[str, int]:
    values = {channel: int(value) for channel, value in READING_PATTERN.findall(line)}
    if not values:
        raise ValueError(f"invalid telemetry line: {line!r}")
    return values


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Control Raspberry Pi relays from Arduino analog readings."
    )
    parser.add_argument("--port", default="/dev/ttyACM0", help="Arduino serial port")
    parser.add_argument("--baudrate", type=int, default=9600, help="Arduino serial baudrate")
    parser.add_argument("--threshold-a0", type=int, default=512, help="Relay 1 ON threshold")
    parser.add_argument("--threshold-a4", type=int, default=None, help="Optional relay 2 ON threshold")
    parser.add_argument("--relay1-gpio", type=int, default=17, help="BCM pin for relay IN1")
    parser.add_argument(
        "--relay2-gpio",
        type=int,
        default=27,
        help="BCM pin for relay IN2; use 18 here if IN2 is wired to GPIO18",
    )
    parser.add_argument("--active-low", action="store_true", help="Use for active-LOW relay boards")
    args = parser.parse_args()

    try:
        import serial
        from gpiozero import OutputDevice
    except ImportError as exc:
        print(
            "Missing dependency. Install with: python3 -m pip install pyserial gpiozero lgpio",
            file=sys.stderr,
        )
        raise SystemExit(2) from exc

    active_high = not args.active_low
    relay1 = OutputDevice(args.relay1_gpio, active_high=active_high, initial_value=False)
    relay2 = OutputDevice(args.relay2_gpio, active_high=active_high, initial_value=False)

    while True:
        try:
            with serial.Serial(args.port, args.baudrate, timeout=2) as ser:
                time.sleep(2)
                print(f"Reading Arduino telemetry from {args.port} at {args.baudrate} baud")
                while True:
                    raw_line = ser.readline().decode("ascii", errors="ignore").strip()
                    if not raw_line:
                        continue
                    readings = parse_readings(raw_line)
                    a0 = readings.get("A0")
                    a4 = readings.get("A4")

                    if a0 is not None:
                        relay1.value = a0 > args.threshold_a0

                    if args.threshold_a4 is not None and a4 is not None:
                        relay2.value = a4 > args.threshold_a4

                    print(
                        f"A0={a0} A4={a4} "
                        f"relay1={'ON' if relay1.value else 'OFF'} "
                        f"relay2={'ON' if relay2.value else 'OFF'}"
                    )
        except KeyboardInterrupt:
            relay1.off()
            relay2.off()
            return 0
        except Exception as exc:
            relay1.off()
            relay2.off()
            print(f"error: {exc}; retrying in 2 seconds", file=sys.stderr)
            time.sleep(2)


if __name__ == "__main__":
    raise SystemExit(main())
