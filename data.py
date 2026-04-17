"""CSV/JSON loading and last_sung computation."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

DATA_DIR = Path(__file__).parent / "data"
HYMNS_CSV = DATA_DIR / "hymns.csv"
HISTORY_JSON = DATA_DIR / "history.json"

Slot = Literal["opening", "sacrament", "intermediate", "closing"]


@dataclass(frozen=True)
class Hymn:
    id: int
    name: str
    length: str
    popularity: int
    popularity_adjustment: int | None
    flagged: bool
    is_sacrament: bool
    is_general: bool
    is_holiday: bool


@dataclass(frozen=True)
class HistoryEntry:
    date: date
    slot: Slot
    hymn_id: int
    name: str


def _flag(value: str) -> bool:
    return value.strip() == "1"


def _optional_int(value: str) -> int | None:
    stripped = value.strip()
    return int(stripped) if stripped else None


def load_hymns(path: Path = HYMNS_CSV) -> list[Hymn]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [
            Hymn(
                id=int(row["id"]),
                name=row["name"],
                length=row["length"],
                popularity=int(row["popularity"]),
                popularity_adjustment=_optional_int(row["popularity_adjustment"]),
                flagged=_flag(row["flagged"]),
                is_sacrament=_flag(row["is_sacrament"]),
                is_general=_flag(row["is_general"]),
                is_holiday=_flag(row["is_holiday"]),
            )
            for row in reader
        ]


def load_history(path: Path = HISTORY_JSON) -> list[HistoryEntry]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return [
        HistoryEntry(
            date=date.fromisoformat(entry["date"]),
            slot=entry["slot"],
            hymn_id=entry["hymn_id"],
            name=entry["name"],
        )
        for entry in raw
    ]


def last_sung(
    hymn_id: int,
    history: list[HistoryEntry],
    reference_sunday: date,
) -> date | None:
    dates = [
        e.date
        for e in history
        if e.hymn_id == hymn_id and e.date != reference_sunday
    ]
    return max(dates) if dates else None
