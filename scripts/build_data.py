#!/usr/bin/env python3
"""
Generate the booth analytics data payload (data.json) from raw source files.

Combines all constituencies from ac_config.ACS into a single JSON payload.
Each booth gets a Voronoi cell clipped to its AC outline.

Usage: python scripts/build_data.py
Output: site/data.json
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
from alliances import alliance_for, ALLIANCE_COLORS

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
SIMPLIFY_TOL = 0.000008
COORD_DECIMALS = 5
TOP_SHARES = 5
CYCLES = [2026, 2024, 2021]


def _round_coords(geom):
    return shp_transform(lambda x, y, z=None: (round(x, COORD_DECIMALS), round(y, COORD_DECIMALS)), geom)


def build_voronoi_cells(points_latlon):
    pts_geo = [(p[1], p[0]) for p in points_latlon]
    hull = shapely.concave_hull(MultiPoint(pts_geo), ratio=HULL_RATIO, allow_holes=False).buffer(HULL_BUFFER)
    center = points_latlon.mean(axis=0)
    far = center + np.array([[100, 100], [100, -100], [-100, 100], [-100, -100]])
    vor = Voronoi(np.vstack([points_latlon, far]))
    cells = []
    for i in range(len(points_latlon)):
        region = vor.regions[vor.point_region[i]]
        if not region or -1 in region:
            cells.append(None)
            continue
        poly = Polygon([(vor.vertices[k, 1], vor.vertices[k, 0]) for k in region])
        if not poly.is_valid:
            poly = poly.buffer(0)
        clipped = poly.intersection(hull)
        if clipped.is_empty:
            cells.append(None)
            continue
        if clipped.geom_type == "MultiPolygon":
            clipped = max(clipped.geoms, key=lambda g: g.area)
        if clipped.area < SLIVER_AREA:
            cells.append(None)
            continue
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
    cfg = ac_config.get(ac_name)
    prefix = cfg["prefix"]
    coords = load_coords(prefix)
    demo = load_demographics(cfg["demographics"])
    common = sorted(set(coords) & set(demo))
    points = np.array([[float(coords[p]["lat"]), float(coords[p]["lon"])] for p in common])
    cells, hull = build_voronoi_cells(points)

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
                    cycle_votes[y] = {"shares": top, "winner": winner, "margin": round(margin, 4)}

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
            "uid": f"{ac_name}_{part_no}", "part_no": part_no, "ac": ac_name,
            "tier": c["tier"], "street": c["street"], "locality": c["locality"],
            "total": total, "total_male": int(dd["Booth_Total_Male"]),
            "total_female": int(dd["Booth_Total_Female"]),
            "bands": bands, "dominant_band": dominant_band, "male_ratio": male_ratio,
            "youth_share": youth_share, "elderly_share": elderly_share,
            "band_gender_skew": band_gender_skew, "cohort_shares": cohort_shares,
            "votes": cycle_votes,
        }
        features.append({"type": "Feature", "geometry": mapping(geom), "properties": props})

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

    meta = {"name": cfg["name"], "code": ac_name, "pc": cfg["pc"], "center": list(cfg["center"]),
            "n_booths": len(common), "n_voters": sum(int(demo[p]["Booth_Total"]) for p in common), "hull_idx": None}
    return features, mapping(hull), cycle_summary, meta


def build_all():
    all_features, all_hulls, ac_summaries, ac_meta = [], [], {}, {}
    for ac_name in ac_config.ACS:
        features, hull_geojson, summary, meta = build_one(ac_name)
        meta["hull_idx"] = len(all_hulls)
        all_features.extend(features)
        all_hulls.append(hull_geojson)
        ac_summaries[ac_name] = summary
        ac_meta[ac_name] = meta
        print(f"  {ac_name} ({meta['name']}): {meta['n_booths']} booths, "
              f"winners {[(y, s['winner']) for y, s in summary.items()]}")

    all_summaries = {}
    for y in CYCLES:
        combined, combined_valid = {}, 0
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
    for ac in ac_summaries:
        for y in ac_summaries[ac]:
            ac_summaries[ac][y].pop("_raw", None)

    all_centers = np.array([m["center"] for m in ac_meta.values()])
    map_center = all_centers.mean(axis=0).tolist()
    all_cycles = sorted(set(y for s in ac_summaries.values() for y in s.keys()), reverse=True)

    return {
        "geojson": {"type": "FeatureCollection", "features": all_features},
        "hulls": all_hulls, "acs": ac_meta, "ac_summaries": ac_summaries,
        "all_summaries": all_summaries, "cycles": all_cycles, "center": map_center,
        "n_booths": len(all_features), "n_voters": sum(m["n_voters"] for m in ac_meta.values()),
        "age_bands": AGE_BANDS, "band_colors": BAND_COLORS, "alliance_colors": ALLIANCE_COLORS,
    }


def main():
    print("Building booth analytics data...")
    payload = build_all()
    print(f"  total: {payload['n_booths']} booths, {payload['n_voters']} voters, "
          f"{len(payload['acs'])} constituencies")
    out = BASE / "site" / "data.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {out} ({out.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
