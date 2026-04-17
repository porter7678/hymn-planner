# Hymn Planner — Design Spec

## 1. Purpose

A small local web app that helps me plan the hymns for each Sunday's sacrament meeting in my LDS congregation. I'm the only user.

Each Sunday has four slots: **opening**, **sacrament**, **intermediate** (sometimes skipped), and **closing**. The app ranks eligible hymns for each slot based on popularity and how long it's been since each hymn was last sung, and I make the final pick. It then records my choices to a local history file, commits them to git, and gives me a formatted block of text I can paste into a shared Google Sheet.

## 2. Non-Goals

To keep scope sharp, the app explicitly does **not**:

- Run as a hosted service or mobile app. It's a local Python process I launch at my desk.
- Auto-pick hymns without my confirmation. It ranks; I choose.
- Support multiple users, auth, or concurrent editing.
- Sync to or read from the shared Google Sheet directly. I copy-paste.
- Provide an in-app editor for `hymns.csv` or `history.json`. I edit those files directly in a text editor when needed.
- Handle holiday hymn selection automatically. For holiday weeks, I hand-pick; the app just shows a banner reminder.

## 3. Tech Stack

- **Language:** Python 3.11+
- **Backend:** Flask (lightweight, good for server-rendered HTML with a sprinkle of JS). FastAPI is an acceptable alternative.
- **Frontend:** Jinja templates for page rendering; htmx for in-page interactions (picking, toggling, swapping). If htmx feels like too much ceremony, vanilla JS is fine — no React/Vue/etc.
- **Data storage:** `hymns.csv` (read-only source of truth for hymn metadata) and `history.json` (append-mostly log of what's been planned/sung).
- **Dependencies:** Keep minimal. Expected: `flask`, `pytest`, `uv`. No `pandas`/`polars` — the dataset is ~400 rows, plain Python dicts/lists are plenty.
- **Version control:** git. The app auto-commits `history.json` on confirm.

## 4. Data Model

### 4.1 `hymns.csv` (read-only input)

Columns:

- `id` — integer, unique hymn id. Can exceed 1000 (newer hymnal releases).
- `name` — display name.
- `count` — **ignore.** Historical input used to derive `popularity`; no longer meaningful.
- `length` — string like `"3:55"`. Display only; does not affect scoring.
- `popularity` — integer 1–10.
- `popularity_adjustment` — integer, possibly null/blank. Added to `popularity`.
- `flagged` — `1` if I never want this hymn suggested; blank otherwise.
- `is_sacrament` — `1` if eligible for the sacrament slot.
- `is_general` — `1` if eligible for opening/intermediate/closing slots.
- `is_holiday` — `1` if the hymn should only surface on holiday weeks. Mutually exclusive with the other two in practice, and `is_holiday` hymns are **hidden from normal suggestions** entirely.

Flags are not strictly mutually exclusive: a hymn can be both `is_sacrament` and `is_general` (rare but happens).

### 4.2 `history.csv` (seed data — imported once)

Columns: `date` (MM/DD/YYYY), `slot`, `id`, `name`.

Used only for the initial import into `history.json`. After import, this file is no longer read.

### 4.3 `history.json` (live history)

The app's source of truth for what's been planned/sung. A list of objects:

```json
[
  { "date": "2026-04-19", "slot": "opening", "hymn_id": 85, "name": "How Firm a Foundation" },
  { "date": "2026-04-19", "slot": "sacrament", "hymn_id": 177, "name": "'Tis Sweet to Sing the Matchless Love" },
  { "date": "2026-04-19", "slot": "closing", "hymn_id": 117, "name": "Come, unto Jesus" }
]
```

Rules:

- Dates are ISO format (`YYYY-MM-DD`).
- A skipped intermediate means **no row exists** for that (date, "intermediate") pair.
- "Planned" and "sung" are the same thing — no status field. If a planned hymn wasn't actually sung, I edit `history.json` manually.
- `name` is included for readability when editing the file directly. Hymns are assumed never to be renamed, so no drift concern.
- Scoring and lookups use `hymn_id` as the authoritative key; `name` is display-only.

## 5. Scoring Algorithm

This is the brain of the app. It runs once per slot-pool for a given target Sunday.

### 5.1 Inputs

- `reference_sunday`: the Sunday being planned (a date). **All recency math is computed relative to this date, not "today"**, so planning four weeks out still ranks hymns correctly.
- `pool`: either `"sacrament"` or `"general"` (the latter serves opening/intermediate/closing).
- `history`: the current `history.json` contents.
- Config (defaults below, but configurable in one place):
  - `popularity_weight = 0.7`
  - `noise_amplitude = 0.15`
  - `cooldown_weeks = 8`
  - `recency_cap_weeks = 52`
  - `sigmoid_midpoint = 7`
  - `sigmoid_slope = 2`

### 5.2 Filters (hard exclusions)

A hymn is excluded from the rankings if any of the following hold:

1. `flagged == 1`.
2. `is_holiday == 1` (holiday hymns never appear in normal rankings).
3. The hymn does not belong to the requested pool (`is_sacrament != 1` for the sacrament pool; `is_general != 1` for the general pool).
4. `weeks_since <= cooldown_weeks`, where `weeks_since = (reference_sunday - last_sung_date).days // 7`. If the hymn has never been sung, treat `weeks_since` as effectively infinite (use `recency_cap_weeks` directly).

There is no hard popularity floor. Low-popularity hymns are suppressed naturally by the sigmoid — a hymn with `adj_popularity` of 4 scores ~0.02 on the popularity component, making it vanishingly unlikely to surface in the top 10–20. This is intentional: the sigmoid does the work without a hard cutoff.

**Edge case:** when computing `last_sung_date` for scoring, ignore any history entries for `reference_sunday` itself. Otherwise re-planning a Sunday would see that day's current picks as "just sung" and exclude them.

**Edge case:** hymns already placed into other slots on `reference_sunday` during the current planning session are also filtered out (no duplicates within a Sunday).

### 5.3 Scoring

For each surviving hymn:

```
adj_popularity   = popularity + (popularity_adjustment or 0)
popularity_score = 1 / (1 + exp(-sigmoid_slope * (adj_popularity - sigmoid_midpoint)))
                   # centered at popularity 7, range (0, 1)
recency_score    = min(weeks_since, recency_cap_weeks) / recency_cap_weeks
                   # linear ramp, capped at 1.0 after ~1 year
noise            = uniform(-noise_amplitude, +noise_amplitude)
score            = popularity_weight * popularity_score
                 + (1 - popularity_weight) * recency_score
                 + noise
```

Rankings are returned sorted by `score` descending. The UI surfaces the top 10–20.

### 5.4 Notes on this formula vs. the prior draft

- Both components are now on a [0, 1] scale (the prior draft had recency topping out at 2.0, which silently made it heavier than popularity at the nominal 50/50 weight).
- Cooldown is a hard filter instead of a `-100` penalty; easier to explain in the UI ("12 hymns in cooldown, 289 eligible").
- The popularity sigmoid shape is unchanged — aggressive, centered at 7. This is intentional.
- There is no hard popularity floor; the sigmoid naturally suppresses low-popularity hymns without a sharp cutoff.
- Default `popularity_weight = 0.7` and `noise_amplitude = 0.15` match prior preference.

### 5.5 Intermediate values to expose

The scoring function should return not just the ranked ids, but also the intermediate components per hymn: `weeks_since`, `adj_popularity`, `popularity_score`, `recency_score`, `score`. The UI displays at least `weeks_since` next to each suggestion (it's genuinely useful context when picking).

## 6. Planning Flow / UI

### 6.1 Default view on launch

When the app starts, the default page is the **next Sunday that has no hymns planned yet**. If every Sunday in the next 8 weeks already has plans, default to the next upcoming Sunday regardless.

### 6.2 Single-page layout for one Sunday

```
┌─────────────────────────────────────────────────────────┐
│  [◀ prev Sunday]  Sunday, April 26, 2026  [next ▶]     │
│  ⚠ First Sunday of the month — Fast Sunday             │  (banner appears only when relevant)
├─────────────────────────────────────────────────────────┤
│  Sacrament (pick 1)    │  General (pick 2 or 3)        │
│  ─────────────────     │  ─────────────────            │
│  171  With Humble Heart     (42 wks)                    │
│  177  'Tis Sweet to Sing... (31 wks)                    │
│  ...                   │  66  Rejoice, the Lord is King (19 wks)
│                        │  85  How Firm a Foundation    (26 wks)
│                        │  ...                           │
├─────────────────────────────────────────────────────────┤
│  Your picks:                                            │
│    Opening:      85 — How Firm a Foundation     [swap] │
│    Sacrament:    177 — 'Tis Sweet...             [swap] │
│    Intermediate: ☐ skip  |  (none picked)        [pick] │
│    Closing:      66 — Rejoice, the Lord is King  [swap] │
├─────────────────────────────────────────────────────────┤
│  [ Confirm & commit ]   [ Copy for sheet ]              │
└─────────────────────────────────────────────────────────┘
```

### 6.3 Interactions

- **Navigation.** Prev/next Sunday buttons, plus a date picker for jumping.
- **Picking.** Clicking a hymn in either ranking assigns it to the next empty slot (sacrament → sacrament slot; general → next empty of opening/intermediate/closing). Once picked, the hymn is removed from the visible rankings.
- **Swapping.** Each picked slot has a "swap" action that returns the current pick to the pool and clears that slot.
- **Intermediate toggle.** A "skip intermediate" checkbox. When checked, the intermediate slot is disabled; I only pick 2 hymns from the general pool. When unchecked, I pick 3.
- **Re-planning a Sunday with existing history.** If I navigate to a Sunday that already has entries in `history.json`, the existing picks are shown as the current picks. I can swap any or all of them. On confirm, the app overwrites that Sunday's entries.
- **Confirm.** Writes to `history.json`, then runs git add + git commit.
- **Copy for sheet.** Produces a four-line block I can paste into my shared Google Sheet:
  ```
  85 - How Firm a Foundation
  177 - 'Tis Sweet to Sing the Matchless Love
  (intermediate skipped → line omitted, or left blank — TBD, pick the one my sheet prefers)
  66 - Rejoice, the Lord is King
  ```
  When an intermediate is skipped, **omit the line entirely** (so the block has 3 lines, not 4 with a blank).

### 6.4 Banners

Shown at the top of the planning page, above the rankings:

- **Fast Sunday** — displayed when the reference Sunday is the first Sunday of its calendar month.
- **Holiday** — displayed when the reference Sunday is within 7 days of a holiday. The initial holiday list: Easter, Christmas (Dec 24 or 25), Mother's Day (2nd Sunday of May), Father's Day (3rd Sunday of June), Thanksgiving (4th Thursday of November), 4th of July, New Year's Day. The banner names the holiday and links to a read-only list of `is_holiday` hymns so I can hand-pick.

The list of holidays should live in one small module/config so it's trivial to add or remove.

## 7. Git Integration

On confirm:

1. Write updated `history.json`.
2. Run `git add history.json`.
3. Run `git commit -m "Plan for YYYY-MM-DD"` (where the date is the reference Sunday).
4. If git commit fails (no changes, no git user configured, not in a repo), the save to `history.json` still succeeds; the UI shows a non-blocking warning noting the commit did not happen.

No automatic `git push`. If I want offsite backup, I configure a remote and push manually (or set up a cron, but that's out of scope).

## 8. Launch

`uv app:app` starts the Flask server on `localhost:5000` and opens the default browser to that URL. Ctrl+C stops it.

No config needed beyond having `hymns.csv` and `history.json` present in the expected location.

## 9. Suggested File Structure

```
hymn-planner/
├── SPEC.md
├── MILESTONES.md
├── CLAUDE.md
├── README.md
├── app.py                 # Flask entrypoint + routes
├── scoring.py             # Pure scoring logic (no I/O)
├── data.py                # Load hymns.csv + history.json; last_sung computation
├── holidays.py            # Fast Sunday + holiday detection
├── requirements.txt
├── data/
│   ├── hymns.csv
│   ├── history.csv        # seed only; not read after import
│   └── history.json
├── scripts/
│   └── import_history.py  # one-time: history.csv → history.json
├── templates/
│   └── index.html
├── static/
│   └── ...
└── tests/
    ├── test_scoring.py
    ├── test_data.py
    └── test_holidays.py
```

`scoring.py` should be a pure module — takes data in, returns rankings, no file I/O or Flask imports. This makes it easy to test and easy to reason about.

## 10. Testing

Required:

- Unit tests for `scoring.py` covering: cooldown filter, popularity floor, sigmoid shape at a few known values, recency normalization, noise respecting the amplitude bound, handling of never-sung hymns, handling of the "ignore today's picks when planning today" edge case.
- Unit tests for `data.py` covering: loading `hymns.csv` with messy values (blank `popularity_adjustment`, blank `flagged`), computing `last_sung` from history, and the history import script's date parsing.
- Unit tests for `holidays.py` covering: Fast Sunday on the first of each month, known Easter dates for 2024–2027, Mother's/Father's Day computation.

Not required (too costly for the value): end-to-end UI tests, Flask route integration tests.

## 11. Open Questions (future, not blocking v1)

- In-app editor for `hymns.csv` (flip `flagged`, tweak `popularity_adjustment`, add a newly released hymn).
- In-app history editor (edit/delete a past row without opening the JSON file).
- Theme-based suggestions (e.g., "show me hymns about gratitude for a Thanksgiving-themed sacrament meeting").
- Stake/general conference weeks (where the hymn pattern changes or is skipped entirely).
- Cloud backup beyond local git (push to a private GitHub repo on confirm, authenticated via a local token).

These are captured here so they don't clutter the v1 build.
