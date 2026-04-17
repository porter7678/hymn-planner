"""Tests for data.py."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from textwrap import dedent

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from data import HistoryEntry, Hymn, last_sung, load_history, load_hymns
from import_history import import_history


HYMNS_CSV_HEADER = "id,name,count,length,popularity,popularity_adjustment,flagged,is_sacrament,is_general,is_holiday\n"


def _write_hymns_csv(path: Path, body: str) -> None:
    path.write_text(HYMNS_CSV_HEADER + dedent(body).lstrip())


class TestLoadHymns:
    def test_blank_popularity_adjustment_becomes_none(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "hymns.csv"
        _write_hymns_csv(csv_path, "2,The Spirit of God,374,5:55,9,,1,0,1,0\n")

        [hymn] = load_hymns(csv_path)

        assert hymn.popularity_adjustment is None

    def test_numeric_popularity_adjustment_parses(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "hymns.csv"
        _write_hymns_csv(csv_path, "1,The Morning Breaks,100,3:55,5,2,,0,1,0\n")

        [hymn] = load_hymns(csv_path)

        assert hymn.popularity_adjustment == 2

    def test_flagged_blank_is_false_and_one_is_true(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "hymns.csv"
        _write_hymns_csv(
            csv_path,
            """\
            1,The Morning Breaks,100,3:55,5,2,,0,1,0
            2,The Spirit of God,374,5:55,9,,1,0,1,0
            """,
        )

        morning, spirit = load_hymns(csv_path)

        assert morning.flagged is False
        assert spirit.flagged is True

    def test_pool_and_holiday_flags_parse(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "hymns.csv"
        _write_hymns_csv(
            csv_path,
            """\
            171,With Humble Heart,100,3:00,8,,,1,0,0
            100,Christmas Bells,50,2:30,7,,,0,0,1
            """,
        )

        sacrament, holiday = load_hymns(csv_path)

        assert sacrament.is_sacrament is True
        assert sacrament.is_general is False
        assert sacrament.is_holiday is False
        assert holiday.is_holiday is True
        assert holiday.is_sacrament is False
        assert holiday.is_general is False

    def test_count_column_is_ignored(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "hymns.csv"
        _write_hymns_csv(csv_path, "1,The Morning Breaks,100,3:55,5,2,,0,1,0\n")

        [hymn] = load_hymns(csv_path)

        assert not hasattr(hymn, "count")
        assert hymn.id == 1
        assert hymn.name == "The Morning Breaks"
        assert hymn.length == "3:55"
        assert hymn.popularity == 5


class TestLoadHistory:
    def test_missing_file_returns_empty_list(self, tmp_path: Path) -> None:
        assert load_history(tmp_path / "does_not_exist.json") == []

    def test_round_trip_parses_iso_dates(self, tmp_path: Path) -> None:
        json_path = tmp_path / "history.json"
        json_path.write_text(
            json.dumps(
                [
                    {"date": "2026-04-19", "slot": "opening", "hymn_id": 85, "name": "How Firm a Foundation"},
                    {"date": "2026-04-19", "slot": "sacrament", "hymn_id": 177, "name": "'Tis Sweet"},
                ]
            )
        )

        entries = load_history(json_path)

        assert entries == [
            HistoryEntry(date=date(2026, 4, 19), slot="opening", hymn_id=85, name="How Firm a Foundation"),
            HistoryEntry(date=date(2026, 4, 19), slot="sacrament", hymn_id=177, name="'Tis Sweet"),
        ]


class TestLastSung:
    @pytest.fixture
    def history(self) -> list[HistoryEntry]:
        return [
            HistoryEntry(date=date(2025, 1, 5), slot="opening", hymn_id=85, name="How Firm a Foundation"),
            HistoryEntry(date=date(2025, 6, 15), slot="closing", hymn_id=85, name="How Firm a Foundation"),
            HistoryEntry(date=date(2026, 4, 19), slot="opening", hymn_id=85, name="How Firm a Foundation"),
            HistoryEntry(date=date(2025, 3, 2), slot="sacrament", hymn_id=177, name="'Tis Sweet"),
        ]

    def test_returns_most_recent_match(self, history: list[HistoryEntry]) -> None:
        assert last_sung(85, history, date(2027, 1, 1)) == date(2026, 4, 19)

    def test_never_sung_returns_none(self, history: list[HistoryEntry]) -> None:
        assert last_sung(999, history, date(2026, 4, 19)) is None

    def test_ignores_entries_on_reference_sunday(self, history: list[HistoryEntry]) -> None:
        # Hymn 85 was "sung" on 2026-04-19 in history, but when planning that same
        # Sunday we must ignore it — otherwise re-planning excludes today's picks.
        assert last_sung(85, history, date(2026, 4, 19)) == date(2025, 6, 15)


class TestImportHistory:
    def test_converts_dates_drops_blank_ids_and_populates_names(self, tmp_path: Path) -> None:
        hymns_csv = tmp_path / "hymns.csv"
        _write_hymns_csv(
            hymns_csv,
            """\
            85,How Firm a Foundation,100,3:55,8,,,0,1,0
            177,'Tis Sweet to Sing the Matchless Love,50,2:30,9,,,1,0,0
            """,
        )
        history_csv = tmp_path / "history.csv"
        history_csv.write_text(
            "date,slot,id,name\n"
            "1/1/2023,opening,85,\n"
            "1/1/2023,sacrament,177,\n"
            "1/1/2023,intermediate,,\n"
            "12/31/2024,closing,85,\n"
        )
        out_json = tmp_path / "history.json"

        n = import_history(history_csv, hymns_csv, out_json)

        assert n == 3
        assert json.loads(out_json.read_text()) == [
            {"date": "2023-01-01", "slot": "opening", "hymn_id": 85, "name": "How Firm a Foundation"},
            {"date": "2023-01-01", "slot": "sacrament", "hymn_id": 177, "name": "'Tis Sweet to Sing the Matchless Love"},
            {"date": "2024-12-31", "slot": "closing", "hymn_id": 85, "name": "How Firm a Foundation"},
        ]
