"""Flask entrypoint and route handlers."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import date, timedelta
from pathlib import Path
from typing import Literal

from flask import Flask, abort, redirect, render_template, request, url_for

import data as datamod
import holidays as holmod
import scoring as scoremod
from data import HistoryEntry, Slot

app = Flask(__name__)
app.secret_key = "hymn-planner-local"

REPO_ROOT = Path(__file__).parent

Slot_t = Literal["opening", "sacrament", "intermediate", "closing"]
SLOTS: list[Slot_t] = ["opening", "sacrament", "intermediate", "closing"]

# In-memory pending picks: date -> {slot -> hymn_id}
PENDING_PICKS: dict[date, dict[str, int]] = {}
# In-memory commit warnings: date -> warning message
COMMIT_WARNINGS: dict[date, str] = {}


def _next_sunday_on_or_after(d: date) -> date:
    days_ahead = (6 - d.weekday()) % 7  # isoweekday: Mon=0, Sun=6
    return d + timedelta(days=days_ahead)


def _iter_sundays(from_date: date, count: int) -> list[date]:
    start = _next_sunday_on_or_after(from_date)
    return [start + timedelta(weeks=i) for i in range(count)]


def _default_sunday(history: list[HistoryEntry]) -> date:
    planned_dates = {e.date for e in history}
    for sunday in _iter_sundays(date.today(), 8):
        if sunday not in planned_dates:
            return sunday
    return _next_sunday_on_or_after(date.today())


def _picks_for_date(d: date, history: list[HistoryEntry]) -> dict[str, int]:
    """Return {slot: hymn_id} for the given date, preferring pending picks."""
    if d in PENDING_PICKS:
        return dict(PENDING_PICKS[d])
    return {e.slot: e.hymn_id for e in history if e.date == d}


def _write_history(entries: list[HistoryEntry]) -> None:
    tmp = datamod.HISTORY_JSON.with_suffix(".json.tmp")
    payload = [
        {"date": e.date.isoformat(), "slot": e.slot, "hymn_id": e.hymn_id, "name": e.name}
        for e in entries
    ]
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp, datamod.HISTORY_JSON)


def _try_git_commit(d: date) -> str | None:
    """Attempt git add + commit. Returns an error message on failure, None on success."""
    try:
        subprocess.run(
            ["git", "add", "data/history.json"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", f"Plan for {d.isoformat()}"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
        )
        return None
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        return f"Git commit failed: {exc}"


@app.get("/")
def index():
    history = datamod.load_history()
    sunday = _default_sunday(history)
    return redirect(url_for("plan_view", date_str=sunday.isoformat()))


@app.get("/plan/<date_str>")
def plan_view(date_str: str):
    try:
        ref = date.fromisoformat(date_str)
    except ValueError:
        abort(400, f"Invalid date: {date_str!r}")
    if ref.isoweekday() != 7:
        abort(404, f"{date_str} is not a Sunday.")

    hymns = datamod.load_hymns()
    history = datamod.load_history()
    hymn_map = {h.id: h for h in hymns}

    current_picks = _picks_for_date(ref, history)
    excluded_ids = frozenset(current_picks.values())

    sacrament_ranked = scoremod.score_hymns(
        hymns, history, ref, "sacrament", excluded_ids=excluded_ids
    )[:15]
    general_ranked = scoremod.score_hymns(
        hymns, history, ref, "general", excluded_ids=excluded_ids
    )[:15]

    fast_sunday = holmod.is_fast_sunday(ref)
    holiday = holmod.upcoming_holiday(ref)

    prev_sunday = ref - timedelta(weeks=1)
    next_sunday = ref + timedelta(weeks=1)

    commit_warning = COMMIT_WARNINGS.pop(ref, None)

    return render_template(
        "index.html",
        ref=ref,
        prev_sunday=prev_sunday,
        next_sunday=next_sunday,
        fast_sunday=fast_sunday,
        holiday=holiday,
        sacrament_ranked=sacrament_ranked,
        general_ranked=general_ranked,
        current_picks=current_picks,
        hymn_map=hymn_map,
        slots=SLOTS,
        commit_warning=commit_warning,
    )


@app.post("/confirm/<date_str>")
def confirm(date_str: str):
    try:
        ref = date.fromisoformat(date_str)
    except ValueError:
        abort(400, f"Invalid date: {date_str!r}")

    hymns = datamod.load_hymns()
    hymn_map = {h.id: h for h in hymns}

    picks: dict[str, int] = {}
    for slot in SLOTS:
        raw = request.form.get(slot, "").strip()
        if not raw:
            continue
        try:
            hymn_id = int(raw)
        except ValueError:
            abort(400, f"Invalid hymn id for slot {slot!r}: {raw!r}")
        if hymn_id not in hymn_map:
            abort(400, f"Unknown hymn id {hymn_id} for slot {slot!r}")
        picks[slot] = hymn_id

    history = datamod.load_history()
    retained = [e for e in history if e.date != ref]
    new_entries = [
        HistoryEntry(date=ref, slot=slot, hymn_id=hid, name=hymn_map[hid].name)
        for slot, hid in picks.items()
    ]
    _write_history(retained + new_entries)

    warning = _try_git_commit(ref)
    if warning:
        COMMIT_WARNINGS[ref] = warning

    PENDING_PICKS.pop(ref, None)
    return redirect(url_for("plan_view", date_str=date_str), 303)


@app.get("/holiday-hymns")
def holiday_hymns():
    hymns = datamod.load_hymns()
    hol_hymns = [h for h in hymns if h.is_holiday]
    return render_template("holiday_hymns.html", hymns=hol_hymns)


@app.get("/copy/<date_str>")
def copy_sheet(date_str: str):
    try:
        ref = date.fromisoformat(date_str)
    except ValueError:
        abort(400, f"Invalid date: {date_str!r}")

    hymns = datamod.load_hymns()
    hymn_map = {h.id: h for h in hymns}
    history = datamod.load_history()
    picks = _picks_for_date(ref, history)

    lines = []
    for slot in SLOTS:
        if slot == "intermediate" and slot not in picks:
            continue
        if slot in picks:
            hid = picks[slot]
            name = hymn_map[hid].name if hid in hymn_map else str(hid)
            lines.append(f"{hid} - {name}")

    return "\n".join(lines), 200, {"Content-Type": "text/plain; charset=utf-8"}


if __name__ == "__main__":
    import threading
    import webbrowser

    threading.Timer(1.0, lambda: webbrowser.open("http://localhost:5000")).start()
    app.run(host="127.0.0.1", port=5000, debug=False)
