# voter-patterns

**Booth-level electoral intelligence for Chennai — who voted, where they live, and how it shifted across three elections.**

🔗 **Live: [kaduvan.github.io/voter-patterns](https://kaduvan.github.io/voter-patterns/)**

---

## Why this exists

I built [electoral-analytics](https://github.com/kaduvan/electoral-analytics) to map the 2026 Tamil Nadu election across all 234 constituencies — village by village, statewide. It answered a broad question: *who won where?*

But the closer you look at an election, the more you realize that constituency-level and even village-level results only tell you half the story. They tell you **how people voted**. They don't tell you **who those voters are** — their age, their gender, the generational makeup of a neighborhood. Without the Electoral Roll, you're looking at outcomes without the people behind them.

**voter-patterns** is the project that fixes that. It takes two constituencies — Harbour (AC018) and Chepauk-Thiruvallikeni (AC019), both in Chennai Central — and goes all the way down to the individual polling booth. Not just *who won this street*, but *who lives on this street, and did they change their mind?*

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
| **Time depth** | Single snapshot | Track how the same booth shifted across 5 years |
| **File size** | 39.5 MB monolith | 790 KB data + modular HTML/CSS/JS |

**In short:** electoral-analytics is breadth (the whole state). voter-patterns is depth (every booth, every voter, every cycle). They're complementary — use electoral-analytics to see the macro picture, then drop into voter-patterns when you need to understand *why* a neighborhood voted the way it did.

The reason this is a separate repo, not a feature added to electoral-analytics, is that they solve fundamentally different problems with different data pipelines. electoral-analytics aggregates Form 20 PDFs statewide. voter-patterns merges two independent datasets — the Electoral Roll (who can vote) and Form 20 (how they voted) — at the most granular level possible. The architecture, data sources, and analysis are distinct enough that forcing them together would compromise both.

---

## What you can explore

**397 polling booths** across two constituencies, each rendered as an interactive Voronoi cell on a light basemap. Click any booth to see:

### 🗳️ Votes (from Form 20)
- Winner by alliance, with opacity scaled to vote share
- Alliance-specific share maps (e.g., "where is TVK strongest?")
- Lead margins — from razor-thin to landslide
- Full vote breakdowns across all 3 cycles (2021, 2024, 2026)

### 👥 Demographics (from the Electoral Roll)
- Dominant age band per booth (18-21 through 70+)
- Cohort share — any age × gender combination
- Gender ratio mapping (male-skew to female-skew)
- Youth (<30) and elderly (60+) concentration
- Absolute voter counts — where people physically are
- Population pyramids on booth click

### 📊 Analytics
- Donut chart showing alliance breakdown for any cycle/constituency
- Summary cards: valid votes, voter counts, youth/elderly share
- Top 5 rankings for any metric
- Per-constituency split when viewing all constituencies combined

---

## The two datasets — and why they're independent

This is the most important thing to understand about this project:

**The Electoral Roll** describes *who is registered to vote* — name, age, gender, address. It's a census of eligible voters, published as PDFs by the Election Commission.

**Form 20** describes *how votes were cast* — candidate-by-candidate counts at each polling station, EVM only.

These are **two completely independent datasets**. The Electoral Roll doesn't tell you how someone voted (that's a secret ballot). Form 20 doesn't tell you who the voters are (just how many voted for each candidate). By merging them at the booth level — the only unit where both datasets overlap — we can ask questions that neither can answer alone:

- *Do younger neighborhoods vote differently than older ones?*
- *Did the booths with the most first-time voters shift between 2021 and 2026?*
- *Where are the gender gaps, and do they correlate with political outcomes?*

Every booth detail panel labels its data sources explicitly, because conflating "who can vote" with "how they voted" is the fastest way to draw wrong conclusions.

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

**No individual vote attribution.** This project merges demographics (who voters *are*) with results (how the booth *voted*). It cannot and does not claim to know how any individual voted — that's protected by secret ballot. The demographic patterns are ecological, not individual.

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
