"""One-time import of history.csv into history.json."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def import_history(
    history_csv: Path = DATA_DIR / "history.csv",
    hymns_csv: Path = DATA_DIR / "hymns.csv",
    out_json: Path = DATA_DIR / "history.json",
) -> int:
    names_by_id = _load_hymn_names(hymns_csv)

    entries: list[dict] = []
    with open(history_csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            raw_id = row["id"].strip()
            if not raw_id:
                continue
            hymn_id = int(raw_id)
            iso_date = datetime.strptime(row["date"].strip(), "%m/%d/%Y").date().isoformat()
            entries.append(
                {
                    "date": iso_date,
                    "slot": row["slot"].strip(),
                    "hymn_id": hymn_id,
                    "name": names_by_id.get(hymn_id, ""),
                }
            )

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)
        f.write("\n")

    return len(entries)


def _load_hymn_names(hymns_csv: Path) -> dict[int, str]:
    with open(hymns_csv, newline="", encoding="utf-8") as f:
        return {int(row["id"]): row["name"] for row in csv.DictReader(f)}


if __name__ == "__main__":
    n = import_history()
    print(f"Wrote {n} history entries")
