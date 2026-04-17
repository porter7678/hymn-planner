"""Tests for holidays.py."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from holidays import is_fast_sunday, upcoming_holiday, _easter, _nth_weekday_of_month


class TestIsFastSunday:
    @pytest.mark.parametrize("d", [
        date(2026, 1, 4),   # first Sunday of January
        date(2026, 2, 1),
        date(2026, 3, 1),
        date(2026, 4, 5),
        date(2026, 5, 3),
        date(2026, 6, 7),
        date(2026, 7, 5),
        date(2026, 8, 2),
        date(2026, 9, 6),
        date(2026, 10, 4),
        date(2026, 11, 1),
        date(2026, 12, 6),
    ])
    def test_first_sunday_of_month(self, d: date) -> None:
        assert is_fast_sunday(d) is True

    def test_second_sunday_is_not_fast(self) -> None:
        assert is_fast_sunday(date(2026, 4, 12)) is False

    def test_weekday_on_first_is_not_fast(self) -> None:
        # April 1 2026 is a Wednesday
        assert is_fast_sunday(date(2026, 4, 1)) is False


class TestEaster:
    @pytest.mark.parametrize("year,expected", [
        (2024, date(2024, 3, 31)),
        (2025, date(2025, 4, 20)),
        (2026, date(2026, 4, 5)),
        (2027, date(2027, 3, 28)),
    ])
    def test_known_easter_dates(self, year: int, expected: date) -> None:
        assert _easter(year) == expected


class TestNthWeekday:
    def test_mothers_day_2025(self) -> None:
        # 2nd Sunday of May 2025
        assert _nth_weekday_of_month(2025, 5, 6, 2) == date(2025, 5, 11)

    def test_mothers_day_2026(self) -> None:
        assert _nth_weekday_of_month(2026, 5, 6, 2) == date(2026, 5, 10)

    def test_fathers_day_2025(self) -> None:
        # 3rd Sunday of June 2025
        assert _nth_weekday_of_month(2025, 6, 6, 3) == date(2025, 6, 15)

    def test_fathers_day_2026(self) -> None:
        assert _nth_weekday_of_month(2026, 6, 6, 3) == date(2026, 6, 21)

    def test_thanksgiving_2025(self) -> None:
        # 4th Thursday of November 2025
        assert _nth_weekday_of_month(2025, 11, 3, 4) == date(2025, 11, 27)

    def test_thanksgiving_2026(self) -> None:
        assert _nth_weekday_of_month(2026, 11, 3, 4) == date(2026, 11, 26)


class TestUpcomingHoliday:
    def test_easter_on_the_day(self) -> None:
        assert upcoming_holiday(date(2026, 4, 5)) == "Easter"

    def test_easter_six_days_before(self) -> None:
        assert upcoming_holiday(date(2026, 3, 30)) == "Easter"

    def test_outside_window_returns_none(self) -> None:
        # April 5 2026 is Easter; April 13 is 8 days later — outside default window
        assert upcoming_holiday(date(2026, 4, 13)) is None

    def test_new_years_from_prior_year(self) -> None:
        # Dec 25 is Christmas; Dec 26 is 6 days before Jan 1.
        # Dec 26 2026 is a Saturday — not used for planning but tests year-boundary logic.
        # Use Dec 28 2026 (Sunday, 4 days before Jan 1 2027).
        result = upcoming_holiday(date(2026, 12, 28))
        # Christmas (Dec 25) is 3 days away; New Year's is 4 days away — Christmas wins.
        assert result == "Christmas"

    def test_new_years_day_only_in_window(self) -> None:
        # Dec 29 2025: 3 days from Jan 1 2026, Christmas is 4 days back
        result = upcoming_holiday(date(2025, 12, 29))
        assert result == "New Year's Day"

    def test_christmas_three_days_before(self) -> None:
        assert upcoming_holiday(date(2026, 12, 22)) == "Christmas"

    def test_custom_window(self) -> None:
        # 8 days before Easter 2026 — outside default 7-day window but inside 10
        assert upcoming_holiday(date(2026, 3, 28), window_days=10) == "Easter"
        assert upcoming_holiday(date(2026, 3, 28), window_days=7) is None
