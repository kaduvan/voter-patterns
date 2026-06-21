#!/usr/bin/env python3
"""
Parse booth-AC018-2026.xlsx into a clean per-booth CSV.

AC018 = Harbour constituency, Chennai Central PC. The xlsx is the ECI
"List of Polling Stations" — a 5-col table (Part No, PS NO, Location+building,
Polling Area streets, Voter Type) with a title row, a header row, and a
column-number sub-header (1,2,3,4,5) that REPEATS on every page break.

We discard the repeats and the page-break noise, extract the pincode from the
location string, and emit one row per Part (the unit that matches the voter-roll
demographics via booth_number = Part No = the `-TAM-{N}-WI.pdf` suffix).

Output: data/booths_ac018.csv
"""
import csv
import re
import sys
from pathlib import Path

import openpyxl

BASE = Path(__file__).resolve().parent.parent
SRC = BASE / "analysis" / "booth-AC018-2026.xlsx"
OUT = BASE / "data" / "booths_ac018.csv"


def clean(x) -> str:
    return re.sub(r"\s+", " ", str(x or "")).strip()


def main() -> int:
    if not SRC.exists():
        print(f"ERROR: {SRC} not found", file=sys.stderr)
        return 1

    wb = openpyxl.load_workbook(SRC, data_only=True)
    ws = wb["Table 1"]

    rows, seen = [], set()
    for r in ws.iter_rows(values_only=True):
        # Must have numeric Part No AND PS NO — this drops title/header/sub-header.
        try:
            part_no, ps_no = int(r[0]), int(r[1])
        except (TypeError, ValueError):
            continue
        location = clean(r[2])
        # Drop the repeating column-number sub-header row: its "location" is "3".
        # Real locations always contain a letter (a building name).
        if not re.search(r"[A-Za-z]", location):
            continue
        # Dedup identical (part_no, location) pairs from any double-listing.
        key = (part_no, location)
        if key in seen:
            continue
        seen.add(key)

        m = re.search(r"(\d{6})", location)
        rows.append({
            "part_no": part_no,
            "ps_no": ps_no,
            "building": location,
            "pincode": m.group(1) if m else "",
            "polling_area": clean(r[3]),
            "voter_type": clean(r[4]),
        })

    rows.sort(key=lambda x: x["part_no"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    n_unique_buildings = len({r["building"].upper() for r in rows})
    with_pin = sum(1 for r in rows if r["pincode"])
    print(f"Wrote {len(rows)} booths -> {OUT}")
    print(f"  parts {min(r['part_no'] for r in rows)}-{max(r['part_no'] for r in rows)}, "
          f"{n_unique_buildings} unique buildings, {with_pin}/{len(rows)} with pincode")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
