"""Persistent settings storage for DustSoft."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


@dataclass(slots=True)
class InjectionSettings:
    duration_seconds: float = 1.0
    interval_seconds: float = 5.0
    count: int = 1
    cycle_seconds: float = 5.0


@dataclass(slots=True)
class PressureSettings:
    minimum_bar: float = 0.8
    maximum_bar: float = 1.5


@dataclass(slots=True)
class SettingsBundle:
    injection: InjectionSettings = field(default_factory=InjectionSettings)
    pressure: PressureSettings = field(default_factory=PressureSettings)
    user_parameters: dict[str, Any] = field(default_factory=dict)


class JsonSettingsStorage:
    """Persist settings to a JSON file with atomic replacement."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> SettingsBundle:
        if not self.path.exists():
            return SettingsBundle()

        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return SettingsBundle(
            injection=InjectionSettings(**payload.get("injection", {})),
            pressure=PressureSettings(**payload.get("pressure", {})),
            user_parameters=dict(payload.get("user_parameters", {})),
        )

    def save(self, settings: SettingsBundle) -> SettingsBundle:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(asdict(settings), ensure_ascii=True, indent=2, sort_keys=True)

        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            delete=False,
            dir=self.path.parent,
            prefix=f"{self.path.stem}-",
            suffix=".tmp",
        ) as handle:
            handle.write(serialized)
            temp_path = Path(handle.name)

        temp_path.replace(self.path)
        return settings
