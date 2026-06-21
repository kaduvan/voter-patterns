#!/usr/bin/env python3
"""
Parse PDFs (booth list + Form-20) for an AC into the same CSV/JSON formats
that the xlsx-based parsers produce. Works for constituencies whose ECI data
was exported as PDF instead of xlsx (e.g. AC019 Chepauk-Thiruvallikeni).

Outputs (under data/):
  booths_{prefix}.csv              — Part No, PS NO, building, pincode, area
  votes_{prefix}_{year}.csv        — per-booth candidate vote counts
  candidates_{prefix}_{year}.json  — candidate name + party per col

Usage: python scripts/parse_pdf.py [--ac AC019]
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

import fitz  # pymupdf

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ac_config


# ── Booth list PDF parser ───────────────────────────────────────────────────

def parse_booth_list(pdf_path, prefix):
    """Parse the ECI 'List of Polling Stations' PDF into a booths CSV.

    The PDF is a 5-column table (Part No, PS NO, Location+building, Polling
    Area, Polling Station Type) that repeats its column-number header on each
    page break. Pymupdf's text extraction gives us one line per cell, so we
    reconstruct rows by tracking the Part No / PS NO integers.
    """
    doc = fitz.open(str(pdf_path))
    raw_lines = []
    for page in doc:
        raw_lines.extend(page.get_text().split("\n"))
    doc.close()

    lines = [l.strip() for l in raw_lines if l.strip()]

    # Walk the lines and extract booth records.
    # Structure: after the column-header row ("1\n2\n3\n4\n5"), data starts.
    # Each booth has: Part No (int), PS NO (int), then multi-line Location
    # (quoted if multi-line), then multi-line Polling Area, then Voter Type.
    booths = []
    i = 0
    n = len(lines)

    # Skip past the page title and find the first column-number sequence
    # "1", "2", "3", "4", "5"
    while i < n - 5:
        if (lines[i] == "1" and lines[i + 1] == "2" and lines[i + 2] == "3"
                and lines[i + 3] == "4" and lines[i + 4] == "5"):
            i += 5  # skip past column headers
            break
        i += 1

    while i < n:
        # Expect: Part No (int), PS NO (int)
        if not re.match(r"^\d+$", lines[i]):
            i += 1
            continue

        # Check if next is also an integer (PS NO) — if so, this is Part No
        if i + 1 < n and re.match(r"^\d+[A-Za-z]?$", lines[i + 1]):
            try:
                part_no = int(lines[i])
            except ValueError:
                i += 1
                continue
            ps_no_str = lines[i + 1]
            try:
                ps_no = int(ps_no_str)
            except ValueError:
                ps_no = ps_no_str  # keep as-is (e.g. "1A")
        else:
            i += 1
            continue

        # Collect subsequent lines until we hit the next Part No / PS NO pair
        # or a column-header repeat. Everything between is Location + Area + Type.
        j = i + 2
        cell_lines = []
        while j < n:
            # Stop if we see the next Part No + PS NO pair
            if (re.match(r"^\d+$", lines[j]) and j + 1 < n
                    and re.match(r"^\d+[A-Za-z]?$", lines[j + 1])):
                # Make sure this isn't just a number inside an address.
                # Heuristic: the Part No should be sequential (current + 1).
                try:
                    next_part = int(lines[j])
                    if next_part == part_no + 1 or (next_part == 1 and part_no > 200):
                        break
                except ValueError:
                    pass
            # Stop at column-header repeat
            if lines[j] == "1" and j + 4 < n and lines[j + 1] == "2":
                j += 5  # skip the header repeat
                continue
            cell_lines.append(lines[j])
            j += 1

        # Parse cell_lines into: Location (building), Polling Area, Voter Type
        # Voter Type is typically the last line: "All Voters", "All Women", etc.
        building = ""
        polling_area = ""
        voter_type = ""

        if cell_lines:
            # Voter type = last line if it matches known types
            known_types = ["All Voters", "All Women", "All Men", "All Service"]
            for kt in known_types:
                if cell_lines and cell_lines[-1].strip() == kt:
                    voter_type = cell_lines.pop().strip()
                    break

            # Polling Area starts after a line that looks like an address
            # (contains "Chennai-" or pincode). The building is everything before.
            area_start = len(cell_lines)
            for k in range(len(cell_lines)):
                if re.search(r"\d{6}", cell_lines[k]):
                    # This line has a pincode. Building = up to and including
                    # this line. Polling Area = everything after.
                    area_start = k + 1
                    break

            building = " ".join(cell_lines[:area_start]).strip()
            polling_area = " ".join(cell_lines[area_start:]).strip()

        # Extract pincode from building
        pin_match = re.search(r"(\d{6})", building)
        pincode = pin_match.group(1) if pin_match else ""

        # Clean building — remove surrounding quotes
        building = building.strip().strip('"').strip()

        booths.append({
            "part_no": part_no,
            "ps_no": ps_no,
            "building": building,
            "pincode": pincode,
            "polling_area": polling_area,
            "voter_type": voter_type,
        })

        i = j

    booths.sort(key=lambda x: x["part_no"])

    out = DATA / f"booths_{prefix}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["part_no", "ps_no", "building",
                                          "pincode", "polling_area", "voter_type"])
        w.writeheader()
        w.writerows(booths)

    print(f"  Booth list: {len(booths)} booths -> {out.name}")
    if booths:
        print(f"    parts {booths[0]['part_no']}-{booths[-1]['part_no']}, "
              f"{len({b['building'][:30] for b in booths})} unique buildings")
    return booths


# ── Form-20 PDF parser ──────────────────────────────────────────────────────

HEADER_LABELS = [
    "serial no", "sl. no", "sl no", "polling station", "total of valid",
    "total no. of votes", "total no of votes", "no. of rejected", "rejected",
    "nota", "grand total", "total", "no. of tendered", "tendered",
    "no of valid votes", "valid votes cast",
]


def is_header_label(s):
    s = re.sub(r"\s+", " ", str(s).lower()).strip()
    return any(lbl in s for lbl in HEADER_LABELS)


def parse_form20_pdf(pdf_path, year, prefix):
    """Parse a Form-20 result PDF into per-booth votes CSV + candidates JSON.

    Uses pymupdf table extraction across all pages. The layout varies by year:
    - 2026: row 0 = headers, row 1 = names, row 2+ = data
    - 2024: row 0 = title, row 1 = subtitle, row 2 = col numbers, row 3 = parties,
            row 4 = names, row 5 = col numbers, row 6+ = data
    - 2021: row 0 = title, row 1 = names, row 2 = parties, row 3 = col numbers,
            row 4+ = data
    """
    doc = fitz.open(str(pdf_path))

    # Collect all rows from all pages
    all_rows = []
    for page in doc:
        tabs = page.find_tables()
        if tabs.tables:
            rows = tabs.tables[0].extract()
            all_rows.extend(rows)
    doc.close()

    if not all_rows:
        print(f"  {year}: no tables found in PDF")
        return

    # Find the header structure. We need to locate:
    # 1. The candidate-name row
    # 2. The party row (if present)
    # 3. Summary columns (total_valid, rejected, nota, total)
    # 4. The station column

    # Strategy: scan rows to find candidate names and column roles.
    # Candidate names are short person names (not header labels, not party names).
    name_row_idx = None
    party_row_idx = None
    station_col = 0  # default: col 0

    # Identify candidate name row: the row with the most person-name-like cells
    best_score = -1
    for i, row in enumerate(all_rows[:10]):
        score = 0
        for v in row:
            if v is None:
                continue
            s = re.sub(r"\s+", " ", str(v)).strip()
            if not s or is_header_label(s):
                continue
            low = s.lower()
            # Party-like strings
            if any(k in low for k in ["party", "kazhagam", "independent",
                                      "congress", "front", "katchi", "maiam"]):
                score -= 2
            # Pure numbers (column numbers)
            elif re.match(r"^\d+$", s):
                continue
            # Person names (short, has letters)
            elif re.search(r"[A-Za-z]{2,}", s) and len(s) <= 40:
                score += 1
        if score > best_score:
            best_score = score
            name_row_idx = i

    # Party row: the row after name_row (or before) with party-like strings
    if name_row_idx is not None:
        for offset in [1, -1, 2]:
            idx = name_row_idx + offset
            if idx < 0 or idx >= len(all_rows):
                continue
            row = all_rows[idx]
            party_count = 0
            for v in row:
                if v is None:
                    continue
                low = str(v).lower().strip()
                if any(k in low for k in ["party", "kazhagam", "independent",
                                          "congress", "front", "katchi", "maiam"]):
                    party_count += 1
            if party_count >= 3:
                party_row_idx = idx
                break

    # Identify summary columns from the header row(s)
    # Scan the first few rows for cells with known labels
    summary_cols = {}  # col_index -> role
    for i in range(min(5, len(all_rows))):
        row = all_rows[i]
        for j, v in enumerate(row):
            if v is None:
                continue
            low = re.sub(r"\s+", " ", str(v).lower())
            if "total of valid" in low or "total no. of votes" in low \
                    or "total no of valid" in low:
                summary_cols[j] = "total_valid"
            elif low.strip() == "rejected" or "no. of rejected" in low:
                summary_cols[j] = "rejected"
            elif low.strip() == "nota":
                summary_cols[j] = "nota"
            elif low.strip() == "total" or "grand total" in low:
                if j not in summary_cols:
                    summary_cols[j] = "total"

    # Station column: look for "Polling Station" or "Serial" label
    for i in range(min(5, len(all_rows))):
        for j, v in enumerate(all_rows[i]):
            if v is None:
                continue
            low = str(v).lower()
            if "polling station" in low:
                station_col = j
                break
            if "serial" in low:
                station_col = j

    # Candidate columns = non-header cells in name_row that look like names
    cand_cols = []
    if name_row_idx is not None:
        for j, v in enumerate(all_rows[name_row_idx]):
            if v is None:
                continue
            name = re.sub(r"\s+", " ", str(v)).strip()
            if not name or is_header_label(name):
                continue
            # Skip pure numbers (column number headers)
            if re.match(r"^\d+$", name):
                continue
            # Skip very long strings (section titles)
            if len(name) > 50:
                continue
            # Skip abbreviated summary-column headers that leak into name row
            # ("Tot", "NOTA", "Rej", "No.", "TR", "TRV", "TRD", etc.)
            if name.lower() in ("tot", "total", "nota", "rej", "rejected",
                                "no", "no.", "tr", "trv", "trd", "grand",
                                "grand total", "sl", "sl."):
                continue
            # Skip this column if it's already identified as a summary column
            if j in summary_cols:
                continue
            cand_cols.append((j, name.replace("\n", " ")))

    # Party lookup
    party_by_col = {}
    if party_row_idx is not None:
        for j, v in enumerate(all_rows[party_row_idx]):
            if v is not None:
                party_by_col[j] = re.sub(r"\s+", " ", str(v)).strip()

    candidates = [{"col": j, "name": n, "party": party_by_col.get(j, "")}
                  for j, n in cand_cols]

    # Data rows: rows where station_col has an integer value.
    # BUT: 2021/2024 Form-20 has repeating column-number rows (1, 2, 3, 4, ...)
    # that look like data. Filter them out: if col 0 = 1 AND col 1 = 2 AND
    # col 2 = 3, it's a column-number header, not a data row.
    out = []
    seen_stations = set()
    for row in all_rows:
        if station_col >= len(row) or row[station_col] is None:
            continue
        try:
            sno = int(str(row[station_col]).strip())
        except (ValueError, TypeError):
            continue

        # Skip column-number header rows (1, 2, 3, ...) — present in 2021/2024
        vals = []
        is_col_header = True
        for v in row[:max(5, len(cand_cols) + 2)]:
            try:
                vals.append(int(float(str(v).replace(",", "").strip())))
            except (ValueError, TypeError):
                is_col_header = False
                break
        if is_col_header and len(vals) >= 5 and vals[:5] == [1, 2, 3, 4, 5]:
            continue

        if sno in seen_stations:
            continue
        seen_stations.add(sno)

        rec = {"station_no": sno}
        for j, n in cand_cols:
            v = row[j] if j < len(row) else 0
            try:
                rec[n] = int(float(str(v).replace(",", "").strip() or 0))
            except (ValueError, TypeError):
                rec[n] = 0
        for role, col in [(v, k) for k, v in summary_cols.items()]:
            v = row[col] if col < len(row) else 0
            try:
                rec[role] = int(float(str(v).replace(",", "").strip() or 0))
            except (ValueError, TypeError):
                rec[role] = 0
        out.append(rec)

    out.sort(key=lambda x: x["station_no"])

    # If no total_valid column detected, compute from candidate sums
    cand_names = [c["name"] for c in candidates]
    if "total_valid" not in summary_cols.values():
        for rec in out:
            rec["total_valid"] = sum(int(rec.get(n, 0) or 0) for n in cand_names)
        print(f"    computed total_valid as candidate-vote sum (no explicit column)")

    # Sanitize: if total_valid is 0 but candidate votes sum > 0, recompute
    fixed = 0
    for rec in out:
        cand_sum = sum(int(rec.get(n, 0) or 0) for n in cand_names)
        if not rec.get("total_valid") and cand_sum > 0:
            rec["total_valid"] = cand_sum
            fixed += 1
    if fixed:
        print(f"    sanitized {fixed} rows with missing total_valid")

    # Write votes CSV
    DATA.mkdir(exist_ok=True)
    summary_fields = sorted({v for v in summary_cols.values()})
    if "total_valid" not in summary_fields:
        summary_fields = ["total_valid"] + summary_fields
    fields = ["station_no"] + cand_names + summary_fields
    vpath = DATA / f"votes_{prefix}_{year}.csv"
    with open(vpath, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(out)

    # Write candidates JSON
    cpath = DATA / f"candidates_{prefix}_{year}.json"
    cpath.write_text(json.dumps(candidates, ensure_ascii=False, indent=2),
                     encoding="utf-8")

    print(f"  {year}: {len(out)} stations, {len(candidates)} candidates "
          f"-> {vpath.name} + {cpath.name}")
    return candidates, out


# ── 2026 party overrides for AC019 Chepauk ──────────────────────────────────
# The 2026 Form-20 PDF has no party row. Confirmed from ECI official results.
PARTY_OVERRIDES_2026_AC019 = {
    "UDHAYANIDHI STALIN": "Dravida Munnetra Kazhagam",
    "SELVAM. D": "Tamilaga Vettri Kazhagam",
    "AADIRAJARAM": "All India Anna Dravida Munnetra Kazhagam",
    "AYSHA": "Naam Tamilar Katchi",
    "MOHAMMED YASSER": "Bahujan Samaj Party",
    "IRFAN BASHA": "Tamizhaga Vaazhvurimai Katchi",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ac", default="AC019")
    args = parser.parse_args()

    cfg = ac_config.get(args.ac)
    prefix = cfg["prefix"]
    print(f"Parsing PDFs for {args.ac} ({cfg['name']})...")

    # 1. Booth list
    bl = cfg["booth_list"]
    bl_path = BASE / bl if not bl.startswith("..") else Path(__file__).resolve().parent.parent / bl
    if bl_path.exists():
        parse_booth_list(bl_path, prefix)
    else:
        print(f"  Booth list not found: {bl_path}")

    # 2. Form-20 results
    for year, fname in cfg.get("form20", {}).items():
        fp = BASE / fname if not fname.startswith("..") else Path(__file__).resolve().parent.parent / fname
        if fp.exists():
            parse_form20_pdf(fp, year, prefix)
            # Apply 2026 party overrides if needed
            if year == 2026 and PARTY_OVERRIDES_2026_AC019:
                cpath = DATA / f"candidates_{prefix}_2026.json"
                if cpath.exists():
                    cands = json.loads(cpath.read_text(encoding="utf-8"))
                    for c in cands:
                        if c["name"] in PARTY_OVERRIDES_2026_AC019:
                            c["party"] = PARTY_OVERRIDES_2026_AC019[c["name"]]
                    cpath.write_text(json.dumps(cands, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
                    n_set = sum(1 for c in cands if c["party"] != "Independent")
                    print(f"    applied 2026 party overrides ({n_set} named)")
        else:
            print(f"  {year}: {fp} not found")


if __name__ == "__main__":
    main()
