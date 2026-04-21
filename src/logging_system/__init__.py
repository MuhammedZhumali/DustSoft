"""Structured journals for events, alarms, and technical diagnostics."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile


@dataclass(slots=True)
class JournalEntry:
    timestamp: str
    event_type: str
    description: str
    system_snapshot: dict[str, Any]


class JsonLineJournal:
    """Append-only journal stored as JSON lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.channel_name = self.path.name.removesuffix(".jsonl")
        self.archive_dir = self.path.parent / "history" / self.channel_name

    def append(self, entry: JournalEntry) -> JournalEntry:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        line = json.dumps(asdict(entry), ensure_ascii=True, sort_keys=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        with self._daily_path(entry.timestamp).open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        return entry

    def read_all(self) -> list[JournalEntry]:
        files = self.list_files(include_current_fallback=True)
        entries: list[JournalEntry] = []
        for file_path in files:
            with file_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    payload = json.loads(line)
                    entries.append(JournalEntry(**payload))
        return entries

    def list_files(self, *, include_current_fallback: bool = False) -> list[Path]:
        archived = sorted(self.archive_dir.glob("*.jsonl")) if self.archive_dir.exists() else []
        if archived:
            return archived
        if include_current_fallback and self.path.exists():
            return [self.path]
        return []

    def _daily_path(self, timestamp: str) -> Path:
        day = timestamp.split("T", 1)[0]
        return self.archive_dir / f"{day}.jsonl"


class JournalService:
    """High-level API over event, alarm, and technical journals."""

    def __init__(
        self,
        *,
        event_journal: JsonLineJournal,
        alarm_journal: JsonLineJournal,
        technical_journal: JsonLineJournal,
    ) -> None:
        self.event_journal = event_journal
        self.alarm_journal = alarm_journal
        self.technical_journal = technical_journal

    def log_event(
        self,
        *,
        event_type: str,
        description: str,
        system_snapshot: dict[str, Any],
    ) -> JournalEntry:
        return self.event_journal.append(
            self._entry(
                event_type=event_type,
                description=description,
                system_snapshot=system_snapshot,
            )
        )

    def log_alarm(
        self,
        *,
        event_type: str,
        description: str,
        system_snapshot: dict[str, Any],
    ) -> JournalEntry:
        return self.alarm_journal.append(
            self._entry(
                event_type=event_type,
                description=description,
                system_snapshot=system_snapshot,
            )
        )

    def log_technical(
        self,
        *,
        event_type: str,
        description: str,
        system_snapshot: dict[str, Any],
    ) -> JournalEntry:
        return self.technical_journal.append(
            self._entry(
                event_type=event_type,
                description=description,
                system_snapshot=system_snapshot,
            )
        )

    def export_archive(self, destination_dir: str | Path) -> Path:
        destination = Path(destination_dir)
        destination.mkdir(parents=True, exist_ok=True)
        archive_path = destination / (
            f"logs-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.zip"
        )

        with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as zip_file:
            for journal in (
                self.event_journal,
                self.alarm_journal,
                self.technical_journal,
            ):
                if journal.path.exists():
                    zip_file.write(journal.path, arcname=journal.path.name)
                for file_path in journal.list_files():
                    zip_file.write(
                        file_path,
                        arcname=str(Path("history") / journal.channel_name / file_path.name),
                    )

        return archive_path

    @staticmethod
    def _entry(
        *,
        event_type: str,
        description: str,
        system_snapshot: dict[str, Any],
    ) -> JournalEntry:
        return JournalEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=event_type,
            description=description,
            system_snapshot=system_snapshot,
        )
