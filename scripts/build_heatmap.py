#!/usr/bin/env python3
"""
Build the unified multi-AC booth analytics heatmap — demographics + votes.

Combines all constituencies from ac_config.ACS into a single self-contained
Leaflet HTML. Each booth gets a Voronoi cell clipped to its AC outline.
An AC selector lets the user filter summaries/headlines/legends to one AC
or view all constituencies combined.

Usage: python scripts/build_heatmap.py
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np
import shapely
from scipy.spatial import Voronoi
from shapely.geometry import MultiPoint, Polygon, box, mapping
from shapely.ops import transform as shp_transform

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ac_config
from alliances import alliance_for, ALLIANCE_COLORS, PARTY_COLORS

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"

AGE_BANDS = ["18-21", "22-29", "30-39", "40-49", "50-59", "60-69", "70+"]
BAND_COLORS = {
    "18-21": "#ff00ff", "22-29": "#ff6db6", "30-39": "#fee08b",
    "40-49": "#a6d96a", "50-59": "#1a9850", "60-69": "#4575b4", "70+": "#313695",
}
HULL_RATIO = 0.2
HULL_BUFFER = 0.0006
SLIVER_AREA = 1e-7
SIMPLIFY_TOL = 0.000008  # ~0.9m
COORD_DECIMALS = 5  # 1.1m precision
TOP_SHARES = 5  # keep top-N shares per booth
CYCLES = [2026, 2024, 2021]


def build_voronoi_cells(points_latlon):
    pts_geo = [(p[1], p[0]) for p in points_latlon]
    hull = shapely.concave_hull(MultiPoint(pts_geo),
                                ratio=HULL_RATIO, allow_holes=False).buffer(HULL_BUFFER)
    center = points_latlon.mean(axis=0)
    far = center + np.array([[100, 100], [100, -100], [-100, 100], [-100, -100]])
    vor = Voronoi(np.vstack([points_latlon, far]))
    cells = []
    for i in range(len(points_latlon)):
        region = vor.regions[vor.point_region[i]]
        if not region or -1 in region:
            cells.append(None); continue
        poly = Polygon([(vor.vertices[k, 1], vor.vertices[k, 0]) for k in region])
        if not poly.is_valid:
            poly = poly.buffer(0)
        clipped = poly.intersection(hull)
        if clipped.is_empty:
            cells.append(None); continue
        if clipped.geom_type == "MultiPolygon":
            clipped = max(clipped.geoms, key=lambda g: g.area)
        if clipped.area < SLIVER_AREA:
            cells.append(None); continue
        cells.append(clipped)
    return cells, hull


def load_coords(prefix):
    with open(DATA / f"booth_coords_{prefix}.csv", encoding="utf-8") as f:
        return {int(r["part_no"]): r for r in csv.DictReader(f)}


def load_demographics(path):
    out = {}
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            out[int(r["booth_number"])] = r
    return out


def load_votes(year, prefix):
    cpath = DATA / f"candidates_{prefix}_{year}.json"
    vpath = DATA / f"votes_{prefix}_{year}.csv"
    if not cpath.exists() or not vpath.exists():
        return {}, []
    cands = json.load(open(cpath, encoding="utf-8"))
    votes = {}
    with open(vpath, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            votes[int(r["station_no"])] = r
    return votes, cands


def alliance_vote_shares(votes_row, cands, year):
    total_valid = int(votes_row.get("total_valid", 0) or 0)
    if total_valid <= 0:
        return {}
    alliance_votes = {}
    for c in cands:
        v = int(votes_row.get(c["name"], 0) or 0)
        if v <= 0:
            continue
        a = alliance_for(c["party"], year)
        alliance_votes[a] = alliance_votes.get(a, 0) + v
    return {a: v / total_valid for a, v in alliance_votes.items()}


def build_one(ac_name):
    """Build features, hull geojson, cycle summary, and meta for a single AC."""
    cfg = ac_config.get(ac_name)
    prefix = cfg["prefix"]
    coords = load_coords(prefix)
    demo = load_demographics(cfg["demographics"])
    common = sorted(set(coords) & set(demo))

    points = np.array([[float(coords[p]["lat"]), float(coords[p]["lon"])] for p in common])
    cells, hull = build_voronoi_cells(points)

    # Load all vote cycles
    votes_by_year = {}
    for y in CYCLES:
        v, c = load_votes(y, prefix)
        if v:
            votes_by_year[y] = {"votes": v, "cands": c}

    features = []
    for idx, part_no in enumerate(common):
        cell = cells[idx]
        if cell is None:
            d = 0.0002
            geom = box(float(coords[part_no]["lon"]) - d, float(coords[part_no]["lat"]) - d,
                       float(coords[part_no]["lon"]) + d, float(coords[part_no]["lat"]) + d)
        else:
            geom = cell.simplify(SIMPLIFY_TOL, preserve_topology=True)
        def _round_coords(g):
            return shp_transform(lambda x, y, z=None: (round(x, COORD_DECIMALS), round(y, COORD_DECIMALS)), g)
        geom = _round_coords(geom)

        c = coords[part_no]
        dd = demo[part_no]
        bands = {b: {"Male": int(dd[f"{b}_Male"]), "Female": int(dd[f"{b}_Female"]),
                     "Total": int(dd[f"{b}_Total"])} for b in AGE_BANDS}
        band_totals = {b: bands[b]["Total"] for b in AGE_BANDS}
        dominant_band = max(band_totals, key=band_totals.get)
        total = int(dd["Booth_Total"])
        mfe = int(dd["Booth_Total_Male"]) + int(dd["Booth_Total_Female"])
        male_ratio = round(int(dd["Booth_Total_Male"]) / mfe, 4) if mfe else 0.5
        youth_share = round((band_totals["18-21"] + band_totals["22-29"]) / total, 4) if total else 0.0
        elderly_share = round((band_totals["60-69"] + band_totals["70+"]) / total, 4) if total else 0.0

        band_gender_skew = {}
        for b in AGE_BANDS:
            bt = bands[b]["Male"] + bands[b]["Female"]
            band_gender_skew[b] = round(bands[b]["Male"] / bt, 4) if bt else 0.5

        cycle_votes = {}
        for y, vd in votes_by_year.items():
            vrow = vd["votes"].get(part_no)
            if vrow:
                shares = alliance_vote_shares(vrow, vd["cands"], y)
                if shares:
                    winner = max(shares, key=shares.get)
                    sorted_shares = sorted(shares.values(), reverse=True)
                    margin = sorted_shares[0] - (sorted_shares[1] if len(sorted_shares) > 1 else 0)
                    top = dict(sorted(shares.items(), key=lambda x: -x[1])[:TOP_SHARES])
                    if winner not in top:
                        top[winner] = shares[winner]
                    cycle_votes[y] = {"shares": top, "winner": winner,
                                      "margin": round(margin, 4)}

        cohort_shares = {}
        for b in AGE_BANDS + ["All"]:
            for sex in ["Male", "Female", "All"]:
                if b == "All" and sex == "All":
                    cnt = total
                elif b == "All":
                    cnt = sum(bands[bb][sex] for bb in AGE_BANDS)
                elif sex == "All":
                    cnt = bands[b]["Total"]
                else:
                    cnt = bands[b][sex]
                cohort_shares[f"{b}|{sex}"] = round(cnt / total, 4) if total else 0.0

        props = {
            "uid": f"{ac_name}_{part_no}",
            "part_no": part_no, "ac": ac_name,
            "tier": c["tier"], "street": c["street"],
            "locality": c["locality"], "door_no": c["door_no"],
            "total": total, "total_male": int(dd["Booth_Total_Male"]),
            "total_female": int(dd["Booth_Total_Female"]),
            "bands": bands,
            "dominant_band": dominant_band, "male_ratio": male_ratio,
            "youth_share": youth_share, "elderly_share": elderly_share,
            "band_gender_skew": band_gender_skew,
            "cohort_shares": cohort_shares,
            "votes": cycle_votes,
        }
        features.append({"type": "Feature", "geometry": mapping(geom), "properties": props})

    # per-AC cycle summary (with raw alliance vote totals for cross-AC merging)
    cycle_summary = {}
    for y, vd in votes_by_year.items():
        alliance_totals = {}
        tot = 0
        for part_no in common:
            vrow = vd["votes"].get(part_no)
            if not vrow:
                continue
            tv = int(vrow.get("total_valid", 0) or 0)
            tot += tv
            for c in vd["cands"]:
                v = int(vrow.get(c["name"], 0) or 0)
                if v > 0:
                    a = alliance_for(c["party"], y)
                    alliance_totals[a] = alliance_totals.get(a, 0) + v
        cycle_summary[y] = {
            "alliance_shares": {a: round(v / tot, 4) for a, v in alliance_totals.items()},
            "total_valid": tot,
            "winner": max(alliance_totals, key=alliance_totals.get) if alliance_totals else None,
            "_raw": alliance_totals,
        }

    meta = {
        "name": cfg["name"],
        "code": ac_name,
        "pc": cfg["pc"],
        "center": list(cfg["center"]),
        "n_booths": len(common),
        "n_voters": sum(int(demo[p]["Booth_Total"]) for p in common),
        "hull_idx": None,
    }
    return features, mapping(hull), cycle_summary, meta


def build_all():
    all_features = []
    all_hulls = []
    ac_summaries = {}
    ac_meta = {}

    for ac_name in ac_config.ACS:
        features, hull_geojson, summary, meta = build_one(ac_name)
        meta["hull_idx"] = len(all_hulls)
        all_features.extend(features)
        all_hulls.append(hull_geojson)
        ac_summaries[ac_name] = summary
        ac_meta[ac_name] = meta
        print(f"  {ac_name} ({meta['name']}): {meta['n_booths']} booths, "
              f"winners {[(y, s['winner']) for y, s in summary.items()]}")

    # Combined "ALL" cycle summaries (aggregate raw vote counts across ACs)
    all_summaries = {}
    for y in CYCLES:
        combined = {}
        combined_valid = 0
        for ac in ac_config.ACS:
            if y in ac_summaries[ac]:
                for a, v in ac_summaries[ac][y].get("_raw", {}).items():
                    combined[a] = combined.get(a, 0) + v
                combined_valid += ac_summaries[ac][y]["total_valid"]
        if combined_valid > 0:
            all_summaries[y] = {
                "alliance_shares": {a: round(v / combined_valid, 4) for a, v in combined.items()},
                "total_valid": combined_valid,
                "winner": max(combined, key=combined.get) if combined else None,
            }

    # Strip _raw from ac_summaries (not needed in JSON output)
    for ac in ac_summaries:
        for y in ac_summaries[ac]:
            ac_summaries[ac][y].pop("_raw", None)

    # Map center = mean of all AC centers
    all_centers = np.array([m["center"] for m in ac_meta.values()])
    map_center = all_centers.mean(axis=0).tolist()

    all_cycles = sorted(set(y for s in ac_summaries.values() for y in s.keys()), reverse=True)

    payload = {
        "geojson": {"type": "FeatureCollection", "features": all_features},
        "hulls": all_hulls,
        "acs": ac_meta,
        "ac_summaries": ac_summaries,
        "all_summaries": all_summaries,
        "cycles": all_cycles,
        "center": map_center,
        "n_booths": len(all_features),
        "n_voters": sum(m["n_voters"] for m in ac_meta.values()),
        "age_bands": AGE_BANDS,
        "band_colors": BAND_COLORS,
        "alliance_colors": ALLIANCE_COLORS,
    }
    return payload


def write_html(payload):
    data_js = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    html = build_html(data_js)
    out = BASE / "site" / "heatmap.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"Wrote {out} ({out.stat().st_size/1024:.0f} KB)")


def build_html(data_js):
    body = _HTML_BODY.replace("__DATA__", data_js)
    return _HTML_HEADER + _CSS + body


_HTML_HEADER = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Chennai Booth Analytics</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
"""

_HTML_BODY = r"""
</style>
</head>
<body>
<div class="topbar">
  <h1>Chennai Booth Analytics</h1>
  <div class="headline" id="headline"></div>
  <div class="stats" id="stats"></div>
</div>
<div class="app">
  <div id="map"></div>
  <div class="sidebar">
    <div class="sb-sticky">
      <div class="sb-sticky-pad">
        <h3>Constituency</h3>
        <div id="acBtns" class="ac-row"></div>
      </div>
      <div class="sb-sticky-pad">
        <div id="donut" class="donut-section"></div>
      </div>
    </div>
    <div class="sb-scroll">

    <h3>Domain</h3>
    <div class="mode-grid">
      <button class="domain-btn active" data-domain="votes">🗳 votes</button>
      <button class="domain-btn" data-domain="demo">👥 demographics</button>
    </div>

    <div id="votesControls">
      <div class="section">
        <h3>Election cycle</h3>
        <div id="cycleBtns" class="cycle-row"></div>
      </div>
      <div class="section">
        <h3>Votes view</h3>
        <div class="mode-grid">
          <button class="vmode-btn active" data-vmode="winner">winner</button>
          <button class="vmode-btn" data-vmode="share">alliance share</button>
          <button class="vmode-btn" data-vmode="margin">lead margin</button>
        </div>
      </div>
      <div id="shareControls" class="section" style="display:none">
        <h3>Alliance</h3>
        <div id="allianceBtns"></div>
      </div>
    </div>

    <div id="demoControls" style="display:none">
      <div class="section">
        <h3>Demographics view</h3>
        <div class="mode-grid">
          <button class="dmode-btn active" data-dmode="dominant">dominant age</button>
          <button class="dmode-btn" data-dmode="cohort">cohort share</button>
          <button class="dmode-btn" data-dmode="gender">gender ratio</button>
          <button class="dmode-btn" data-dmode="youth">youth/elderly</button>
          <button class="dmode-btn" data-dmode="absolute">absolute count</button>
          <button class="dmode-btn" data-dmode="bandskew">band gender skew</button>
        </div>
      </div>
      <div id="cohortControls" class="section" style="display:none">
        <h3>Cohort</h3>
        <div style="display:flex;gap:14px">
          <div style="flex:1">
            <div class="mini">SEX</div>
            <label><input type="radio" name="sex" value="All" checked> All</label>
            <label><input type="radio" name="sex" value="Male"> Male</label>
            <label><input type="radio" name="sex" value="Female"> Female</label>
          </div>
          <div style="flex:1.4">
            <div class="mini">AGE</div>
            <div id="ageBtns"></div>
            <label><input type="radio" name="age" value="All"> all ages</label>
          </div>
        </div>
      </div>
      <div id="youthControls" class="section" style="display:none">
        <h3>Age axis</h3>
        <label><input type="radio" name="yaxis" value="youth_share" checked> Youth (&lt;30)</label>
        <label><input type="radio" name="yaxis" value="elderly_share"> Elderly (60+)</label>
      </div>
      <div id="absControls" class="section" style="display:none">
        <h3>Count of</h3>
        <div id="absBtns"></div>
      </div>
      <div id="skewControls" class="section" style="display:none">
        <h3>Age band</h3>
        <div id="skewBtns"></div>
      </div>
    </div>

    <div class="section">
      <h3 id="legendTitle">Legend</h3>
      <div id="legendBody"></div>
    </div>
    <div class="section">
      <h3>Summary</h3>
      <div class="cards" id="cards"></div>
      <div class="toplist" id="toplist"></div>
    </div>
    <div class="section">
      <h3>Layers</h3>
      <div class="toggle-row">
        <label><input type="checkbox" id="baseToggle"> satellite</label>
        <label><input type="checkbox" id="showOutline" checked> outlines</label>
        <label><input type="checkbox" id="showLabels"> labels</label>
      </div>
      <div class="tier-note" id="tierNote"></div>
    </div>
    <div class="section">
      <h3>Data &amp; Limitations</h3>
      <div class="limits-note">
        <div><b>Demo</b> = Electoral Roll (registered voters). <b>Votes</b> = Form 20 (EVM ballots). Independent datasets.</div>
        <div><b>Voronoi cells</b> are approximations, not official booth boundaries.</div>
        <div><b>Centroid</b> booths (faded) have unknown precise locations.</div>
        <div><b>2024</b> is Lok Sabha (Chennai Central PC), not Assembly.</div>
        <div><b>No postal ballots</b> in booth-level data.</div>
      </div>
    </div>
  </div></div>
  <div class="info-panel" id="infoPanel">
    <div class="mini" style="color:var(--accent);margin-bottom:6px">BOOTH DETAIL</div>
    <div style="display:flex;justify-content:space-between;align-items:center">
      <h4 id="infoTitle"></h4>
      <button id="closeInfo" class="xbtn">&times;</button>
    </div>
    <div class="sub" id="infoSub"></div>
    <div class="src-label">👥 ELECTORAL ROLL &mdash; Age &times; gender distribution</div>
    <div class="pyramid" id="pyramid"></div>
    <table id="infoTable"></table>
    <div id="infoVotes"></div>
  </div>
</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const P = __DATA__;
// ---- state ----
let selectedAc = 'ALL';
let domain = 'votes', cycle = P.cycles[0];
let vmode = 'winner', valliance = null;
let dmode = 'dominant', dage = '18-21', dsex = 'All', dyaxis = 'youth_share';
let dabs = '18-21', dskew = '18-21';
let selPart = null, cellLayer = null, outlineLayer = null, labelLayer = null;
let baseGrey, baseSat, baseActive;
let legFilter = null;

// ---- helpers: AC filtering ----
function visFeatures() {
  if (selectedAc === 'ALL') return P.geojson.features;
  return P.geojson.features.filter(f => f.properties.ac === selectedAc);
}
function getCs(yr) {
  const tbl = selectedAc === 'ALL' ? P.all_summaries : P.ac_summaries[selectedAc];
  return tbl ? tbl[yr] : null;
}
function selAcName() {
  if (selectedAc === 'ALL') return 'all constituencies';
  return P.acs[selectedAc].name;
}
function legFilteredFeatures() {
  const fs = visFeatures();
  if (legFilter === null) return fs;
  if (domain==='votes') return fs.filter(f=>{const cv=f.properties.votes[cycle];return cv && cv.winner===legFilter;});
  if (dmode==='dominant') return fs.filter(f=>f.properties.dominant_band===legFilter);
  return fs;
}

document.getElementById('tierNote').innerHTML =
  'Each polygon is a booth Voronoi cell clipped to its AC outline. ' +
  'Geocoding tier shown on hover; <b>centroid</b> booths are approximate.';

const map = L.map('map', {zoomControl:true}).setView(P.center, 13);
baseGrey = L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
  {attribution:'&copy; CARTO &copy; OSM', maxZoom:20});
baseSat = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
  {attribution:'&copy; Esri', maxZoom:19});
baseActive = baseGrey; baseGrey.addTo(map);

// ---- color helpers ----
function hexToRgb(h){h=h.replace('#','');return [parseInt(h.slice(0,2),16),parseInt(h.slice(2,4),16),parseInt(h.slice(4,6),16)];}
function rgb(a){return 'rgb('+a[0]+','+a[1]+','+a[2]+')';}
function seqColor(t,stops){t=Math.max(0,Math.min(1,t));let i=t<0.5?0:1,f=t<0.5?t*2:(t-0.5)*2;const a=stops[i][1],b=stops[i+1][1];return rgb([Math.round(a[0]+(b[0]-a[0])*f),Math.round(a[1]+(b[1]-a[1])*f),Math.round(a[2]+(b[2]-a[2])*f)]);}
const SEQ = {
  lowHigh:[[0,hexToRgb('#1a1a2e')],[0.5,hexToRgb('#4fc3f7')],[1,hexToRgb('#fff176')]],
  youth:[[0,hexToRgb('#0d1b2a')],[0.5,hexToRgb('#2ec4b6')],[1,hexToRgb('#ffd166')]],
  elder:[[0,hexToRgb('#0d1b2a')],[0.5,hexToRgb('#9d4edd')],[1,hexToRgb('#ffd166')]],
  gender:[[0,hexToRgb('#ec4899')],[0.5,hexToRgb('#c8c8d0')],[1,hexToRgb('#4fc3f7')]],
  margin:[[0,hexToRgb('#1a1a2e')],[0.5,hexToRgb('#ffa726')],[1,hexToRgb('#e53935')]],
};
function tierOpacity(p){return p.tier==='ac_centroid'?0.5:(p.tier==='locality'?0.75:0.88);}
function rangeOf(getter){let mn=1e9,mx=-1e9;for(const f of visFeatures()){const v=getter(f.properties);if(v==null)continue;if(v<mn)mn=v;if(v>mx)mx=v;}return [mn,mx];}

function colorOf(p) {
  if (domain==='demo') {
    if (dmode==='dominant') return P.band_colors[p.dominant_band]||'#666';
    if (dmode==='gender') return seqColor((p.male_ratio-0.40)/0.20, SEQ.gender);
    if (dmode==='youth') {
      const [mn,mx]=rangeOf(x=>x[dyaxis]);
      return seqColor((p[dyaxis]-mn)/Math.max(mx-mn,1e-6), dyaxis==='youth_share'?SEQ.youth:SEQ.elder);
    }
    if (dmode==='absolute') {
      const key = dabs+'|All';
      const [mn,mx]=rangeOf(x=>x.cohort_shares[key]*x.total);
      const v = p.cohort_shares[key]*p.total;
      return seqColor((v-mn)/Math.max(mx-mn,1e-6), SEQ.lowHigh);
    }
    if (dmode==='bandskew') {
      const v = p.band_gender_skew[dskew];
      return seqColor((v-0.40)/0.20, SEQ.gender);
    }
    if (dmode==='cohort') {
      const m = cohortMean();
      const v = (p.cohort_shares[dage+'|'+dsex]||0);
      return seqColor((v/Math.max(m,1e-6)-0.4)/1.2, SEQ.lowHigh);
    }
  } else {
    const cv = p.votes[cycle];
    if (!cv) return '#333';
    if (vmode==='winner') return P.alliance_colors[cv.winner]||'#888';
    if (vmode==='margin') return seqColor(cv.margin, SEQ.margin);
    if (vmode==='share') {
      const s = cv.shares[valliance]||0;
      return seqColor(s/0.7, SEQ.lowHigh);
    }
  }
  return '#666';
}
function cohortMean(){const k=dage+'|'+dsex;let s=0;const fs=visFeatures();for(const f of fs)s+=f.properties.cohort_shares[k]||0;return fs.length?s/fs.length:0;}
function valueStr(p){
  if (domain==='demo') {
    if (dmode==='dominant') return p.dominant_band;
    if (dmode==='gender') return (p.male_ratio*100).toFixed(1)+'% M';
    if (dmode==='youth') return (p[dyaxis]*100).toFixed(1)+'%';
    if (dmode==='absolute') return Math.round(p.cohort_shares[dabs+'|All']*p.total);
    if (dmode==='bandskew') return (p.band_gender_skew[dskew]*100).toFixed(1)+'% M';
    if (dmode==='cohort') return ((p.cohort_shares[dage+'|'+dsex]||0)*100).toFixed(1)+'%';
  } else {
    const cv=p.votes[cycle]; if(!cv) return 'no data';
    if (vmode==='winner') return cv.winner+' ('+(cv.shares[cv.winner]*100).toFixed(0)+'%)';
    if (vmode==='margin') return (cv.margin*100).toFixed(1)+'% lead';
    if (vmode==='share') return ((cv.shares[valliance]||0)*100).toFixed(1)+'%';
  }
}
function styleOf(feat){
  const p=feat.properties; const sel=selPart!==null&&p.uid===selPart;
  const dimmed = selectedAc!=='ALL' && p.ac!==selectedAc;
  let fo=tierOpacity(p);
  if(domain==='votes'&&vmode==='winner'&&p.votes[cycle]){
    const sh=p.votes[cycle].shares[p.votes[cycle].winner];
    fo=0.30+sh*0.65;
  }
  return {fillColor:colorOf(p),weight:sel?2.5:0.6,color:sel?'#1565c0':'rgba(50,50,50,0.35)',
          opacity:dimmed?0.2:0.85,fillOpacity:dimmed?0.08:Math.min(fo,0.95)};
}

function render(){
  if(cellLayer)cellLayer.remove();
  const visFC={type:'FeatureCollection',features:visFeatures()};
  cellLayer=L.geoJSON(visFC,{style:styleOf,
    onEachFeature:(feat,layer)=>{
      layer.on({
        mouseover:e=>{e.target.setStyle({weight:2,color:'#1565c0',opacity:1,fillOpacity:Math.min(1,tierOpacity(feat.properties)+0.12)});e.target.bringToFront();},
        mouseout:e=>{if(feat.properties.uid!==selPart)cellLayer.resetStyle(e.target);},
        click:e=>{selectBooth(feat.properties.uid);L.DomEvent.stopPropagation(e);}
      });
      const p=feat.properties;
      layer.bindTooltip('<b>'+p.ac+' Part '+p.part_no+'</b> &middot; '+(p.street||p.locality||'?')+'<br>'+valueStr(p)+' &middot; '+p.tier,{direction:'top',className:'ac18'});
    }
  }).addTo(map);
  if(outlineLayer)outlineLayer.eachLayer(l=>l.bringToFront&&l.bringToFront());
  renderLegend(); renderSummary(); renderHeadline(); renderDonut();
  if(labelLayer){labelLayer.remove();labelLayer=null;renderLabels();}
}

function renderHeadline(){
  let h='';
  if(legFilter!==null){
    const fs=legFilteredFeatures();
    if(domain==='votes'){
      h='Filtered: <b>'+fs.length+' booths</b> where '+legFilter+' won in '+cycle;
    } else {
      h='Filtered: <b>'+fs.length+' booths</b> with dominant age band '+legFilter;
    }
    document.getElementById('headline').innerHTML=h;return;
  }
  if(domain==='votes'){
    const cs=getCs(cycle);
    if(cs){
      const sorted=Object.entries(cs.alliance_shares).sort((a,b)=>b[1]-a[1]);
      const top=sorted[0], sec=sorted[1];
      h='<span style="color:'+(P.alliance_colors[top[0]]||'#fff')+';font-weight:600">'+top[0]+'</span> led '+
        selAcName()+' '+cycle+' with '+(top[1]*100).toFixed(1)+'% of valid votes';
      if(sec) h+=', '+(P.alliance_colors[sec[0]]?'<span style="color:'+P.alliance_colors[sec[0]]+'">'+sec[0]+'</span>':sec[0])+' was second at '+(sec[1]*100).toFixed(1)+'%';
    }
  } else {
    if(dmode==='youth'){
      const label=dyaxis==='youth_share'?'young voters':'elderly voters';
      let top=null;for(const f of visFeatures()){const v=f.properties[dyaxis];if(!top||v>top.v)top={v,p:f.properties};}
      h=top?'Most '+label+': <b>Part '+top.p.part_no+'</b> ('+(top.v*100).toFixed(1)+'%) &mdash; '+(top.p.street||top.p.locality||''):'';
    } else if(dmode==='gender'){
      let mostM=null,mostF=null;
      for(const f of visFeatures()){const p=f.properties;if(!mostM||p.male_ratio>mostM.v)mostM={v:p.male_ratio,p};if(!mostF||p.male_ratio<mostF.v)mostF={v:p.male_ratio,p};}
      h=mostM?'Most male-skewed: <b>Part '+mostM.p.part_no+'</b> ('+(mostM.v*100).toFixed(0)+'% M) &middot; Most female-skewed: <b>Part '+mostF.p.part_no+'</b> ('+(mostF.v*100).toFixed(0)+'% M)':'';
    } else if(dmode==='dominant'){
      h='Most booths have modal age band 40-49 (typical for Chennai). Switch to <b>youth/elderly</b> or <b>cohort share</b> to see variation.';
    } else if(dmode==='cohort'){
      const m=cohortMean();h='Average '+selAcName()+' booth: '+dsex.toLowerCase()+' '+dage+' = '+(m*100).toFixed(1)+'% of voters.';
    } else if(dmode==='absolute'){
      h='Largest '+dabs+' cohort by raw count. Useful for finding where most young/old voters physically are.';
    } else if(dmode==='bandskew'){
      h='Where the '+dskew+' age band is unusually male (blue) vs female (pink).';
    }
  }
  document.getElementById('headline').innerHTML=h;
}

function renderLegend(){
  let html='', title='';
  if(domain==='votes'){
    if(vmode==='winner'){title='Winner by alliance \u2014 click to filter';
      const cs=getCs(cycle);
      if(cs){const sorted=Object.entries(cs.alliance_shares).sort((a,b)=>b[1]-a[1]);const top=sorted.slice(0,6);const rest=sorted.slice(6);const restPct=rest.reduce((s,[,v])=>s+v,0);
        html='<div class="legend-cats">'+top.map(([a,s])=>'<span class="leg-click'+(legFilter===a?' active':'')+'" data-leg="'+a+'"><i style="background:'+(P.alliance_colors[a]||'#888')+'"></i>'+a+' ('+(s*100).toFixed(1)+'%)</span>').join('')+(restPct>0?'<span class="leg-click'+(legFilter==='Others'?' active':'')+'" data-leg="Others"><i style="background:#555"></i>Others ('+(restPct*100).toFixed(1)+'%)</span>':'')+'<span class="leg-clear" data-leg="" style="grid-column:1/-1;'+(legFilter===null?'display:none':'')+'">\u2715 clear filter</span></div>';}
    } else if(vmode==='share'){title=valliance+' vote share';
      html='<div class="legend-bar" style="background:linear-gradient(to right,rgb(26,26,46),rgb(79,195,247),rgb(255,241,118))"></div>'+
        '<div class="legend-labels"><span>0%</span><span>35%</span><span>70%+</span></div>';
    } else {title='Lead margin';
      html='<div class="legend-bar" style="background:linear-gradient(to right,rgb(26,26,46),rgb(255,167,38),rgb(229,57,53))"></div>'+
        '<div class="legend-labels"><span>close (0%)</span><span>20%</span><span>landslide (40%+)</span></div>';
    }
  } else {
    const titles={dominant:'Dominant age band \u2014 click to filter',cohort:'Cohort share',gender:'Male share',youth:dyaxis==='youth_share'?'Youth share (<30)':'Elderly share (60+)',absolute:'Absolute count ('+dabs+')',bandskew:'Male share within '+dskew};
    title=titles[dmode];
    if(dmode==='dominant'){html='<div class="legend-cats">'+P.age_bands.map(b=>'<span class="leg-click'+(legFilter===b?' active':'')+'" data-leg="'+b+'"><i style="background:'+P.band_colors[b]+'"></i>'+b+'</span>').join('')+'<span class="leg-clear" data-leg="" style="grid-column:1/-1;'+(legFilter===null?'display:none':'')+'">\u2715 clear filter</span></div>';}
    else if(dmode==='gender'||dmode==='bandskew'){html='<div class="legend-bar" style="background:linear-gradient(to right,rgb(236,72,153),rgb(59,59,92),rgb(79,195,247))"></div><div class="legend-labels"><span>F female-skew</span><span>50/50</span><span>male-skew M</span></div>';}
    else if(dmode==='cohort'){const m=cohortMean();html='<div class="legend-bar" style="background:linear-gradient(to right,rgb(26,26,46),rgb(79,195,247),rgb(255,241,118))"></div><div class="legend-labels"><span>0.4x avg</span><span>1.0x ('+(m*100).toFixed(1)+'%)</span><span>1.6x avg</span></div>';}
    else {const ramp=dmode==='youth'?(dyaxis==='youth_share'?'rgb(46,196,182)':'rgb(157,78,221)'):'rgb(79,195,247)';html='<div class="legend-bar" style="background:linear-gradient(to right,rgb(13,27,42),'+ramp+',rgb(255,209,102))"></div><div class="legend-labels"><span>low</span><span>medium</span><span>high</span></div>';}
  }
  document.getElementById('legendTitle').textContent=title;
  document.getElementById('legendBody').innerHTML=html;
  document.querySelectorAll('.leg-click,.leg-clear').forEach(el=>el.addEventListener('click',()=>{
    const v=el.dataset.leg;
    legFilter = v===''?null:v;
    render(); renderSummary(); renderHeadline();
  }));
}

function renderSummary(){
  let cards=[], toplabel='', metric=null, fmt=null;
  const filtered = legFilter!==null;
  const fs=filtered?legFilteredFeatures():visFeatures();
  const filterNote = filtered?' ('+fs.length+' matching \u201c'+legFilter+'\u201d)':'';
  if(domain==='votes'){
    const cs=getCs(cycle);
    const tv = cs?cs.total_valid:0;
    const wc = fs.filter(f=>f.properties.votes[cycle]).length;
    cards=[['Valid votes',tv.toLocaleString(),''],['Booths',wc,''],['Cycle',cycle,'']];
    if(cs){toplabel='Booths where '+(valliance||cs.winner)+' leads'+filterNote;metric=p=>{const cv=p.votes[cycle];return cv?cv.shares[valliance||cv.winner]||0:0;};fmt=v=>(v*100).toFixed(1)+'%';}
  } else {
    let yT=0,eT=0,tot=0,mT=0,fT=0;
    for(const f of fs){const p=f.properties;tot+=p.total;mT+=p.total_male;fT+=p.total_female;yT+=p.bands['18-21'].Total+p.bands['22-29'].Total;eT+=p.bands['60-69'].Total+p.bands['70+'].Total;}
    cards=[['Voters',tot.toLocaleString(),''],['M / F',tot?((mT/tot*100).toFixed(0)+'/'+(fT/tot*100).toFixed(0)):'-/-',''],['Under-30',tot?(yT/tot*100).toFixed(1)+'%':'-','of all'],['60+',tot?(eT/tot*100).toFixed(1)+'%':'-','of all']];
    if(dmode==='cohort'){toplabel='Top 5 &middot; '+dage+'/'+dsex;metric=p=>p.cohort_shares[dage+'|'+dsex]||0;fmt=v=>(v*100).toFixed(1)+'%';}
    else if(dmode==='youth'){toplabel='Top 5 &middot; '+(dyaxis==='youth_share'?'youth':'elderly');metric=p=>p[dyaxis];fmt=v=>(v*100).toFixed(1)+'%';}
    else if(dmode==='gender'){toplabel='Top 5 &middot; most male';metric=p=>p.male_ratio;fmt=v=>(v*100).toFixed(1)+'% M';}
    else if(dmode==='absolute'){toplabel='Top 5 &middot; largest '+dabs;metric=p=>p.cohort_shares[dabs+'|All']*p.total;fmt=v=>Math.round(v);}
    else if(dmode==='bandskew'){toplabel='Top 5 &middot; most-male '+dskew;metric=p=>p.band_gender_skew[dskew];fmt=v=>(v*100).toFixed(1)+'% M';}
    else {toplabel='Top 5 &middot; youngest';metric=p=>p.bands['18-21'].Total+p.bands['22-29'].Total;fmt=v=>v+' young';}
  }
  document.getElementById('cards').innerHTML=cards.map(c=>'<div class="card"><div class="k">'+c[0]+'</div><div class="v">'+c[1]+(c[2]?' <span class="unit">'+c[2]+'</span>':'')+'</div></div>').join('');
  if(metric){
    const ranked=fs.map(f=>[f.properties.part_no,f.properties.ac,f.properties.street||f.properties.locality||'?',metric(f.properties)]).sort((a,b)=>b[3]-a[3]).slice(0,5);
    document.getElementById('toplist').innerHTML='<div class="mini" style="margin-bottom:4px">'+toplabel+'</div>'+ranked.map((r,i)=>'<div class="row"><span class="rank">'+(i+1)+'</span><span class="name">'+r[1].replace('AC','')+'-'+r[0]+' &middot; '+r[2]+'</span><span class="val">'+fmt(r[3])+'</span></div>').join('');
  } else {document.getElementById('toplist').innerHTML='';}
}

function renderDonut(){
  const cs=getCs(cycle);
  const el=document.getElementById('donut');
  if(!cs||!cs.alliance_shares){el.innerHTML='';return;}
  const sorted=Object.entries(cs.alliance_shares).sort((a,b)=>b[1]-a[1]);
  const total=sorted.reduce((s,[,v])=>s+v,0);
  if(total<=0){el.innerHTML='';return;}
  const r=38,cx=50,cy=50,sw=12,C=2*Math.PI*r;
  let acc=0,arcs='';
  for(const [a,s] of sorted){
    const frac=s/total,dash=frac*C,off=-acc*C;
    const col=P.alliance_colors[a]||'#888';
    arcs+=`<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${col}" stroke-width="${sw}" stroke-dasharray="${dash.toFixed(2)} ${(C-dash).toFixed(2)}" stroke-dashoffset="${off.toFixed(2)}" transform="rotate(-90 ${cx} ${cy})"/>`;
    acc+=frac;
  }
  const w=cs.winner,ws=cs.alliance_shares[w];
  const svg=`<svg viewBox="0 0 100 100" width="100" height="100">${arcs}</svg>`;
  const center=`<div class="donut-center"><div class="dc-name" style="color:${P.alliance_colors[w]||'#fff'}">${w}</div><div class="dc-pct">${(ws*100).toFixed(1)}%</div></div>`;
  const top=sorted.slice(0,6);
  const rest=sorted.slice(6);
  const restPct=rest.reduce((s,[,v])=>s+v,0);
  let legItems=top.map(([a,s],i)=>`<div class="donut-leg-item${i===0?' lead':''}"><span class="wb-dot" style="background:${P.alliance_colors[a]||'#888'}"></span><span class="dl-name">${a}</span><span class="dl-val">${(s*100).toFixed(1)}%</span></div>`);
  if(restPct>0)legItems.push(`<div class="donut-leg-item"><span class="wb-dot" style="background:#555"></span><span class="dl-name">Others (${rest.length})</span><span class="dl-val">${(restPct*100).toFixed(1)}%</span></div>`);
  const legend=legItems.join('');
  let acSplit='';
  if(selectedAc==='ALL'){
    acSplit='<div class="donut-ac-split">';
    for(const [code,meta] of Object.entries(P.acs)){
      const acs=P.ac_summaries[code][cycle];
      if(!acs)continue;
      acSplit+=`<div class="das-row"><span class="das-name">${meta.name}</span><span class="wb-dot" style="background:${P.alliance_colors[acs.winner]||'#888'}"></span>${acs.winner} ${(acs.alliance_shares[acs.winner]*100).toFixed(1)}%</div>`;
    }
    acSplit+='</div>';
  }
  el.innerHTML=`<div class="donut-chart">${svg}${center}</div><div class="donut-legend">${legend}${acSplit}</div>`;
}

function renderLabels(){if(labelLayer){labelLayer.remove();labelLayer=null;}if(!document.getElementById('showLabels').checked)return;labelLayer=L.layerGroup().addTo(map);
  for(const f of visFeatures()){const ctr=L.geoJSON(f).getBounds().getCenter();L.tooltip({permanent:true,direction:'center',className:'ac18-label'}).setContent(String(f.properties.part_no)).setLatLng(ctr).addTo(labelLayer);}}

function renderOutline(){if(outlineLayer)outlineLayer.remove();if(!document.getElementById('showOutline').checked)return;
  outlineLayer=L.layerGroup().addTo(map);
  const hullsToShow = selectedAc==='ALL'?P.hulls:[P.hulls[P.acs[selectedAc].hull_idx]];
  for(const h of hullsToShow){L.geoJSON(h,{style:{weight:2,color:'#1565c0',dashArray:'6,4',fill:false,opacity:0.7}}).addTo(outlineLayer);}
  outlineLayer.eachLayer(l=>l.bringToFront&&l.bringToFront());}

function selectBooth(uid){
  selPart=uid;const f=P.geojson.features.find(x=>x.properties.uid===uid);if(!f)return;const p=f.properties;
  document.getElementById('infoTitle').textContent=p.ac.replace('AC','')+' Part '+p.part_no;
  document.getElementById('infoSub').innerHTML=(p.street||p.locality||'?')+' &middot; '+p.total.toLocaleString()+' voters &middot; M '+p.total_male+'/F '+p.total_female+' &middot; geocode: '+p.tier;
  let mx=0;for(const b of P.age_bands)mx=Math.max(mx,p.bands[b].Total);
  let py='';for(const b of P.age_bands){const bd=p.bands[b];const mh=bd.Total>0?(bd.Male/mx*100):0,fh=bd.Total>0?(bd.Female/mx*100):0;py+='<div class="pcol"><div class="pseg" style="height:'+fh+'%;background:#ec4899" title="'+b+' F '+bd.Female+'"></div><div class="pseg" style="height:'+mh+'%;background:#4fc3f7" title="'+b+' M '+bd.Male+'"></div></div>';}
  document.getElementById('pyramid').innerHTML=py;
  let t='<tr><th>Band</th><th>M</th><th>F</th><th>Tot</th><th>%</th></tr>';
  for(const b of P.age_bands){const bd=p.bands[b];const pct=p.total?(bd.Total/p.total*100).toFixed(1):'0.0';const w=mx?(bd.Total/mx*100).toFixed(0):0;t+='<tr><td>'+b+'</td><td>'+bd.Male+'</td><td>'+bd.Female+'</td><td>'+bd.Total+'</td><td><span class="bar" style="width:'+(w*0.5)+'px;background:'+P.band_colors[b]+'"></span> '+pct+'%</td></tr>';}
  document.getElementById('infoTable').innerHTML=t;
  let vh='<div class="src-label">🗳 FORM 20 &mdash; Vote shares by cycle (EVM only)</div>';
  for(const y of P.cycles){const cv=p.votes[y];if(!cv){vh+='<div class="wb-row"><span class="yr">'+y+'</span> no data</div>';continue;}
    const sorted=Object.entries(cv.shares).sort((a,b)=>b[1]-a[1]);
    vh+='<div class="wb-row"><span class="yr">'+y+'</span> '+sorted.map(([a,s])=>'<span class="wb-mini"><span class="wb-dot" style="background:'+(P.alliance_colors[a]||'#888')+'"></span>'+a+' '+(s*100).toFixed(0)+'%</span>').join(' ')+'</div>';}
  vh+='<div class="src-note">Top shares shown. Demographics above are from the Electoral Roll; votes are from Form 20 (EVM). These are independent datasets &mdash; one describes who can vote, the other how they voted.</div>';
  document.getElementById('infoVotes').innerHTML=vh;
  document.getElementById('infoPanel').style.display='block';render();
}
function clearSel(){selPart=null;document.getElementById('infoPanel').style.display='none';render();}

// ---- build dynamic controls ----
function buildAcBtns(){
  let html='<button class="ac-btn'+(selectedAc==='ALL'?' active':'')+'" data-ac="ALL">All</button>';
  for(const [code,meta] of Object.entries(P.acs)){
    html+='<button class="ac-btn'+(selectedAc===code?' active':'')+'" data-ac="'+code+'">'+meta.name+'</button>';
  }
  document.getElementById('acBtns').innerHTML=html;
  document.querySelectorAll('.ac-btn').forEach(b=>b.addEventListener('click',()=>{
    selectedAc=b.dataset.ac;legFilter=null;
    document.querySelectorAll('.ac-btn').forEach(x=>x.classList.remove('active'));b.classList.add('active');
    valliance=null;
    buildAllianceBtns(); render(); renderOutline();
    if(selectedAc==='ALL'){
      map.fitBounds(cellLayer.getBounds().pad(0.05));
    } else {
      const acFeats=visFeatures();
      if(acFeats.length){const b=L.geoJSON({type:'FeatureCollection',features:acFeats}).getBounds();map.fitBounds(b.pad(0.05));}
    }
    updateStats();
  }));
}

function buildControls(){
  document.getElementById('cycleBtns').innerHTML=P.cycles.map(y=>'<button class="cycle-btn'+(y===cycle?' active':'')+'" data-cycle="'+y+'">'+y+'</button>').join('');
  document.querySelectorAll('.cycle-btn').forEach(b=>b.addEventListener('click',()=>{cycle=+b.dataset.cycle;legFilter=null;document.querySelectorAll('.cycle-btn').forEach(x=>x.classList.remove('active'));b.classList.add('active');if(!valliance){const cs=getCs(cycle);valliance=cs?cs.winner:null;}buildAllianceBtns();render();}));
  document.getElementById('ageBtns').innerHTML=P.age_bands.map(b=>'<label><input type="radio" name="age" value="'+b+'"'+(b===dage?' checked':'')+'> '+b+'</label>').join('');
  document.getElementById('absBtns').innerHTML=P.age_bands.map(b=>'<button class="chip'+(b===dabs?' active':'')+'" data-abs="'+b+'">'+b+'</button>').join('');
  document.getElementById('skewBtns').innerHTML=P.age_bands.map(b=>'<button class="chip'+(b===dskew?' active':'')+'" data-skew="'+b+'">'+b+'</button>').join('');
  document.querySelectorAll('input[name=age]').forEach(el=>el.addEventListener('change',e=>{dage=e.target.value;render();}));
  document.querySelectorAll('[data-abs]').forEach(el=>el.addEventListener('click',()=>{dabs=el.dataset.abs;document.querySelectorAll('[data-abs]').forEach(x=>x.classList.remove('active'));el.classList.add('active');render();}));
  document.querySelectorAll('[data-skew]').forEach(el=>el.addEventListener('click',()=>{dskew=el.dataset.skew;document.querySelectorAll('[data-skew]').forEach(x=>x.classList.remove('active'));el.classList.add('active');render();}));
  buildAllianceBtns();
}
function buildAllianceBtns(){
  const cs=getCs(cycle);if(!cs)return;
  const alliances=Object.keys(cs.alliance_shares).sort((a,b)=>cs.alliance_shares[b]-cs.alliance_shares[a]);
  if(!valliance||!alliances.includes(valliance))valliance=alliances[0];
  document.getElementById('allianceBtns').innerHTML=alliances.map(a=>'<button class="chip'+(a===valliance?' active':'')+'" data-alliance="'+a+'" style="border-color:'+(P.alliance_colors[a]||'#888')+'"><span class="wb-dot" style="background:'+(P.alliance_colors[a]||'#888')+'"></span>'+a+'</button>').join('');
  document.querySelectorAll('[data-alliance]').forEach(el=>el.addEventListener('click',()=>{valliance=el.dataset.alliance;document.querySelectorAll('[data-alliance]').forEach(x=>x.classList.remove('active'));el.classList.add('active');render();}));
}

function updateStats(){
  const n=selectedAc==='ALL'?P.n_booths:P.acs[selectedAc].n_booths;
  const v=selectedAc==='ALL'?P.n_voters:P.acs[selectedAc].n_voters;
  const acLabel=selectedAc==='ALL'?'all ACs':P.acs[selectedAc].name;
  document.getElementById('stats').innerHTML='<span>'+n+' booths</span><span>'+v.toLocaleString()+' voters</span><span>'+P.cycles.length+' cycles</span><span>'+acLabel+'</span>';
}

// ---- event wiring ----
document.querySelectorAll('.domain-btn').forEach(b=>b.addEventListener('click',()=>{
  document.querySelectorAll('.domain-btn').forEach(x=>x.classList.remove('active'));b.classList.add('active');domain=b.dataset.domain;legFilter=null;
  document.getElementById('votesControls').style.display=domain==='votes'?'block':'none';
  document.getElementById('demoControls').style.display=domain==='demo'?'block':'none';render();}));
document.querySelectorAll('.vmode-btn').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('.vmode-btn').forEach(x=>x.classList.remove('active'));b.classList.add('active');vmode=b.dataset.vmode;legFilter=null;document.getElementById('shareControls').style.display=vmode==='share'?'block':'none';render();}));
document.querySelectorAll('.dmode-btn').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('.dmode-btn').forEach(x=>x.classList.remove('active'));b.classList.add('active');dmode=b.dataset.dmode;legFilter=null;
  document.getElementById('cohortControls').style.display=dmode==='cohort'?'block':'none';
  document.getElementById('youthControls').style.display=dmode==='youth'?'block':'none';
  document.getElementById('absControls').style.display=dmode==='absolute'?'block':'none';
  document.getElementById('skewControls').style.display=dmode==='bandskew'?'block':'none';render();}));
document.querySelectorAll('input[name=sex]').forEach(el=>el.addEventListener('change',e=>{dsex=e.target.value;render();}));
document.querySelectorAll('input[name=yaxis]').forEach(el=>el.addEventListener('change',e=>{dyaxis=e.target.value;render();}));
document.getElementById('baseToggle').addEventListener('change',e=>{map.removeLayer(baseActive);baseActive=e.target.checked?baseSat:baseGrey;baseActive.addTo(map);if(cellLayer)cellLayer.bringToFront();if(outlineLayer)outlineLayer.eachLayer(l=>l.bringToFront&&l.bringToFront());});
document.getElementById('showOutline').addEventListener('change',renderOutline);
document.getElementById('showLabels').addEventListener('change',renderLabels);
document.getElementById('closeInfo').addEventListener('click',clearSel);
map.on('click',clearSel);

buildAcBtns(); buildControls(); updateStats();
render(); renderOutline();
map.fitBounds(cellLayer.getBounds().pad(0.05));
</script>
</body></html>
"""


_CSS = """
  :root{--bg:#0a0e14;--panel:#111821;--panel2:#1a2330;--panel3:#222d3d;--text:#e4e8ef;--text-dim:#7d8699;--border:#243044;--accent:#4fc3f7;--accent-dim:#1a3a4a;}
  *{box-sizing:border-box;}
  html,body{margin:0;height:100%;color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;}
  body{display:flex;flex-direction:column;background:var(--bg);}
  .topbar{background:var(--panel);border-bottom:1px solid var(--border);padding:8px 16px;display:flex;align-items:center;gap:14px;flex-wrap:wrap;flex-shrink:0;z-index:1000;position:sticky;top:0;}
  .topbar h1{margin:0;font-size:16px;font-weight:700;color:var(--accent);white-space:nowrap;}
  .headline{flex:1;font-size:12.5px;color:var(--text);min-width:240px;line-height:1.4;}
  .stats{font-size:11px;color:var(--text-dim);display:flex;gap:6px;flex-wrap:wrap;}
  .stats span{padding:3px 8px;background:var(--panel2);border-radius:10px;}
  .app{flex:1;display:flex;min-height:0;position:relative;}
  #map{flex:1;background:#d9dde2;}
  .leaflet-container{background:#d9dde2 !important;}
  .sidebar{width:350px;flex-shrink:0;background:var(--panel);border-left:1px solid var(--border);overflow:hidden;display:flex;flex-direction:column;}
  .sb-sticky{flex-shrink:0;background:var(--panel);border-bottom:1px solid var(--border);z-index:10;}
  .sb-sticky-pad{padding:12px 14px;}
  .sb-sticky-pad+.sb-sticky-pad{padding-top:0;}
  .sb-scroll{overflow-y:auto;padding:14px;flex:1;}
  h3{margin:0 0 8px 0;font-size:11px;text-transform:uppercase;letter-spacing:.6px;color:var(--text-dim);}
  .mini{font-size:10px;color:var(--text-dim);margin-bottom:3px;text-transform:uppercase;letter-spacing:.4px;}
  .ac-row{display:flex;gap:5px;flex-wrap:wrap;}
  .ac-btn{padding:6px 11px;background:var(--panel2);border:1px solid var(--border);border-radius:14px;color:var(--text-dim);cursor:pointer;font-size:11.5px;font-weight:500;transition:all .15s;}
  .ac-btn:hover{border-color:var(--accent);color:var(--text);}
  .ac-btn.active{background:var(--accent);color:#001525;border-color:var(--accent);}
  .donut-section{display:flex;gap:12px;align-items:center;}
  .donut-chart{flex-shrink:0;position:relative;width:100px;height:100px;}
  .donut-center{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);text-align:center;pointer-events:none;width:70px;}
  .donut-center .dc-name{font-size:10px;font-weight:600;line-height:1;}
  .donut-center .dc-pct{font-size:17px;font-weight:700;line-height:1.1;margin-top:2px;color:var(--text);}
  .donut-legend{flex:1;font-size:11px;display:flex;flex-direction:column;gap:1px;}
  .donut-leg-item{display:flex;align-items:center;gap:5px;color:var(--text-dim);padding:1px 0;}
  .donut-leg-item .dl-name{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
  .donut-leg-item .dl-val{color:var(--text);font-weight:600;font-variant-numeric:tabular-nums;}
  .donut-leg-item.lead{color:var(--text);font-weight:600;}
  .donut-ac-split{margin-top:8px;padding-top:8px;border-top:1px solid var(--border);font-size:10.5px;color:var(--text-dim);}
  .donut-ac-split .das-row{display:flex;align-items:center;gap:5px;padding:2px 0;}
  .donut-ac-split .das-name{flex:1;color:var(--accent);font-weight:500;}
  .wb-row{display:flex;align-items:center;gap:5px;padding:2px 0;font-size:12px;flex-wrap:wrap;}
  .wb-dot{width:9px;height:9px;border-radius:50%;display:inline-block;flex-shrink:0;}
  .wb-mini{display:inline-flex;align-items:center;gap:3px;font-size:10.5px;margin-right:6px;}
  .yr{color:var(--text-dim);font-weight:600;width:32px;display:inline-block;}
  .mode-grid{display:grid;grid-template-columns:1fr 1fr;gap:5px;margin-bottom:4px;}
  .domain-btn,.vmode-btn,.dmode-btn,.cycle-btn,.chip{padding:7px 8px;background:var(--panel2);border:1px solid var(--border);border-radius:6px;color:var(--text-dim);cursor:pointer;font-size:11.5px;font-weight:500;transition:all .15s;}
  .domain-btn,.vmode-btn,.dmode-btn{text-align:left;}
  .domain-btn:hover,.vmode-btn:hover,.dmode-btn:hover,.cycle-btn:hover,.chip:hover{border-color:var(--accent);color:var(--text);}
  .domain-btn.active,.vmode-btn.active,.dmode-btn.active,.cycle-btn.active,.chip.active{background:var(--accent-dim);color:var(--accent);border-color:var(--accent);}
  .chip{display:inline-flex;align-items:center;gap:4px;margin:3px 3px 3px 0;}
  .cycle-row{display:flex;gap:5px;flex-wrap:wrap;}
  .section{margin-top:14px;padding-top:12px;border-top:1px solid var(--border);}
  .legend-bar{height:10px;border-radius:5px;margin:6px 0;}
  .legend-labels{display:flex;justify-content:space-between;font-size:10px;color:var(--text-dim);margin-bottom:2px;}
  .legend-cats{display:grid;grid-template-columns:1fr 1fr;gap:3px 10px;font-size:10.5px;color:var(--text-dim);margin-top:4px;}
  .legend-cats span{display:flex;align-items:center;gap:5px;}
  .legend-cats i{width:10px;height:10px;border-radius:2px;display:inline-block;}
  .leg-click{cursor:pointer;padding:2px 5px;border-radius:4px;transition:all .15s;border:1px solid transparent;}
  .leg-click:hover{background:var(--panel2);border-color:var(--accent);}
  .leg-click.active{background:var(--accent-dim);border-color:var(--accent);color:var(--accent);font-weight:600;}
  .leg-clear{cursor:pointer;padding:3px 6px;border-radius:4px;font-size:10px;color:var(--accent);text-align:center;margin-top:2px;}
  .leg-clear:hover{text-decoration:underline;}
  .limits-note{font-size:10px;color:var(--text-dim);line-height:1.6;display:flex;flex-direction:column;gap:5px;}
  .limits-note div{padding:4px 8px;background:var(--panel2);border-radius:5px;}
  .limits-note b{color:var(--accent);font-weight:600;}
  .cards{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:4px;}
  .card{background:var(--panel2);border-radius:7px;padding:8px 10px;}
  .card .k{font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.4px;}
  .card .v{font-size:16px;font-weight:600;color:var(--text);margin-top:1px;}
  .card .v .unit{font-size:10px;color:var(--text-dim);font-weight:400;}
  .toplist{margin-top:8px;font-size:11.5px;}
  .toplist .row{display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid var(--border);gap:5px;align-items:center;}
  .toplist .row:last-child{border-bottom:none;}
  .toplist .rank{color:var(--text-dim);width:16px;font-size:10px;}
  .toplist .name{flex:1;color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
  .toplist .val{color:var(--accent);font-variant-numeric:tabular-nums;font-weight:600;}
  .tier-note{font-size:10px;color:var(--text-dim);line-height:1.5;margin-top:8px;}
  .toggle-row{display:flex;gap:8px;align-items:center;margin-top:6px;font-size:11px;color:var(--text-dim);flex-wrap:wrap;}
  .toggle-row label{cursor:pointer;display:flex;align-items:center;gap:4px;}
  .info-panel{display:none;position:absolute;bottom:16px;left:16px;width:320px;max-height:calc(100vh - 110px);overflow-y:auto;background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:14px;box-shadow:0 8px 32px rgba(0,0,0,0.35);z-index:500;animation:slideUp .25s ease;}
  @keyframes slideUp{from{transform:translateY(20px);opacity:0;}to{transform:translateY(0);opacity:1;}}
  .info-panel .xbtn:hover{color:var(--accent);}
  .info-panel h4{margin:0 0 3px 0;font-size:14px;color:var(--text);}
  .info-panel .sub{font-size:10.5px;color:var(--text-dim);margin-bottom:8px;}
  .info-panel table{width:100%;border-collapse:collapse;font-size:11.5px;}
  .info-panel th,.info-panel td{padding:2px 3px;text-align:right;}
  .info-panel th{color:var(--text-dim);font-weight:500;border-bottom:1px solid var(--border);}
  .info-panel th:first-child,.info-panel td:first-child{text-align:left;}
  .info-panel td .bar{display:inline-block;height:5px;border-radius:3px;min-width:2px;vertical-align:middle;}
  .pyramid{display:flex;align-items:flex-end;gap:2px;height:40px;margin:6px 0;padding:0 4px;}
  .pyramid .pcol{flex:1;display:flex;flex-direction:column-reverse;gap:1px;height:100%;}
  .pyramid .pseg{width:100%;border-radius:1px;}
  .xbtn{background:none;border:none;color:var(--text-dim);font-size:18px;cursor:pointer;line-height:1;}
  .leaflet-tooltip.ac18{background:var(--panel2);color:var(--text);border:1px solid var(--border);box-shadow:none;font-size:11.5px;}
  .leaflet-tooltip.ac18::before{border-top-color:var(--panel2);}
  .leaflet-tooltip.ac18-label{background:rgba(17,24,33,0.7);color:#cfd6e4;border:none;box-shadow:none;font-size:9px;font-weight:600;}
  .leaflet-tooltip.ac18-label::before{display:none;}
"""


def main():
    print("Building unified multi-AC heatmap...")
    payload = build_all()
    print(f"  total: {payload['n_booths']} booths, {payload['n_voters']} voters, "
          f"{len(payload['acs'])} constituencies")
    write_html(payload)


if __name__ == "__main__":
    main()
