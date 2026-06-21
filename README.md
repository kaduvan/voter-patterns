# 🗺️ Chennai Booth Analytics — Harbour & Chepauk-Thiruvallikeni

An open-source, interactive booth-level electoral analytics platform for Chennai's coastal constituencies. Every polling booth is a polygon on the map — colored by who won, how decisively, who lives there, and how the neighborhood voted across three election cycles.

🔗 **Live demo: [kaduvan.github.io/voter-patterns](https://kaduvan.github.io/voter-patterns/)**

**Key question this answers:** *How did each polling booth in Harbour and Chepauk-Thiruvallikeni vote in 2021, 2024, and 2026 — and who are the voters behind those numbers?*

---

## 🌟 What This Is

Most election dashboards stop at constituency-level winners. We go deeper — to the **individual polling booth** (Part), the smallest unit where votes are counted and reported in India.

Each booth has:
- **A geographic footprint** — a Voronoi cell clipped to the constituency outline
- **Full vote breakdowns** — candidate-by-candidate vote counts from official ECI Form 20 PDFs
- **Complete voter demographics** — age bands (18–21 through 70+), gender, and cohort analysis from the Electoral Roll
- **Three cycles of history** — 2021 Assembly, 2024 Lok Sabha, and 2026 Assembly

This isn't a prediction tool or a partisan project. It's a transparency tool — built to help citizens, journalists, researchers, and campaigns understand how Chennai votes, booth by booth.

---

## 📖 How to Use

### Getting Started

1. **Open the map** — Simply open `site/index.html` in a modern browser (Chrome recommended)
2. **Explore** — The map (left) shows every booth as a clickable polygon. The sidebar (right) has the analytics.

> 💡 **Tip:** For best performance: `cd site && python -m http.server 8000`, then open `http://localhost:8000/`

### 🗺️ The Map

Each colored polygon is a single polling booth. The color depends on your selected view:

**Votes domain:**
| View | What it shows |
|---|---|
| **Winner** | Each booth colored by its winning alliance. Opacity reflects vote share — darker = landslide, lighter = close contest |
| **Alliance share** | A single alliance's vote share across all booths, on a gradient from low to high |
| **Lead margin** | How decisively the winner won — from razor-thin (dark) to blowout (bright) |

**Demographics domain:**
| View | What it shows |
|---|---|
| **Dominant age** | Modal age band per booth (18-21, 22-29, 30-39, 40-49, 50-59, 60-69, 70+) |
| **Cohort share** | Any age × gender combination's share of voters, on a gradient |
| **Gender ratio** | Male-skew (blue) to female-skew (pink) across booths |
| **Youth / Elderly** | Share of under-30 or 60+ voters per booth |
| **Absolute count** | Raw headcount of a cohort — where voters physically are |
| **Band gender skew** | Gender split within a specific age band |

### 📊 The Sidebar

- **Donut chart** — Real-time alliance breakdown for the selected cycle and constituency. Always visible in the sticky top section.
- **Constituency selector** — Switch between "All" (combined view) or individual constituencies. The map zooms accordingly.
- **Cycle switcher** — 2026 / 2024 / 2021. All views update instantly.
- **Summary cards** — Valid votes, booth coverage, voter demographics at a glance.
- **Top 5 list** — Rankings for the current metric (e.g., "Top 5 booths where SPA leads").
- **Booth detail panel** — Click any booth for a population pyramid, full vote history across cycles, and age-band breakdown.

### Map Controls
- **Satellite toggle** — Switch between CARTO dark basemap and Esri satellite imagery
- **Outlines** — Show/hide constituency boundary
- **Labels** — Show/hide booth part numbers on the map

---

## 🏘️ Constituencies Covered

| Code | Constituency | Lok Sabha | Booths | Voters |
|---|---|---|---|---|
| AC018 | Harbour | Chennai Central | 192 | ~110,000 |
| AC019 | Chepauk-Thiruvallikeni | Chennai Central | 205 | ~132,000 |
| | **Combined** | | **397** | **~242,000** |

The architecture supports adding more constituencies — each AC is a config entry in `scripts/ac_config.py` with its own booth list, demographics file, and Form 20 data.

---

## 📊 Data Sources & Pipeline

### Where the Data Comes From

| Source | What it provides |
|---|---|
| **ECI Form 20 PDFs** | Official station-level vote counts for every candidate (2021, 2024, 2026) |
| **Electoral Roll PDFs** | Per-booth voter demographics: age, gender, and totals |
| **Election Commission Booth Lists** | Polling station names, addresses, and part numbers |
| **Manual Geocoding** | Lat/lon for every booth using a tiered system (street > locality > centroid) |

### How It's Built

```
Form 20 PDFs → Parsed to CSV (candidate × booth votes)
                  ↓
Electoral Roll PDFs → Extracted to age × gender × band per booth
                  ↓
Booth addresses → Geocoded (street-level → locality → AC centroid fallback)
                  ↓
Voronoi tessellation → Each booth gets a polygon, clipped to AC outline
                  ↓
All embedded as JSON → Single self-contained HTML file
```

### Geocoding Tiers

Every booth is geocoded at one of three precision levels:

| Tier | Precision | Method |
|---|---|---|
| `street` | Best | Exact street address matched via multiple geocoding services |
| `locality` | Good | Matched to neighborhood/locality centroid |
| `ac_centroid` | Approximate | Booth location unknown — placed at AC center with reduced opacity |

Hover any booth to see its geocoding tier. Centroid booths are approximate and shown at lower opacity.

---

## ⚠️ Methodology & Limitations

We believe in being honest about what the data can and cannot tell you.

### Voronoi Approximation
Booth polygons are **not official boundaries**. Polling booths in India don't have defined geographic territories. We use Voronoi tessellation from booth coordinates, clipped to the constituency outline. This gives a reasonable visual proxy — not a precise service-area map.

### Geocoding Gaps
Some booths could not be geocoded to street level. These appear at locality centroids or AC center, with reduced opacity. Vote data for these booths is still accurate — only the position is approximate.

### 2024 is Lok Sabha
The 2024 cycle was a Parliamentary (Lok Sabha) election for Chennai Central PC. The booth-level votes are still booth-level — but the contest was PC-wide, not AC-wide. Alliance totals for 2024 reflect the Chennai Central Lok Sabha contest, not an Assembly contest.

### No Postal Votes
Station-level Form 20 data is EVM-only. Postal votes (typically 1-2% of total) are not distributed to individual booths.

### Candidate Name Variations
Names parsed from PDFs may have minor spelling variations across cycles.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Map rendering** | Leaflet.js 1.9.4 (CDN) |
| **Basemaps** | CARTO Dark Matter + Esri World Imagery |
| **Voronoi cells** | scipy.spatial.Voronoi + shapely concave_hull |
| **Data pipeline** | Python 3.12 |
| **PDF parsing** | Custom Form 20 + Electoral Roll extractors |
| **Output** | Single self-contained HTML (~950 KB, all data embedded) |

No build step, no server, no framework. Just Python → HTML.

---

## 📁 Project Structure

```
harbour/
├── site/
│   ├── index.html              # 🗺️ Main app (loads data.json + app.js + style.css)
│   ├── style.css               # Dark theme stylesheet
│   ├── app.js                  # Interactive Leaflet map + sidebar logic
│   └── data.json               # Generated data payload (~790 KB)
├── scripts/
│   ├── build_data.py           # Data pipeline (CSV → data.json)
│   ├── ac_config.py              # AC registry (add constituencies here)
│   ├── alliances.py              # Party → alliance mapping + colors
│   ├── parse_form20.py           # Form 20 PDF → structured votes CSV
│   ├── parse_pdf.py              # Form 20 parser (candidate extraction)
│   ├── parse_booths_ac018.py     # Booth list parser
│   ├── geocode_booths.py         # Tiered geocoding pipeline
│   └── compute_ei.py             # Ecological inference (research)
├── data/
│   ├── votes_ac018_{2021,2024,2026}.csv    # Station-level vote counts
│   ├── votes_ac019_{2021,2024,2026}.csv
│   ├── candidates_ac0{18,19}_{2021,2024,2026}.json   # Candidate metadata
│   ├── booth_coords_ac0{18,19}.csv         # Geocoded booth coordinates
│   ├── booths_ac0{18,19}.csv               # Booth station lists
│   └── street/locality_coords_ac019.csv    # Geocoding reference data
├── extracted_pdfs/               # Source Electoral Roll PDFs [heavy]
└── analysis/                     # Intermediate analysis files
```

---

## 🚀 Quick Start

### Option 1: Just Open the HTML

```bash
# Simply open in a browser
start site/index.html          # Windows
open site/index.html           # macOS
xdg-open site/index.html       # Linux
```

### Option 2: Serve Locally (Recommended)

```bash
cd site
python -m http.server 8000
# Open http://localhost:8000/
```

### Option 3: Rebuild from Source

```bash
# Prerequisites: Python 3.12+, scipy, shapely, numpy
pip install scipy shapely numpy

# Run the build pipeline
python scripts/build_data.py

# Output: site/data.json
```

### Adding a New Constituency

1. Add an entry to the `ACS` dict in `scripts/ac_config.py`:
```python
"AC017": {
    "name": "Your Constituency",
    "prefix": "ac017",
    "center": [13.08, 80.27],
    "booth_list": "data/booths_ac017.csv",
    "demographics": "data/demographics_ac017.csv",
    # ... form20 paths
}
```

2. Prepare data files: `booth_coords_ac017.csv`, `votes_ac017_{year}.csv`, `candidates_ac017_{year}.json`

3. Rebuild: `python scripts/build_data.py`

The AC selector, donut chart, summaries, and map all update automatically.

---

## 🎨 Party Colors & Alliances

Alliance colors are tuned for the dark map theme and follow established Tamil Nadu political conventions:

| Alliance | Color | Lead party | Cycles |
|---|---|---|---|
| SPA | 🔴 Red `#E02020` | DMK | 2021, 2024, 2026 |
| NDA | 🟠 Saffron `#FF8C00` | BJP | 2021, 2024 |
| AIADMK | 🟢 Green `#22A84B` | AIADMK (contested alone 2026) | 2021, 2026 |
| TVK | 🟡 Gold `#FFB400` | Tamilaga Vettri Kazhagam | 2026 |
| NTK | 🟢 Dark Green `#1B7F3F` | Naam Tamilar Katchi | All |
| BSP | 🔵 Blue `#1E40D1` | Bahujan Samaj Party | 2021, 2024, 2026 |

Alliance mappings are **cycle-specific** — parties switch fronts between elections. All mappings are defined in `scripts/alliances.py`.

---

## 📈 Why This Matters

Election data in India is published as dense PDFs — hundreds of pages, unsearchable, impossible to analyze at scale without significant technical work. This creates an information asymmetry: parties and well-funded campaigns can afford to process this data, but ordinary citizens, journalists, and grassroots organizations cannot.

This project is one small step toward closing that gap. By transforming official ECI data into an interactive, visual, booth-level platform, we make it possible for anyone to:

- **See how their neighborhood voted** — not just the constituency total
- **Identify patterns** — which booths swing, which are consistent, where turnout matters
- **Hold representatives accountable** — with granular, verifiable data
- **Understand voter demographics** — who lives where, and how that correlates with voting

If you believe in electoral transparency, open government data, and civic empowerment — this is for you.

---

## License

MIT — free to use, modify, and distribute. Attribution appreciated but not required.

Election data © Election Commission of India. Basemap tiles © CARTO, Esri, and OpenStreetMap contributors.
