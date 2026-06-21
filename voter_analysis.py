#!/usr/bin/env python3
"""
====================================================================
  Voter Roll → Booth-wise Age/Gender Distribution (with %)
====================================================================
  Reads the extraction CSV (pdf_file | age | gender) and produces:
    1. Booth-wise age group breakdown (Male/Female/Total + %)
    2. Grand totals across all booths
    3. Summary CSVs for easy import to Excel/Sheets

  Output files:
    - booth_age_gender_distribution.csv    (one row per booth)
    - grand_total_summary.csv              (single summary row)

  Age Groups:
    18-21, 22-29, 30-39, 40-49, 50-59, 60-69, 70+

  Percentage columns:
    - Within each age group: Male%, Female%
    - Each age group as % of booth total
    - Booth total gender split %
====================================================================
"""

import csv
import re
import os
from collections import defaultdict

# ============================================================
# Config
# ============================================================
INPUT_CSV = "voter_age_gender_all.csv"

# Output files
OUTPUT_BOOTH   = "booth_age_gender_distribution.csv"
OUTPUT_SUMMARY = "grand_total_summary.csv"

# Age groups (label, min_age, max_age). None = no upper bound
AGE_GROUPS = [
    ("18-21", 18, 21),
    ("22-29", 22, 29),
    ("30-39", 30, 39),
    ("40-49", 40, 49),
    ("50-59", 50, 59),
    ("60-69", 60, 69),
    ("70+",   70, None),
]

# Regex to extract booth number from filename
# Pattern: ...-TAM-{NUMBER}-WI.pdf
BOOTH_PATTERN = re.compile(r'-TAM-(\d+)-WI\.pdf$', re.IGNORECASE)


def get_age_group(age):
    """Return the age group label for a given age."""
    for label, lo, hi in AGE_GROUPS:
        if hi is None:
            if age >= lo:
                return label
        elif lo <= age <= hi:
            return label
    return None


def extract_booth_number(filename):
    """Extract booth number from PDF filename."""
    m = BOOTH_PATTERN.search(filename)
    if m:
        return int(m.group(1))
    return filename


def pct(part, total):
    """Return formatted percentage. Handles divide-by-zero."""
    if total == 0:
        return 0.0
    return round((part / total) * 100, 1)


def main():
    # ---- Header ----
    print()
    print("=" * 70)
    print("   Booth-wise Age/Gender Distribution Generator (with %)")
    print("=" * 70)
    print(f"   Input:  {INPUT_CSV}")
    print(f"   Output: {OUTPUT_BOOTH}")
    print(f"           {OUTPUT_SUMMARY}")
    print("=" * 70)

    if not os.path.exists(INPUT_CSV):
        print(f"\n❌ Error: {INPUT_CSV} not found!")
        return

    # ---- Read data ----
    print(f"\n[1/2] Reading {INPUT_CSV} ...")

    # booth_data[booth_number][age_group] = {'Male': N, 'Female': N, 'Other': N}
    booth_data = defaultdict(lambda: defaultdict(lambda: {'Male': 0, 'Female': 0, 'Other': 0}))
    booth_filenames = {}  # booth_number -> original filename

    total_read = 0
    skipped = 0

    with open(INPUT_CSV, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f, delimiter='|')
        header = next(reader, None)

        for row in reader:
            if len(row) < 3:
                skipped += 1
                continue

            pdf_file, age_str, gender = row[0], row[1], row[2]

            if age_str == 'ERROR':
                skipped += 1
                continue

            try:
                age = int(age_str)
            except ValueError:
                skipped += 1
                continue

            group = get_age_group(age)
            if group is None:
                skipped += 1
                continue

            booth_num = extract_booth_number(pdf_file)
            booth_filenames[booth_num] = pdf_file

            if gender not in ('Male', 'Female'):
                gender = 'Other'

            booth_data[booth_num][group][gender] += 1
            total_read += 1

    print(f"   ✓ Read {total_read:,} entries, skipped {skipped}")
    print(f"   ✓ Found {len(booth_data)} booths")

    # ---- Write booth-wise output ----
    print(f"\n[2/2] Writing {OUTPUT_BOOTH} ...")

    group_labels = [g[0] for g in AGE_GROUPS]

    # Column headers: booth info + per-group (Male, Female, Total, Male%, Female%, Group%) + booth totals
    headers = ['booth_number', 'pdf_file']
    for gl in group_labels:
        headers.extend([
            f'{gl}_Male',
            f'{gl}_Female',
            f'{gl}_Total',
            f'{gl}_Male%',        # Male as % of this group's total
            f'{gl}_Female%',      # Female as % of this group's total
            f'{gl}_of_Booth%',    # This group as % of entire booth
        ])
    headers.extend([
        'Booth_Total_Male',
        'Booth_Total_Female',
        'Booth_Total_Other',
        'Booth_Total',
        'Booth_Male%',
        'Booth_Female%',
    ])

    # Grand totals accumulator
    grand = defaultdict(lambda: {'Male': 0, 'Female': 0, 'Other': 0})

    # Sort booths by number
    def booth_sort_key(b):
        if isinstance(b, int):
            return (0, b)
        return (1, 0)

    sorted_booths = sorted(booth_data.keys(), key=booth_sort_key)

    with open(OUTPUT_BOOTH, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        for booth_num in sorted_booths:
            groups = booth_data[booth_num]

            # Calculate booth total first (needed for percentages)
            booth_total = {'Male': 0, 'Female': 0, 'Other': 0}
            for gl in group_labels:
                counts = groups.get(gl, {'Male': 0, 'Female': 0, 'Other': 0})
                booth_total['Male']   += counts['Male']
                booth_total['Female'] += counts['Female']
                booth_total['Other']  += counts['Other']

            booth_grand = booth_total['Male'] + booth_total['Female'] + booth_total['Other']

            row = [booth_num, booth_filenames.get(booth_num, '')]

            for gl in group_labels:
                counts = groups.get(gl, {'Male': 0, 'Female': 0, 'Other': 0})
                m, fe, ot = counts['Male'], counts['Female'], counts['Other']
                group_total = m + fe + ot

                row.extend([
                    m,                                            # Male count
                    fe,                                           # Female count
                    group_total,                                  # Group total
                    pct(m, group_total),                          # Male % within group
                    pct(fe, group_total),                         # Female % within group
                    pct(group_total, booth_grand),                # Group as % of booth
                ])

                grand[gl]['Male']   += m
                grand[gl]['Female'] += fe
                grand[gl]['Other']  += ot

            row.extend([
                booth_total['Male'],
                booth_total['Female'],
                booth_total['Other'],
                booth_grand,
                pct(booth_total['Male'], booth_grand),           # Booth Male %
                pct(booth_total['Female'], booth_grand),         # Booth Female %
            ])
            writer.writerow(row)

    # ---- Write grand total summary ----
    # Calculate grand totals
    grand_total = {'Male': 0, 'Female': 0, 'Other': 0}
    for gl in group_labels:
        counts = grand[gl]
        grand_total['Male']   += counts['Male']
        grand_total['Female'] += counts['Female']
        grand_total['Other']  += counts['Other']
    all_total = grand_total['Male'] + grand_total['Female'] + grand_total['Other']

    with open(OUTPUT_SUMMARY, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow([
            'age_group', 'Male', 'Female', 'Other', 'Total',
            'Male%', 'Female%', '% of All Voters',
        ])

        for gl in group_labels:
            counts = grand[gl]
            m, fe, ot = counts['Male'], counts['Female'], counts['Other']
            total = m + fe + ot
            writer.writerow([
                gl, m, fe, ot, total,
                pct(m, total),            # Male % within group
                pct(fe, total),           # Female % within group
                pct(total, all_total),    # Group as % of all voters
            ])

        writer.writerow([])
        writer.writerow([
            'GRAND TOTAL',
            grand_total['Male'], grand_total['Female'], grand_total['Other'], all_total,
            pct(grand_total['Male'], all_total),
            pct(grand_total['Female'], all_total),
            100.0,
        ])

    # ---- Console Summary ----
    print(f"\n{'=' * 75}")
    print(f"   ✅  DONE")
    print(f"{'=' * 75}")

    print(f"\n   📊 Age Group Distribution — All Booths Combined ({all_total:,} voters):")
    print(f"\n   {'Age Group':<12} {'Male':>7} {'M%':>5}  {'Female':>7} {'F%':>5}  "
          f"{'Total':>7} {'% All':>6}")
    print(f"   {'─'*12} {'─'*7} {'─'*5}  {'─'*7} {'─'*5}  {'─'*7} {'─'*6}")

    for gl in group_labels:
        counts = grand[gl]
        m, fe, ot = counts['Male'], counts['Female'], counts['Other']
        total = m + fe + ot
        print(f"   {gl:<12} {m:>7,} {pct(m, total):>4.1f}%  {fe:>7,} {pct(fe, total):>4.1f}%  "
              f"{total:>7,} {pct(total, all_total):>5.1f}%")

    print(f"   {'─'*12} {'─'*7} {'─'*5}  {'─'*7} {'─'*5}  {'─'*7} {'─'*6}")
    print(f"   {'TOTAL':<12} {grand_total['Male']:>7,} {pct(grand_total['Male'], all_total):>4.1f}%  "
          f"{grand_total['Female']:>7,} {pct(grand_total['Female'], all_total):>4.1f}%  "
          f"{all_total:>7,} {'100%':>6}")

    print(f"\n   📁 Output files:")
    print(f"      • {OUTPUT_BOOTH}   ({len(sorted_booths)} booths, {len(headers)} columns)")
    print(f"      • {OUTPUT_SUMMARY}")
    print(f"\n{'=' * 75}\n")


if __name__ == '__main__':
    main()
