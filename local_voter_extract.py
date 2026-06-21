#!/usr/bin/env python3
"""
====================================================================
  Tamil Voter Roll → Extract Age (வயது) & Gender (பாலினம்)
  LOCAL PARALLEL EDITION — 10-14x faster than Kaggle/Colab
====================================================================

WHAT THIS DOES:
  1. Extracts all PDFs from your zip file
  2. Runs Tesseract OCR (Tamil+English) on every page in PARALLEL
  3. Extracts every "வயது : XX பாலினம்‌ : YY" pattern
  4. Saves results to CSV with pipe delimiter: filename | age | sex

YOUR HARDWARE ADVANTAGE:
  - i7-1370P: 14 cores / 20 threads → 14 simultaneous OCR workers
  - Kaggle/Colab free: only 2 cores
  - Expected: ~12-15 minutes for 235 files (vs ~3 hours on Kaggle)

REQUIREMENTS (already installed on your machine):
  - Tesseract OCR:   C:\\Users\\...\\Tesseract-OCR\\tesseract.exe  ✅
  - Python 3.12:     C:/Program Files/Python312/python.exe          ✅
  - pymupdf, pytesseract, Pillow, tqdm                              ✅

USAGE:
  python local_voter_extract.py

  With custom options:
  python local_voter_extract.py --workers 10 --dpi 300

RESUME SUPPORT:
  If the script crashes or you stop it, just re-run — it automatically
  skips files that were already processed and continues from where it left off.
"""

import os
import re
import csv
import sys
import time
import zipfile
import argparse
from multiprocessing import Pool, cpu_count

import pytesseract
from PIL import Image
import io

# Progress bar (with fallback if tqdm not installed)
try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, **kwargs):
        return iterable

# PyMuPDF import (handles both old 'fitz' and new 'pymupdf' package names)
try:
    import pymupdf as fitz
except ImportError:
    import fitz


# ============================================================
# Configuration
# ============================================================
ZIP_FILE      = "18-eroll.zip"
EXTRACT_DIR   = "extracted_pdfs"
OUTPUT_CSV    = "voter_age_gender_all.csv"
DPI           = 300
N_WORKERS     = min(cpu_count(), 14)          # Use up to 14 parallel workers

# Tesseract executable path (Windows)
TESSERACT_PATH = r"C:\Users\PremKumarManickam\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"

# ============================================================
# Regex Patterns (validated on real ECI voter roll OCR output)
# ============================================================
# Primary pattern: வயது : 49 பாலினம்‌ : பெண்‌
# Notes:
#   - [லவ] handles OCR confusion between பாலினம் and பாவினம்
#   - ZWNJ (U+200C) is stripped before matching (see extract function)
AGE_GENDER_PATTERN = re.compile(
    r'வயது\s*[:\-]?\s*(\d{1,3})\s*'          # வயது : 49
    r'பா?[லவ]ினம்?\s*[:\-]?\s*'               # பாலினம் :  (OCR may read பாவினம்)
    r'(ஆண்|பெண்|ஆண|பெண|ஆடு|மற்றோர்|மற்ற)',  # gender value
    re.UNICODE
)

# Fallback patterns (used if primary doesn't match)
AGE_ONLY_PATTERN    = re.compile(r'வயது\s*[:\-]?\s*(\d{1,3})', re.UNICODE)
GENDER_AFTER_AGE    = re.compile(r'(ஆண்|பெண்|ஆண|பெண)', re.UNICODE)


# ============================================================
# Core Functions
# ============================================================

def extract_zip(zip_path, extract_dir):
    """Extract PDFs from the zip file (skips if already extracted)."""
    # Check if already extracted
    if os.path.isdir(extract_dir):
        existing = [f for f in os.listdir(extract_dir) if f.lower().endswith('.pdf')]
        if existing:
            print(f"  ✓ Already extracted ({len(existing)} PDFs found in {extract_dir}/)")
            return

    print(f"  Extracting {zip_path} → {extract_dir}/ ...")
    os.makedirs(extract_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as zf:
        pdf_members = [m for m in zf.namelist() if m.lower().endswith('.pdf')]
        for member in tqdm(pdf_members, desc="  Extracting", unit="file"):
            zf.extract(member, extract_dir)
    print(f"  ✓ Extracted {len(pdf_members)} PDFs")


def extract_entries_from_text(text):
    """
    Extract (age, gender) pairs from OCR text.
    Returns list of tuples: [(age_int, gender_str), ...]
    """
    entries = []

    # Strip zero-width characters that Tesseract inserts in Tamil text
    # U+200C (ZWNJ) and U+200D (ZWJ) break regex matching on words
    # like பாலினம்‌ and ஆண்‌
    text = text.replace('\u200c', '').replace('\u200d', '')

    # --- Primary pattern: age + gender together ---
    matches = list(AGE_GENDER_PATTERN.finditer(text))

    if matches:
        for m in matches:
            age = int(m.group(1))
            gender_raw = m.group(2)
            if 'பெ' in gender_raw:
                gender = 'Female'
            elif 'ஆ' in gender_raw:
                gender = 'Male'
            else:
                gender = 'Other'
            entries.append((age, gender))
    else:
        # --- Fallback: find ages, then search for gender nearby ---
        age_matches = list(AGE_ONLY_PATTERN.finditer(text))
        for am in age_matches:
            age = int(am.group(1))
            if not (18 <= age <= 120):       # sanity filter
                continue
            # Look for gender within 50 chars after the age
            search_text = text[am.end():am.end() + 50]
            gm = GENDER_AFTER_AGE.search(search_text)
            if gm:
                gender_raw = gm.group(1)
                gender = 'Female' if 'பெ' in gender_raw else 'Male'
            else:
                gender = ''
            entries.append((age, gender))

    return entries


def process_single_pdf(pdf_path):
    """
    Worker function (runs in a separate process).
    Opens a PDF, converts each page to image, runs OCR, extracts entries.
    Returns list of tuples: [(filename, age, gender), ...]
    """
    # Each worker process needs the tesseract path set independently
    if sys.platform == 'win32' and os.path.exists(TESSERACT_PATH):
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

    pdf_name = os.path.basename(pdf_path)
    results = []

    try:
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page = doc[page_num]
            # Render page to image at configured DPI
            pix = page.get_pixmap(dpi=DPI)
            img = Image.open(io.BytesIO(pix.tobytes("png")))

            # Run Tesseract OCR with Tamil + English, PSM 6 (uniform text block)
            text = pytesseract.image_to_string(
                img, lang='tam+eng', config='--psm 6'
            )

            # Extract age & gender entries from OCR text
            entries = extract_entries_from_text(text)
            for age, gender in entries:
                results.append((pdf_name, age, gender))

        doc.close()

    except Exception as e:
        # Record error so we know which files failed
        results.append((pdf_name, 'ERROR', str(e)[:100]))

    return results


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Voter Roll OCR Extractor (Parallel Local Edition)"
    )
    parser.add_argument('--zip', default=ZIP_FILE,
                        help=f'Path to zip file (default: {ZIP_FILE})')
    parser.add_argument('--output', default=OUTPUT_CSV,
                        help=f'Output CSV path (default: {OUTPUT_CSV})')
    parser.add_argument('--extract-dir', default=EXTRACT_DIR,
                        help=f'Directory for extracted PDFs (default: {EXTRACT_DIR})')
    parser.add_argument('--workers', type=int, default=N_WORKERS,
                        help=f'Number of parallel workers (default: {N_WORKERS})')
    args = parser.parse_args()

    # Set tesseract path
    if sys.platform == 'win32' and os.path.exists(TESSERACT_PATH):
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

    # ---- Header ----
    print()
    print("=" * 65)
    print("   Voter Roll OCR Extractor — Parallel Local Edition")
    print("=" * 65)
    print(f"   Zip file:      {args.zip}")
    print(f"   Extract to:    {args.extract_dir}/")
    print(f"   Output CSV:    {args.output}")
    print(f"   Workers:       {args.workers} parallel processes")
    print(f"   DPI:           {DPI}")
    print(f"   Tesseract:     {TESSERACT_PATH}")
    print("=" * 65)

    # ---- Step 1: Extract zip ----
    print("\n[1/3] Extracting PDFs from zip...")
    extract_zip(args.zip, args.extract_dir)

    # ---- Step 2: Find PDFs & load resume state ----
    print("\n[2/3] Scanning for PDF files...")
    pdf_files = []
    for root, dirs, files in os.walk(args.extract_dir):
        for f in files:
            if f.lower().endswith('.pdf'):
                pdf_files.append(os.path.join(root, f))
    pdf_files.sort()

    print(f"  Found {len(pdf_files)} PDF files")

    # Resume support: check which files are already in the output CSV
    processed = set()
    if os.path.exists(args.output):
        with open(args.output, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f, delimiter='|')
            header = next(reader, None)  # skip header
            for row in reader:
                if row:
                    processed.add(row[0])
        remaining = [p for p in pdf_files if os.path.basename(p) not in processed]
        print(f"  Resume: {len(processed)} files already done, {len(remaining)} remaining")
        pdf_files = remaining

    if not pdf_files:
        print("\n✅ All files already processed! Check the output CSV.")
        return

    # ---- Step 3: Parallel OCR processing ----
    print(f"\n[3/3] Processing {len(pdf_files)} files with {args.workers} workers...")
    print(f"      (each worker runs Tesseract OCR independently)\n")

    start_time = time.time()

    # Open CSV for incremental writing (append mode for resume support)
    write_header = not os.path.exists(args.output)
    csvfile = open(args.output, 'a', newline='', encoding='utf-8-sig')
    writer = csv.writer(csvfile, delimiter='|')
    if write_header:
        writer.writerow(['pdf_file', 'age', 'gender'])

    total_entries = 0
    error_files = []

    with Pool(processes=args.workers) as pool:
        # imap_unordered yields results as they complete (not in order)
        # This gives the most accurate real-time progress bar
        with tqdm(
            total=len(pdf_files),
            desc="  OCR",
            unit="file",
            bar_format="  {desc}: {percentage:3.0f}% |{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]"
        ) as pbar:
            for results in pool.imap_unordered(process_single_pdf, pdf_files):
                # Write results to CSV immediately (crash-safe)
                for row in results:
                    writer.writerow(row)
                csvfile.flush()

                # Track stats
                file_name = os.path.basename(results[0][0]) if results else "?"
                has_error = any(r[1] == 'ERROR' for r in results)
                if has_error:
                    error_files.append(file_name)

                total_entries += len(results)
                pbar.update(1)

    csvfile.close()
    elapsed = time.time() - start_time

    # ---- Summary ----
    print(f"\n{'=' * 65}")
    print(f"   ✅  EXTRACTION COMPLETE")
    print(f"{'=' * 65}")
    print(f"   Time elapsed:    {elapsed/60:.1f} minutes ({elapsed:.0f}s)")
    print(f"   Files processed: {len(pdf_files)}")
    print(f"   Total entries:   {total_entries}")
    print(f"   Speed:           {len(pdf_files)/elapsed*60:.1f} files/min")
    print(f"   Output file:     {args.output}")

    if error_files:
        print(f"\n   ⚠️  {len(error_files)} files had errors:")
        for f in error_files[:10]:
            print(f"      - {f}")
        if len(error_files) > 10:
            print(f"      ... and {len(error_files) - 10} more")

    # Quick stats from output CSV
    try:
        males = females = 0
        ages = []
        with open(args.output, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f, delimiter='|')
            next(reader, None)  # skip header
            for row in reader:
                if len(row) >= 3 and row[1] != 'ERROR':
                    try:
                        ages.append(int(row[1]))
                    except ValueError:
                        pass
                    if row[2] == 'Male':
                        males += 1
                    elif row[2] == 'Female':
                        females += 1

        print(f"\n   📊 Summary Statistics:")
        print(f"      Total voters:  {len(ages)}")
        print(f"      Male:          {males}")
        print(f"      Female:        {females}")
        if ages:
            print(f"      Age range:     {min(ages)}–{max(ages)}")
            print(f"      Average age:   {sum(ages)/len(ages):.1f}")
    except Exception:
        pass

    print(f"\n{'=' * 65}\n")


if __name__ == '__main__':
    main()
