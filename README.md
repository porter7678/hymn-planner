# hymn-planner

A local web app for planning LDS sacrament meeting hymns. Ranks eligible hymns by popularity and recency, lets you pick from the suggestions, and records confirmed selections to a local history file with an automatic git commit.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)

## Run

```sh
uv run python app.py
```

Opens `http://localhost:5000` in your default browser automatically. `Ctrl+C` to stop.

Alternatively, to start without auto-opening the browser:

```sh
uv run flask --app app run
```

## Usage

1. The app opens to the next Sunday that has no hymns planned yet.
2. Click any hymn in the **Sacrament** or **General** ranking to assign it to the next empty slot.
3. Use **swap** to return a pick to the pool, or **skip** to disable the intermediate slot.
4. Click **Confirm & commit** to save picks to `data/history.json` and auto-commit via git.
5. Click **Copy for sheet** to copy the formatted hymn block to your clipboard for pasting into the shared Google Sheet.

Banners appear automatically for **Fast Sunday** (first Sunday of the month) and **Holiday weeks** (within 7 days of Easter, Christmas, Mother's Day, etc.). The holiday banner links to a read-only list of holiday hymns for hand-picking.

## Data files

| File | Purpose |
|---|---|
| `data/hymns.csv` | Read-only hymn metadata (popularity, eligibility flags) |
| `data/history.json` | Live history of planned hymns — updated on each confirm |

Edit these files directly in a text editor when needed (e.g., to flag a hymn, adjust popularity, or fix a history entry).
