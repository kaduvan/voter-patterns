#!/usr/bin/env python3
"""
Geocode AC018 booths via OpenStreetMap Nominatim — STREET + LOCALITY strategy
with a 3-TIER fallback so EVERY booth gets a coordinate, precision labeled.

WHY THIS DESIGN: AC018 (Harbour = old George Town, North Chennai) is a dense
grid of named streets. Nominatim resolves SOME street names (Mint Street,
Armenian Street, Seven Wells Street...) but NOT the descriptive school/office
names, and many minor streets are simply not in OSM as searchable named ways.
A wide Chennai viewbox returned namesake streets in wrong zones; a TIGHT
bounded=true box fixes precision but leaves coverage partial. So:

  Tier 1 — STREET: parse + normalize the building's street token, geocode
           "<Street>, Chennai" inside the tight AC018 box. Best precision.
           Door-number jitter separates booths sharing a street.
  Tier 2 — LOCALITY: fall back to the locality centroid (Sowcarpet, Sevenwells,
           Kondithope, Park Town, George Town, Broadway, Island Ground...),
           also geocoded inside the tight box. Medium precision.
  Tier 3 — AC018 CENTROID: George Town centre. Worst case; few booths.

Every row records its `precision` tier so the map/UI can flag approximate
points. Building-exact coords can later be pasted over lat/lon for refinement.

Inputs:  data/booths_ac018.csv
Outputs: data/street_coords.csv   (distinct streets -> lat/lon/display_name)
         data/locality_coords.csv (distinct localities -> lat/lon/display_name)
         data/booth_coords.csv    (one row per part_no -> lat/lon/tier/source)

Usage: python scripts/geocode_booths.py
"""
import csv
import hashlib
import re
import sys
import time
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent.parent
IN_CSV = BASE / "data" / "booths_ac018.csv"
STREET_CSV = BASE / "data" / "street_coords.csv"
LOCALITY_CSV = BASE / "data" / "locality_coords.csv"
BOOTH_CSV = BASE / "data" / "booth_coords.csv"

# George Town centre = Tier-3 fallback.
AC018_CENTROID = (13.0921, 80.2822)

USER_AGENT = "ac018-harbour-booth-demographics/1.0 (local analysis; contact: operator)"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# TIGHT viewbox = real AC018 footprint (George Town / Harbour, North Chennai).
# A wide Chennai box returned namesake streets in wrong zones; bounded=true on
# this tight box forces results into the constituency, eliminating false hits.
AC018_VIEWBOX = "80.260,13.075,80.300,13.115"

# Max per-street offset in degrees (~0.0018 deg ~ 200 m). Booths sharing a
# street are spread within this radius using their door number.
MAX_OFFSET_DEG = 0.0018


# ─── Address parsing ────────────────────────────────────────────────────────

# Match the LAST occurrence of "<Name> Street|Salai|Road|Lane|Broadway" in the
# string. The last street is usually the one the building sits on. Broadway is
# an area but tagged like a street in these addresses ("No:28, Broadway").
STREET_RE = re.compile(
    r"([A-Za-z][A-Za-z.'\- ]*?\s+(?:Street|Salai|Road|Lane)|Broadway)\b",
    re.IGNORECASE,
)
# Door number: "No:508", "No. 508", "No 508", "New No 17", "No:26-24 and 29"
DOOR_RE = re.compile(r"(?:New\s+)?No\.?\s*:?\s*(\d{1,4})", re.IGNORECASE)

LOCALITIES = [
    "Sowcarpet", "Kondithope", "Sevenwells", "Seven Wells", "Park Town",
    "George Town", "Muthaiyalpet", "Muthialpet", "Muthaialpet",
    "Vallal Seethakhadhi", "Vallal Seethakathi", "Kachaleeswarar",
    "Kachaleswarar", "Elephantgate", "Elephant Gate", "Edapalayam",
    "Broadway", "Island Ground", "Mannady", "Royapuram", "Tondiarpet",
    "Washermanpet", "Korukkupet", "Vannarapettah", "Chintadripet",
    "Chindadripet", "Purasawalkam", "Vepery",
]
LOCALITY_RE = re.compile(
    r"\b(" + "|".join(re.escape(l) for l in sorted(LOCALITIES, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)

# Map a normalized street key to the query string that OSM actually indexes.
# Discovered empirically by probing George Town streets with bounded=true.
STREET_QUERY_OVERRIDES = {
    "aremenian street": "Armenian Street",
    "mc leans street": "McLean Street",
    "mclean street": "McLean Street",
    "sevenwells street": "Seven Wells Street",
    "northbeach road": "North Beach Road",
    "north beach road": "North Beach Road",
    "porchuges church street": "Portuguese Church Street",
    "annasalai": "Anna Salai",
    "anna salai": "Anna Salai",
    "v o c salai": "Prakasam Salai",      # VOC Salai was renamed Prakasam Salai
    "voc salai": "Prakasam Salai",
    "adhiyappan street": "Aadhiyappan Street",
    "aadhiyappa street": "Aadhiyappan Street",
    "ravanaiyar street": "Ravanaiah Street",
    "ek agraharam street": "Ekambaranathar Agraharam Street",
    "ekambaraeswarar agraharam street": "Ekambaranathar Agraharam Street",
}


def parse_address(building: str) -> dict:
    """Extract street, door_no, locality from a building string."""
    streets = STREET_RE.findall(building)
    street = streets[-1].strip() if streets else ""  # last = building's street
    door_match = DOOR_RE.search(building)
    door_no = int(door_match.group(1)) if door_match else None
    loc_match = LOCALITY_RE.search(building)
    locality = loc_match.group(1).title() if loc_match else ""
    return {"street": street, "door_no": door_no, "locality": locality}


def norm_street(s: str) -> str:
    """Normalize a street token for dedup: lowercase, strip dots/apostrophes,
    collapse whitespace."""
    s = s.lower().replace(".", " ").replace("'", " ").replace("-", " ")
    return re.sub(r"\s+", " ", s).strip()


def query_for_street(street: str) -> str:
    """Pick the Nominatim query string for a street token (apply overrides)."""
    return STREET_QUERY_OVERRIDES.get(norm_street(street), street)


def norm_locality(s: str) -> str:
    """Normalize a locality for dedup."""
    return re.sub(r"\s+", " ", s.lower()).strip()


# Map a normalized locality key to the query string OSM indexes. Discovered by
# probing George Town localities with bounded=true. Merges spelling variants to
# a single canonical form so all booths in one area share one coordinate.
LOCALITY_QUERY_OVERRIDES = {
    "muthaiyalpet": "Muthialpet",
    "muthaialpet": "Muthialpet",
    "muthialpet": "Muthialpet",
    "sevenwells": "Seven Wells Street",
    "seven wells": "Seven Wells Street",
    "vallal seethakhadhi": "Vallal Seethakathi Nagar",
    "vallal seethakathi": "Vallal Seethakathi Nagar",
    "elephantgate": "Elephant Gate",
    "elephant gate": "Elephant Gate",
    "edapalayam": "Edapalayam, Chennai",
    "kachaleeswarar": "Kachaleeswarar Temple, Chennai",
    "kachaleswarar": "Kachaleeswarar Temple, Chennai",
    "island ground": "Island Ground, Chennai",
}


def query_for_locality(locality: str) -> str:
    return LOCALITY_QUERY_OVERRIDES.get(norm_locality(locality), locality)


# ─── Nominatim ──────────────────────────────────────────────────────────────

def _nom(q: str) -> dict | None:
    """Single Nominatim query inside the tight AC018 box, bounded=true. Returns
    top hit or None. Retries transient network/rate errors."""
    params = {
        "q": q, "format": "jsonv2", "limit": 1, "countrycodes": "in",
        "viewbox": AC018_VIEWBOX, "bounded": "true", "addressdetails": "1",
    }
    for attempt in range(3):
        try:
            r = requests.get(NOMINATIM_URL, params=params,
                             headers={"User-Agent": USER_AGENT}, timeout=30)
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
                     query_fn, label: str) -> dict:
    """Geocode a dict of {key: {'display':..., 'count':...}}, query per item.
    query_fn(display) -> query string. Resumable via cache file."""
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
            hit = _nom(query_fn(disp))
            _write_hit(w, fields, key_field, key, disp, hit)
            f.flush()
            time.sleep(1.1)
    return load_cache(path, key_field)


def geocode_all_streets(streets: dict) -> dict:
    return geocode_entities(streets, STREET_CSV, "street_key",
                            query_for_street, "STREETS")


def geocode_all_localities(localities: dict) -> dict:
    return geocode_entities(localities, LOCALITY_CSV, "locality_key",
                            query_for_locality, "LOCALITIES")


# ─── Booth placement ────────────────────────────────────────────────────────

def jitter_offset(part_no: int, door_no: int | None) -> tuple[float, float]:
    """Deterministic (lat, lon) offset within MAX_OFFSET_DEG.

    Uses door_no when available (signal of where along the street), scaled with
    a gentle curve; plus a deterministic hash of part_no for the orthogonal axis
    so multiple booths on the same street separate visibly.
    """
    frac = 1.0 / (1.0 + (door_no or 250) / 250.0)  # door 250 -> ~0.5
    h = hashlib.md5(f"ac018-{part_no}".encode()).hexdigest()
    perp = int(h[:8], 16) / 0xFFFFFFFF
    d_lat = (frac - 0.5) * 2 * MAX_OFFSET_DEG
    d_lon = (perp - 0.5) * 2 * MAX_OFFSET_DEG
    return d_lat, d_lon


def main() -> int:
    if not IN_CSV.exists():
        print(f"ERROR: {IN_CSV} not found. Run parse_booths_ac018.py first.",
              file=sys.stderr)
        return 1

    with open(IN_CSV, encoding="utf-8") as f:
        booths = list(csv.DictReader(f))

    # Parse every booth's address; collect distinct streets + localities.
    streets, localities = {}, {}
    parsed = []
    for b in booths:
        a = parse_address(b["building"])
        s_key = norm_street(a["street"]) if a["street"] else ""
        l_key = norm_locality(a["locality"]) if a["locality"] else ""
        parsed.append({**a, "street_key": s_key, "locality_key": l_key,
                       "part_no": int(b["part_no"]), "pincode": b["pincode"],
                       "building": b["building"]})
        if s_key:
            streets.setdefault(s_key, {"display": a["street"], "count": 0})["count"] += 1
        if l_key:
            localities.setdefault(l_key, {"display": a["locality"], "count": 0})["count"] += 1

    print(f"Booths: {len(parsed)} | with street: {sum(1 for p in parsed if p['street_key'])} "
          f"({len(streets)} distinct) | with locality: "
          f"{sum(1 for p in parsed if p['locality_key'])} ({len(localities)} distinct)")

    # Geocode both tiers (resumable; cached CSVs).
    street_cache = geocode_all_streets(streets)
    locality_cache = geocode_all_localities(localities)
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
            d_lat, d_lon = jitter_offset(p["part_no"], p["door_no"])
            lat, lon = round(float(lat) + d_lat, 6), round(float(lon) + d_lon, 6)
            tier, source = "street", "nominatim:street"
        else:
            lc = locality_cache.get(p["locality_key"], {})
            lat, lon = lc.get("lat", "") or "", lc.get("lon", "") or ""
            if lat and lon:
                d_lat, d_lon = jitter_offset(p["part_no"], p["door_no"])
                lat, lon = round(float(lat) + d_lat, 6), round(float(lon) + d_lon, 6)
                tier, source = "locality", "nominatim:locality"
            else:
                lat, lon = round(AC018_CENTROID[0], 6), round(AC018_CENTROID[1], 6)
                tier, source = "ac_centroid", "ac018_centroid"
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

    with open(BOOTH_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"\nWrote {len(rows)} booths -> {BOOTH_CSV}")
    print(f"  tier=street        : {tier_counts['street']:3}  (best)")
    print(f"  tier=locality      : {tier_counts['locality']:3}  (medium)")
    print(f"  tier=ac_centroid   : {tier_counts['ac_centroid']:3}  (worst)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
