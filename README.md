# voter-patterns

**Booth-level electoral data for Chennai — official vote counts and registered voter demographics, side by side across three elections.**

🔗 **Live: [kaduvan.github.io/voter-patterns](https://kaduvan.github.io/voter-patterns/)**

---

## The status of this project

This is a **prelude**. Two constituencies — Harbour and Chepauk-Thiruvallikeni — are a proof of concept. The pipeline works. The data is real. The visualizations are honest. But two ACs out of 234 in Tamil Nadu is a starting point, not a finished product.

The goal is for this to grow — constituency by constituency, city by city, state by state — until every polling booth in India has its electoral data and Electoral Roll side by side on an open map. That's a lot of booths (nearly a million nationwide), and I can't do it alone.

**If you're reading this and thinking "I could do this for my constituency" — you can.** The section below tells you exactly how. Fork this repo, pick an AC, follow the steps, and submit a pull request. Every contribution moves the map closer to complete.

---

## Why this exists

I built [electoral-analytics](https://github.com/kaduvan/electoral-analytics) to map the 2026 Tamil Nadu election across all 234 constituencies — village by village, statewide. It answered a broad question: *who won where?*

But electoral results only tell you one thing: aggregate vote counts. They don't tell you who the electors in a booth are — their age, their gender, the generational makeup of a neighborhood. That information lives in a separate official document: the Electoral Roll.

This project brings both datasets together at the most granular level where they overlap: the individual polling booth. Form 20 tells you how many votes each candidate got. The Electoral Roll tells you how many registered voters fall into each age and gender band. Shown side by side, they give a fuller picture of a booth than either can alone.

What this is **not**: a claim that we know how any demographic group voted. That would require ecological inference, which we deliberately don't perform. We show the data. The interpretation is yours.

---

## How it differs from [electoral-analytics](https://github.com/kaduvan/electoral-analytics)

| | electoral-analytics | voter-patterns (this repo) |
|---|---|---|
| **Geography** | Village-level (estimated via name matching) | **Booth-level** (exact — no estimation) |
| **Data sources** | Form 20 votes only | **Form 20 votes + Electoral Roll demographics** |
| **Demographics** | None | Age × gender, 7 bands, population pyramids |
| **Elections** | 2026 only | **2021, 2024, 2026** (3 cycles) |
| **Coverage** | 234 ACs, 9,809 villages (statewide) | 2 ACs, 397 booths (hyperlocal) |
| **Data quality** | Village votes estimated (65.6% station match rate) | Booth votes exact (100% — source data is per-booth) |
| **Time depth** | Single snapshot | Same booths across 5 years and 3 elections |
| **File size** | 39.5 MB monolith | 790 KB data + modular HTML/CSS/JS |

**In short:** electoral-analytics is breadth (the whole state, one election). voter-patterns is depth (every booth, both datasets, three elections). They're complementary.

This is a separate repo rather than a feature in electoral-analytics because the data pipelines are fundamentally different. electoral-analytics aggregates Form 20 PDFs statewide. voter-patterns ingests two independent official datasets — the Electoral Roll and Form 20 — and aligns them at the booth level. The sources, parsing, and alignment logic don't share much code.

---

## What you can explore

**397 polling booths** across two constituencies, each rendered as an interactive Voronoi cell on a light basemap. Click any booth to see both datasets side by side:

### Vote results (from Form 20)
- Winner by alliance, with opacity scaled to vote share
- Alliance-specific share maps (e.g., "where is TVK strongest?")
- Lead margins — from razor-thin to landslide
- Full vote breakdowns across all 3 cycles (2021, 2024, 2026)

### Registered voter composition (from the Electoral Roll)
- Dominant age band per booth (18-21 through 70+)
- Cohort share — any age × gender combination as a share of registered voters
- Gender ratio mapping (male-skew to female-skew)
- Youth (<30) and elderly (60+) concentration
- Absolute counts — where registered voters are
- Population pyramids on booth click

### Summary views
- Donut chart showing alliance vote-share breakdown for any cycle/constituency
- Summary cards: valid votes, registered voter counts, age composition
- Top 5 rankings for any metric
- Per-constituency split when viewing all constituencies combined

---

## The two datasets — and why they're independent

This is the most important thing to understand about this project:

**The Electoral Roll** lists *who is registered to vote* — name, age, gender, address. It's a census of eligible voters, published as PDFs by the Election Commission of India.

**Form 20** records *how many votes each candidate received* at each polling station — candidate-wise counts, EVM only.

These are **two completely independent datasets**. The Electoral Roll says nothing about how anyone voted (that's a secret ballot). Form 20 says nothing about who the voters are (just aggregate counts per candidate). They happen to share one common key — the polling booth number — which lets us display them side by side.

That's all this project does: **shows them side by side**. It does not merge them into claims about how demographic groups voted. Inferring individual or group voting behavior from aggregate booth-level data is a statistical technique called *ecological inference*, and it requires careful methodology, assumptions, and uncertainty bounds. We don't do that here. We show the raw data and let you draw your own conclusions — or none at all.

Every booth detail panel labels its data sources explicitly, because conflating "who is registered here" with "how this booth voted" is the fastest way to draw wrong conclusions.

---

## Constituencies

| Code | Constituency | Lok Sabha | Booths | Registered voters |
|---|---|---|---|---|
| AC018 | Harbour | Chennai Central | 192 | ~110,000 |
| AC019 | Chepauk-Thiruvallikeni | Chennai Central | 205 | ~132,000 |
| | **Combined** | | **397** | **~242,000** |

Both are coastal Chennai constituencies — densely populated, politically competitive, and historically significant. Harbour covers the port and old trading quarters. Chepauk-Thiruvallikeni includes Triplicane, Royapettah, and the Marina beachfront.

---

## How to replicate this analysis for your constituency

This is the guide for anyone who wants to add a constituency or build a similar map for their own city/state. It's more approachable than it looks — the hard parts are data collection (downloading PDFs) and geocoding (finding booth locations). The code does the rest.

### What you'll need

1. **Form 20 PDFs** — Download from the [ECI results page](https://results.eci.gov.in) for your constituency. You want the station-wise (Part-wise) results, one PDF per AC per election.
2. **Electoral Roll PDFs** — Download from the [ECI voter portal](https://voters.eci.gov.in) or your state CEO portal. You need the draft/final electoral roll for your AC — it lists every registered voter by age, gender, and polling station.
3. **Booth addresses** — The polling station names and addresses. These are in the Electoral Roll header pages, or available as separate PDFs from the CEO portal.
4. **Python 3.10+** with `scipy`, `shapely`, `numpy`, and `pymupdf` (for PDF parsing).

### The pipeline, step by step

#### Step 1: Parse Form 20 → vote counts per booth

Form 20 PDFs have a consistent structure: a table per polling station with candidate names and vote counts. Our parser (`scripts/parse_pdf.py`) extracts these into:

```
votes_acXXX_YYYY.csv     # one row per station, one column per candidate
candidates_acXXX_YYYY.json   # candidate name → party mapping
```

The parsing is finicky — PDF layouts vary by state and year. Start with `pymupdf` to extract text blocks, then pattern-match the candidate/vote rows. Budget a few hours per state's PDF format.

#### Step 2: Extract demographics from the Electoral Roll

The Electoral Roll lists every voter individually. Aggregate them by polling station and age band:

```
booth_number, 18-21_Male, 18-21_Female, 18-21_Total, 22-29_Male, ...
1, 14, 12, 26, 38, 47, 85, ...
```

Seven age bands (18-21, 22-29, 30-39, 40-49, 50-59, 60-69, 70+) × three columns (Male, Female, Total) = 21 demographic columns per booth. Our extractor (`local_voter_extract.py`) does this from the roll PDFs.

#### Step 3: Geocode the booths

This is the hardest part. Polling booths in India don't have published coordinates — you have to derive them from addresses. We use a tiered approach:

1. **Street-level** (best): Query multiple geocoding APIs (Google, Nominatim, etc.) with the full street address. ~40% hit rate in dense urban areas.
2. **Locality-level** (good): Fall back to the neighborhood/locality centroid. ~30% hit rate.
3. **AC centroid** (approximate): Unknown location — place at the constituency center with reduced opacity. ~30% of booths.

The result is a `booth_coords_acXXX.csv` with `part_no, lat, lon, tier, street, locality, door_no` per booth. The `tier` column drives opacity in the visualization.

#### Step 4: Generate Voronoi cells

Each booth becomes a polygon on the map via Voronoi tessellation, clipped to the constituency outline (concave hull of all booth points). This gives a visual proxy for "this booth serves roughly this area." Run `scripts/build_data.py` — it handles this automatically.

#### Step 5: Register the constituency

Add one entry to `scripts/ac_config.py`:

```python
"AC017": {
    "name": "Your Constituency Name",
    "state": "Tamil Nadu",
    "pc": "Chennai Central",
    "center": [13.08, 80.27],          # lat, lon of AC center
    "prefix": "ac017",                 # filename prefix for data files
    "booth_list": "data/booths_ac017.csv",
    "demographics": "data/demographics_ac017.csv",
    "form20": {"2026": "...", "2024": "...", "2021": "..."},
    "geocode": {"key": "..."},         # optional geocoding API key
},
```

Then run `python scripts/build_data.py`. The AC selector, donut chart, summaries, map — everything updates automatically.

### Submitting your work

1. Fork this repo
2. Add your constituency data (CSVs in `data/`, config entry in `ac_config.py`)
3. Run `python scripts/build_data.py` to regenerate `data.json`
4. Test locally: `cd site && python -m http.server 8000`
5. Open a pull request

I'll review, merge, and deploy. Your constituency goes live within minutes.

---

## Limitations — what this data cannot tell you

I'd rather overstate the limitations than understate them.

**Voronoi cells are approximations, not boundaries.** Polling booths in India don't have defined geographic territories. We generate Voronoi cells from booth coordinates, clipped to the constituency outline. It's a visual proxy for "this booth serves roughly this area" — not an official service-area map.

**Centroid booths have unknown locations.** Some booths couldn't be geocoded to street level. They appear at their locality centroid or AC center, with reduced opacity. Their vote and demographic data is still accurate — only the position is approximate.

**2024 was Lok Sabha, not Assembly.** The 2024 cycle was the Chennai Central Parliamentary election. The booth-level votes are real, but the contest was PC-wide. Don't compare 2024 alliance shares directly with 2021/2026 Assembly shares.

**No postal votes.** Form 20 station-level data is EVM only. Postal ballots (typically 1-2% of total) aren't distributed to booths.

**No individual or group vote attribution.** This project shows two independent datasets side by side: registered voter composition and aggregate vote counts. It does not claim to know how any individual, or any demographic group, voted. Inferring that would require ecological inference — a statistical method with strong assumptions that we deliberately do not apply. The data shows correlations at the booth level. Whether those correlations mean anything causal is for you to decide, carefully.

---

## Tech stack

| Layer | Technology |
|---|---|
| Map | Leaflet.js 1.9.4 |
| Basemap | CARTO Positron (light) + Esri satellite |
| Voronoi tessellation | scipy.spatial.Voronoi + shapely concave_hull |
| Data pipeline | Python 3.12 |
| PDF parsing | Custom Form 20 + Electoral Roll extractors |
| Frontend | Vanilla HTML/CSS/JS — no framework, no build step |

---

## Project structure

```
├── site/
│   ├── index.html              # App shell
│   ├── style.css               # Stylesheet
│   ├── app.js                  # Map + sidebar logic
│   └── data.json               # Generated payload (790 KB)
├── scripts/
│   ├── build_data.py           # Pipeline: raw CSVs → data.json
│   ├── ac_config.py            # Constituency registry
│   ├── alliances.py            # Party → alliance + colors
│   ├── parse_form20.py         # Form 20 PDF parser
│   ├── parse_pdf.py            # Candidate extraction
│   ├── parse_booths_ac018.py   # Booth list parser
│   ├── geocode_booths.py       # Tiered geocoding pipeline
│   └── compute_ei.py           # Ecological inference (experimental)
├── data/                       # Source CSVs + JSONs per AC per cycle
├── extracted_pdfs/             # Source Electoral Roll PDFs [gitignored]
└── README.md
```

---

## Quick start

### Just use the live site

Go to **[kaduvan.github.io/voter-patterns](https://kaduvan.github.io/voter-patterns/)** — no setup needed.

### Run locally

```bash
cd site
python -m http.server 8000
# Open http://localhost:8000/
```

### Rebuild from source

```bash
pip install scipy shapely numpy
python scripts/build_data.py
# Output: site/data.json
```

---

## Party colors & alliances

Colors follow established Tamil Nadu political conventions, tuned for the light map theme:

| Alliance | Color | Lead party | Cycles |
|---|---|---|---|
| SPA | 🔴 Red `#E02020` | DMK | 2021, 2024, 2026 |
| NDA | 🟠 Saffron `#FF8C00` | BJP | 2021, 2024 |
| AIADMK | 🟢 Green `#22A84B` | AIADMK | 2021, 2026 |
| TVK | 🟡 Gold `#FFB400` | Tamilaga Vettri Kazhagam | 2026 |
| NTK | 🟢 Dark Green `#1B7F3F` | Naam Tamilar Katchi | All |
| BSP | 🔵 Blue `#1E40D1` | Bahujan Samaj Party | 2021, 2024, 2026 |

Alliance mappings are **cycle-specific** — parties switch fronts between elections. All defined in `scripts/alliances.py`.

---

## Contributing

This project grows one constituency at a time. If you can:

- **Add a constituency** — follow the guide above, open a PR
- **Improve the parsers** — Form 20 and Electoral Roll PDFs vary wildly by state; better parsers mean more constituencies can be processed
- **Improve geocoding** — street-level hit rates are low (~40%); better geocoding means fewer approximate booth locations
- **Add features** — the frontend is vanilla JS, easy to extend
- **Report data errors** — if you spot a mismatch between our data and the official ECI PDFs, open an issue with the booth number and cycle

Every contribution moves the map closer to covering all of India.

---

## License

MIT — free to use, modify, and distribute.

Election data © Election Commission of India. Electoral Roll data © Election Commission of India. Basemap tiles © CARTO, Esri, and OpenStreetMap contributors.
