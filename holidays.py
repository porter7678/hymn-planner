"""Fast Sunday and holiday-window detection."""

from __future__ import annotations

from datetime import date, timedelta


def _easter(year: int) -> date:
    # Anonymous Gregorian algorithm (Meeus/Jones/Butcher)
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def _nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> date:
    # weekday: 0=Mon … 6=Sun; n: 1-indexed
    d = date(year, month, 1)
    offset = (weekday - d.weekday()) % 7
    return d + timedelta(days=offset + 7 * (n - 1))


def _fixed(month: int, day: int):
    def _fn(year: int) -> date:
        return date(year, month, day)
    return _fn


# Registry: list of (display_name, year -> date).
# Add or remove holidays here.
_HOLIDAYS: list[tuple[str, object]] = [
    ("New Year's Day", _fixed(1, 1)),
    ("Easter", _easter),
    ("Mother's Day", lambda y: _nth_weekday_of_month(y, 5, 6, 2)),
    ("Father's Day", lambda y: _nth_weekday_of_month(y, 6, 6, 3)),
    ("4th of July", _fixed(7, 4)),
    ("Thanksgiving", lambda y: _nth_weekday_of_month(y, 11, 3, 4)),
    ("Christmas", _fixed(12, 25)),
]


def is_fast_sunday(d: date) -> bool:
    return d.isoweekday() == 7 and d.day <= 7


def upcoming_holiday(d: date, window_days: int = 7) -> str | None:
    best_name: str | None = None
    best_dist = window_days + 1

    for name, fn in _HOLIDAYS:
        for year in (d.year - 1, d.year, d.year + 1):
            candidate: date = fn(year)  # type: ignore[operator]
            dist = abs((candidate - d).days)
            if dist <= window_days and dist < best_dist:
                best_dist = dist
                best_name = name

    return best_name
