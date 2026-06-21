# voter-patterns

**Booth-level electoral data for Chennai — official vote counts and registered voter demographics, side by side across three elections.**

🔗 **Live: [kaduvan.github.io/voter-patterns](https://kaduvan.github.io/voter-patterns/)**

---

## Why this exists

I built [electoral-analytics](https://github.com/kaduvan/electoral-analytics) to map the 2026 Tamil Nadu election across all 234 constituencies — village by village, statewide. It answered a broad question: *who won where?*

But electoral results only tell you one thing: aggregate vote counts. They don't tell you who the electors in a booth are — their age, their gender, the generational makeup of a neighborhood. That information lives in a separate official document: the Electoral Roll.

This project takes two constituencies — Harbour (AC018) and Chepauk-Thiruvallikeni (AC019), both in Chennai Central — and brings both datasets together at the most granular level where they overlap: the individual polling booth. Form 20 tells you how many votes each candidate got. The Electoral Roll tells you how many registered voters fall into each age and gender band. Shown side by side, they give a fuller picture of a booth than either can alone.

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

| Code | Constituency | Lok Sabha | Booths | Voters |
|---|---|---|---|---|
| AC018 | Harbour | Chennai Central | 192 | ~110,000 |
| AC019 | Chepauk-Thiruvallikeni | Chennai Central | 205 | ~132,000 |
| | **Combined** | | **397** | **~242,000** |

Both are coastal Chennai constituencies — densely populated, politically competitive, and historically significant. Harbour covers the port and old trading quarters. Chepauk-Thiruvallikeni includes Triplicane, Royapettah, and the Marina beachfront.

Adding more constituencies is straightforward — each AC is a config entry with its own booth list, demographics file, and Form 20 data.

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
│   ├── style.css               # Dark theme
│   ├── app.js                  # Map + sidebar logic
│   └── data.json               # Generated payload (790 KB)
├── scripts/
│   ├── build_data.py           # Pipeline: CSV → data.json
│   ├── ac_config.py            # Constituency registry
│   ├── alliances.py            # Party → alliance + colors
│   ├── parse_form20.py         # Form 20 PDF parser
│   ├── parse_pdf.py            # Candidate extraction
│   ├── geocode_booths.py       # Tiered geocoding
│   └── compute_ei.py           # Ecological inference (research)
├── data/                       # Source CSVs + JSONs
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

### Add a constituency

1. Add an entry to `scripts/ac_config.py`
2. Prepare data files: `booth_coords_acXXX.csv`, `votes_acXXX_{year}.csv`, `candidates_acXXX_{year}.json`, demographics CSV
3. Run `python scripts/build_data.py`

The AC selector, donut chart, summaries, and map update automatically.

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

## License

MIT — free to use, modify, and distribute.

Election data © Election Commission of India. Electoral Roll data © Election Commission of India. Basemap tiles © CARTO, Esri, and OpenStreetMap contributors.
