# Milestones

Progress tracker for building the hymn planner. Check items off as they complete. When starting a new Claude Code session, read `SPEC.md` and this file, then continue with the next unchecked item.

Each milestone should end with a git commit and a quick manual sanity check before moving to the next one.

---

## Milestone 2: Data layer

- [x] `data.py`: load `hymns.csv` into a list of typed records (dataclass or TypedDict). Handle blank `popularity_adjustment` and blank `flagged`.
- [x] `data.py`: load `history.json` into a list of entries. If the file doesn't exist, return an empty list.
- [x] `data.py`: function `last_sung(hymn_id, history, reference_sunday)` → date or None, ignoring entries on `reference_sunday` itself.
- [x] `scripts/import_history.py`: one-time script that reads `history.csv` (MM/DD/YYYY, possibly blank ids) and writes `history.json` (ISO dates, rows with blank ids dropped).
- [x] Run the import once, verify `history.json` has the expected number of rows.
- [x] Unit tests in `tests/test_data.py`.

## Milestone 3: Scoring

- [x] `scoring.py`: pure function that takes `(hymns, history, reference_sunday, pool, config)` and returns a ranked list with intermediate score components. No I/O, no Flask.
- [x] Apply all filters from SPEC section 5.2 (flagged, holiday, pool, popularity floor, cooldown, and excluded-ids for within-Sunday duplicates).
- [x] Implement scoring formula from SPEC section 5.3 with the default config values.
- [x] Unit tests in `tests/test_scoring.py` covering all cases listed in SPEC section 10.
- [x] Sanity check: run the scorer on the real imported history and eyeball the top 20 for `general` pool for the next upcoming Sunday — do the results look reasonable?

## Milestone 4: Holidays module

- [x] `holidays.py`: function `is_fast_sunday(date)` — true if date is the first Sunday of its month.
- [x] `holidays.py`: function `upcoming_holiday(date, window_days=7)` → holiday name or None. Covers Easter, Christmas, Mother's Day, Father's Day, Thanksgiving, 4th of July, New Year's Day.
- [x] Unit tests in `tests/test_holidays.py`.

## Milestone 5: Backend routes

- [x] `app.py`: Flask app with routes for:
  - `GET /` → default planning view (next un-planned Sunday)
  - `GET /plan/<date>` → planning view for a specific Sunday
  - `POST /confirm/<date>` → save picks to history and commit
  - `GET /copy/<date>` → returns the formatted copy-for-sheet text
- [x] Routes should return HTML (Jinja) for page loads and HTML fragments (htmx) or JSON for in-page interactions. Pick one; don't mix.
- [x] Wire up the scoring call, including the "exclude today's picks" logic for within-session de-duplication.

## Milestone 6: Frontend

- [x] `templates/index.html`: layout per SPEC section 6.2 — two ranking columns, current picks area, banner slot, navigation.
- [x] Picking a hymn moves it into the next open slot and removes it from the visible ranking.
- [x] "Swap" action returns a picked hymn to the pool.
- [x] Skip-intermediate toggle disables the intermediate slot.
- [x] Prev/next Sunday navigation + date picker.
- [x] Display `weeks_since` and `length` next to each ranked hymn.
- [x] When navigating to a Sunday with existing history, pre-populate the current picks.

## Milestone 7: Confirm + git

- [ ] On confirm: write `history.json`, then `git add` + `git commit -m "Plan for YYYY-MM-DD"`.
- [ ] If git fails, save still succeeds and the UI shows a non-blocking warning.
- [ ] Overwrite behavior for re-planning a Sunday: remove existing entries for that date, then add the new ones.

## Milestone 8: Polish

- [ ] Fast Sunday banner.
- [ ] Holiday banner with link to the holiday hymns list (read-only view).
- [ ] "Copy for sheet" button produces the formatted text block (section 6.3).
- [ ] `python app.py` opens the browser automatically.
- [ ] Reasonable styling — clean, readable, doesn't need to win awards. Single CSS file, no frameworks.
- [ ] Update `README.md` with a screenshot or two.

---

## Done / shipped

### Milestone 1: Project scaffolding

- [x] Initialize git repo
- [x] Create directory structure per SPEC section 9
- [x] Drop `hymns.csv` and `history.csv` into `data/`
- [x] Record the project's Python dependencies and local launch instructions
- [x] Write a minimal `README.md` with launch instructions
- [x] Confirm `pytest` runs (even with zero tests)

**Deviations from SPEC:**
- Dependencies live in `pyproject.toml` + `uv.lock` (managed by `uv`) instead of the `requirements.txt` shown in SPEC §9.
- SPEC §8's launch command `uv app:app` is not a valid invocation. README documents `uv run flask --app app run` instead. Spec should be corrected before Milestone 8 (browser auto-launch).
