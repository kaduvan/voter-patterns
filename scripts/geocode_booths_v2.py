#!/usr/bin/env python3
"""
AC-agnostic booth geocoder via OpenStreetMap Nominatim — STREET + LOCALITY
strategy with a 3-TIER fallback so EVERY booth gets a coordinate.

WHY THIS DESIGN: Indian AC booths list schools/offices with descriptive names
and a street address. Nominatim resolves SOME street names but NOT the
descriptive building names, and many minor streets are not in OSM as searchable
named ways. A wide city viewbox returned namesake streets in wrong zones; a
TIGHT bounded=true box fixes precision but leaves coverage partial. So:

  Tier 1 — STREET: parse + normalize the building's street token, geocode
           "<Street>, <City>" inside the tight AC box. Best precision.
           Door-number jitter separates booths sharing a street.
  Tier 2 — LOCALITY: fall back to the locality centroid, geocoded inside the
           tight box. Medium precision.
  Tier 3 — AC CENTROID. Worst case; few booths.

Every row records its `precision` tier so the map/UI can flag approximate
points. Building-exact coords can later be pasted over lat/lon for refinement.

Usage:
  python scripts/geocode_booths.py --ac AC018
  python scripts/geocode_booths.py --ac AC019
"""
import argparse
import csv
import hashlib
import re
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ac_config import get as get_ac

BASE = Path(__file__).resolve().parent.parent

# Max per-street offset in degrees (~0.0018 deg ~ 200 m). Booths sharing a
# street are spread within this radius using their door number.
MAX_OFFSET_DEG = 0.0018

# Chennai context suffix for Nominatim queries.
CITY = "Chennai"

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# Match the LAST occurrence of "<Name> Street|Salai|Road|Lane|Broadway" in the
# string. The last street is usually the one the building sits on. Broadway is
# an area but tagged like a street in these addresses ("No:28, Broadway").
STREET_RE = re.compile(
    r"([A-Za-z][A-Za-z.'\- ]*?\s+(?:Street|Salai|Road|Lane|Square|Squaire)|Broadway)\b",
    re.IGNORECASE,
)
# Door number: "No:508", "No. 508", "No 508", "New No 17", "No:26-24 and 29"
DOOR_RE = re.compile(r"(?:New\s+)?No\.?\s*:?\s*(\d{1,4})", re.IGNORECASE)


# ─── Address parsing ────────────────────────────────────────────────────────

def parse_address(building: str, localities_re: re.Pattern) -> dict:
    """Extract street, door_no, locality from a building string."""
    streets = STREET_RE.findall(building)
    street = streets[-1].strip() if streets else ""  # last = building's street
    door_match = DOOR_RE.search(building)
    door_no = int(door_match.group(1)) if door_match else None
    loc_match = localities_re.search(building)
    locality = loc_match.group(1).title() if loc_match else ""
    return {"street": street, "door_no": door_no, "locality": locality}


def norm_street(s: str) -> str:
    """Normalize a street token for dedup: lowercase, strip dots/apostrophes,
    collapse whitespace."""
    s = s.lower().replace(".", " ").replace("'", " ").replace("-", " ")
    return re.sub(r"\s+", " ", s).strip()


def norm_locality(s: str) -> str:
    """Normalize a locality for dedup."""
    return re.sub(r"\s+", " ", s.lower()).strip()


def query_for_street(street: str, overrides: dict) -> str:
    """Pick the Nominatim query string for a street token (apply overrides)."""
    return overrides.get(norm_street(street), street)


def query_for_locality(locality: str, overrides: dict) -> str:
    return overrides.get(norm_locality(locality), locality)


def build_localities_re(localities: list[str]) -> re.Pattern:
    """Build a regex from a list of known locality names."""
    return re.compile(
        r"\b(" + "|".join(re.escape(l) for l in sorted(localities, key=len, reverse=True)) + r")\b",
        re.IGNORECASE,
    )


# ─── Nominatim ──────────────────────────────────────────────────────────────

def _nom(q: str, viewbox: str, user_agent: str) -> dict | None:
    """Single Nominatim query inside the tight AC box, bounded=true. Returns
    top hit or None. Retries transient network/rate errors."""
    params = {
        "q": f"{q}, {CITY}", "format": "jsonv2", "limit": 1, "countrycodes": "in",
        "viewbox": viewbox, "bounded": "true", "addressdetails": "1",
    }
    for attempt in range(3):
        try:
            r = requests.get(NOMINATIM_URL, params=params,
                             headers={"User-Agent": user_agent}, timeout=30)
            if r.status_code == 200:
                data = r.json()
                return data[0] if data else None
            if r.status_code in (429, 503, 504):
                time.sleep(5 * (attempt + 1)); continue
            print(f"      HTTP {r.status_code}: {r.text[:100]}", file=sys.stderr)
            return None
        except requests.RequestException:
            time.sleep(3 * (attempt + 1))
    return None


def load_cache(path: Path, key_field: str) -> dict:
    cache = {}
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                cache[row[key_field]] = row
    return cache


def _write_hit(w, fieldnames, key_field, key, display, hit):
    if hit:
        w.writerow({
            key_field: key, "display": display,
            "lat": hit.get("lat", ""), "lon": hit.get("lon", ""),
            "display_name": hit.get("display_name", ""),
            "state": (hit.get("address") or {}).get("state", ""),
            "class": hit.get("class", ""), "type": hit.get("type", ""),
        })
        print(f"    HIT  {hit['lat']},{hit['lon']}  "
              f"{hit.get('display_name','')[:55]}")
    else:
        w.writerow({key_field: key, "display": display, "lat": "", "lon": "",
                    "display_name": "", "state": "", "class": "", "type": ""})
        print("    MISS")


def geocode_entities(items: dict, path: Path, key_field: str,
                     query_fn, nom_fn, label: str) -> dict:
    """Geocode a dict of {key: {'display':..., 'count':...}}, query per item.
    query_fn(display) -> query string. nom_fn(query) -> hit. Resumable."""
    cache = load_cache(path, key_field)
    todo = [k for k in items if k not in cache]
    print(f"\n{label}: {len(items)} | cached: {len(cache)} | to geocode: {len(todo)}")
    fields = [key_field, "display", "lat", "lon", "display_name",
              "state", "class", "type"]
    write_header = not path.exists()
    with open(path, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if write_header:
            w.writeheader()
        for i, key in enumerate(todo, 1):
            disp = items[key]["display"]
            print(f"[{i}/{len(todo)}] {disp}", flush=True)
            hit = nom_fn(query_fn(disp))
            _write_hit(w, fields, key_field, key, disp, hit)
            f.flush()
            time.sleep(1.1)
    return load_cache(path, key_field)


# ─── Booth placement ────────────────────────────────────────────────────────

def jitter_offset(part_no: int, door_no: int | None, prefix: str) -> tuple[float, float]:
    """Deterministic (lat, lon) offset within MAX_OFFSET_DEG.

    Uses door_no when available (signal of where along the street), scaled with
    a gentle curve; plus a deterministic hash of part_no for the orthogonal axis
    so multiple booths on the same street separate visibly.
    """
    frac = 1.0 / (1.0 + (door_no or 250) / 250.0)  # door 250 -> ~0.5
    h = hashlib.md5(f"{prefix}-{part_no}".encode()).hexdigest()
    perp = int(h[:8], 16) / 0xFFFFFFFF
    d_lat = (frac - 0.5) * 2 * MAX_OFFSET_DEG
    d_lon = (perp - 0.5) * 2 * MAX_OFFSET_DEG
    return d_lat, d_lon


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ac", default="AC018", help="AC code (default AC018)")
    args = ap.parse_args()

    cfg = get_ac(args.ac)
    prefix = cfg["prefix"]
    gc = cfg["geocode"]

    centroid = gc["centroid"]
    viewbox = gc["viewbox"]
    user_agent = gc["user_agent"]
    localities = gc["localities"]
    street_overrides = gc.get("street_overrides", {})
    locality_overrides = gc.get("locality_overrides", {})

    localities_re = build_localities_re(localities)

    in_csv = BASE / "data" / f"booths_{prefix}.csv"
    street_csv = BASE / "data" / f"street_coords_{prefix}.csv"
    locality_csv = BASE / "data" / f"locality_coords_{prefix}.csv"
    booth_csv = BASE / "data" / f"booth_coords_{prefix}.csv"

    if not in_csv.exists():
        print(f"ERROR: {in_csv} not found.", file=sys.stderr)
        return 1

    with open(in_csv, encoding="utf-8") as f:
        booths = list(csv.DictReader(f))

    # Parse every booth's address; collect distinct streets + localities.
    streets, localities_dict = {}, {}
    parsed = []
    for b in booths:
        a = parse_address(b["building"], localities_re)
        s_key = norm_street(a["street"]) if a["street"] else ""
        l_key = norm_locality(a["locality"]) if a["locality"] else ""
        parsed.append({**a, "street_key": s_key, "locality_key": l_key,
                       "part_no": int(b["part_no"]), "pincode": b.get("pincode", ""),
                       "building": b["building"]})
        if s_key:
            streets.setdefault(s_key, {"display": a["street"], "count": 0})["count"] += 1
        if l_key:
            localities_dict.setdefault(l_key, {"display": a["locality"], "count": 0})["count"] += 1

    print(f"AC: {args.ac} ({cfg['name']}) | prefix: {prefix}")
    print(f"Booths: {len(parsed)} | with street: {sum(1 for p in parsed if p['street_key'])} "
          f"({len(streets)} distinct) | with locality: "
          f"{sum(1 for p in parsed if p['locality_key'])} ({len(localities_dict)} distinct)")

    # Nom query function with closure over AC params
    def _nom_fn(q):
        return _nom(q, viewbox, user_agent)

    # Geocode both tiers (resumable; cached CSVs).
    street_cache = geocode_entities(
        streets, street_csv, "street_key",
        lambda disp: query_for_street(disp, street_overrides), _nom_fn, "STREETS")
    locality_cache = geocode_entities(
        localities_dict, locality_csv, "locality_key",
        lambda disp: query_for_locality(disp, locality_overrides), _nom_fn, "LOCALITIES")
    s_hits = sum(1 for v in street_cache.values() if v.get("lat"))
    l_hits = sum(1 for v in locality_cache.values() if v.get("lat"))
    print(f"\nGeocode summary: streets {s_hits}/{len(street_cache)} hit, "
          f"localities {l_hits}/{len(locality_cache)} hit")

    # 3-TIER assignment.
    rows = []
    tier_counts = {"street": 0, "locality": 0, "ac_centroid": 0}
    for p in parsed:
        sc = street_cache.get(p["street_key"], {})
        lat, lon = sc.get("lat", "") or "", sc.get("lon", "") or ""
        if lat and lon:
            d_lat, d_lon = jitter_offset(p["part_no"], p["door_no"], prefix)
            lat, lon = round(float(lat) + d_lat, 6), round(float(lon) + d_lon, 6)
            tier, source = "street", f"nominatim:street"
        else:
            lc = locality_cache.get(p["locality_key"], {})
            lat, lon = lc.get("lat", "") or "", lc.get("lon", "") or ""
            if lat and lon:
                d_lat, d_lon = jitter_offset(p["part_no"], p["door_no"], prefix)
                lat, lon = round(float(lat) + d_lat, 6), round(float(lon) + d_lon, 6)
                tier, source = "locality", "nominatim:locality"
            else:
                lat, lon = round(centroid[0], 6), round(centroid[1], 6)
                tier, source = "ac_centroid", f"{prefix}_centroid"
        tier_counts[tier] += 1
        rows.append({
            "part_no": p["part_no"], "lat": lat, "lon": lon,
            "tier": tier, "source": source,
            "street": p["street"], "street_key": p["street_key"],
            "locality": p["locality"], "locality_key": p["locality_key"],
            "door_no": p["door_no"] if p["door_no"] is not None else "",
            "pincode": p["pincode"],
        })
    rows.sort(key=lambda r: r["part_no"])

    with open(booth_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"\nWrote {len(rows)} booths -> {booth_csv}")
    print(f"  tier=street        : {tier_counts['street']:3}  (best)")
    print(f"  tier=locality      : {tier_counts['locality']:3}  (medium)")
    print(f"  tier=ac_centroid   : {tier_counts['ac_centroid']:3}  (worst)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
