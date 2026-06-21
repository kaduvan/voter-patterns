#!/usr/bin/env python3
"""
Ecological inference (EI) for AC018: how did age/gender cohorts vote?

METHOD — Goodman ecological regression (the defensible analyst-standard EI).
For each (cohort c, alliance a) we run an OLS regression across booths:

    votes_a_b / V_b  =  alpha  +  beta * (electors_c_b / N_b)  +  eps_b

where b indexes booths, V_b = valid votes, N_b = total electors.

Interpretation:
  - beta * (N_b/N) estimates the extra vote share party a picks up per unit of
    cohort-c presence. Scaled to the cohort's electorate share, beta gives an
    estimate of the cohort's support rate for party a.
  - alpha is the baseline party-a vote share where cohort c is absent.
  - R^2 is the honesty signal: low R^2 = geography doesn't track this cohort's
    vote, treat the estimate as weak.

WHY NOT Duncan-Davis bounds: with unknown per-cohort turnout the per-booth
feasible intervals collapse to [0,1] (degenerate) whenever the cohort is a large
share — which is true for Harbour's big 30-49 bands. Goodman regression uses the
CROSS-BOOTH variation, which is where the actual signal lives, and produces a
point estimate with an explicit uncertainty (R^2 + SE). This is what real
analyst reports publish. Per the election prompt v4: "wide-interval,
illustrative" — we report beta + CI, never overclaiming causality.

Outputs:
  data/ei_ac018_<year>.json   {cohort: {alliance: {beta, alpha, r2, se, n}}}
                              + a derived 'estimated_support' = alpha + beta*cshare

Usage: python scripts/compute_ei.py
"""
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from alliances import alliance_for

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"

AGE_BANDS = ["18-21", "22-29", "30-39", "40-49", "50-59", "60-69", "70+"]
COHORTS = AGE_BANDS + ["Under-30", "60+"]


def load_year(year):
    """Booths with both demographics (2026 frame) and Form-20 votes for `year`."""
    cands = json.load(open(DATA / f"candidates_ac018_{year}.json", encoding="utf-8"))
    with open(DATA / f"votes_ac018_{year}.csv", encoding="utf-8") as f:
        votes = list(csv.DictReader(f))
    demo = {}
    dpath = BASE / "analysis" / "booth_age_gender_distribution.csv"
    if dpath.exists():
        with open(dpath, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                demo[int(r["booth_number"])] = r

    booths = []
    for v in votes:
        sno = int(v["station_no"])
        if sno not in demo:
            continue
        d = demo[sno]
        alliance_votes = defaultdict(int)
        for c in cands:
            vv = int(v.get(c["name"], 0) or 0)
            if vv > 0:
                alliance_votes[alliance_for(c["party"], year)] += vv
        total_valid = int(v.get("total_valid", 0) or 0)
        if total_valid <= 0:
            continue
        cohorts = {b: int(d[f"{b}_Total"]) for b in AGE_BANDS}
        cohorts["Under-30"] = cohorts["18-21"] + cohorts["22-29"]
        cohorts["60+"] = cohorts["60-69"] + cohorts["70+"]
        total_electors = int(d["Booth_Total"])
        booths.append({
            "station_no": sno,
            "total_valid": total_valid,
            "total_electors": total_electors,
            "alliance_votes": dict(alliance_votes),
            "cohorts": cohorts,
        })
    return booths


def ols(xs, ys):
    """Simple OLS y = a + b*x. Returns (alpha, beta, r2, se_beta, n)."""
    n = len(xs)
    if n < 3:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0:
        return None
    beta = sxy / sxx
    alpha = my - beta * mx
    # R^2
    ss_res = sum((y - (alpha + beta * x)) ** 2 for x, y in zip(xs, ys))
    r2 = 1 - ss_res / syy if syy > 0 else 0.0
    # SE of beta
    if n > 2 and ss_res > 0:
        se_beta = math.sqrt(ss_res / (n - 2)) / math.sqrt(sxx)
    else:
        se_beta = 0.0
    return {"alpha": round(alpha, 4), "beta": round(beta, 4),
            "r2": round(r2, 4), "se_beta": round(se_beta, 4), "n": n}


def goodman_for(booths, cohort, alliance):
    """Goodman regression: party vote share ~ cohort elector share.

    Estimated cohort support rate for the alliance = alpha + beta (i.e. the
    predicted party vote share in a hypothetical 100%-cohort booth), clamped to
    [0,1]. We also report the per-booth implied support spread.
    """
    xs, ys = [], []
    for b in booths:
        c = b["cohorts"][cohort]
        N = b["total_electors"]
        V = b["total_valid"]
        if N <= 0 or V <= 0:
            continue
        xs.append(c / N)                       # cohort share of electors
        ys.append(b["alliance_votes"].get(alliance, 0) / V)  # party vote share
    fit = ols(xs, ys)
    if fit is None:
        return None
    # Estimated cohort support = predicted party share when cohort share -> 1
    est = max(0.0, min(1.0, fit["alpha"] + fit["beta"]))
    fit["estimated_support"] = round(est, 4)
    # 95% CI on the slope-derived estimate (rough): est +/- 1.96*se_beta
    fit["ci"] = [round(max(0.0, est - 1.96 * fit["se_beta"]), 4),
                 round(min(1.0, est + 1.96 * fit["se_beta"]), 4)]
    return fit


def compute_all(year):
    booths = load_year(year)
    print(f"  {year}: {len(booths)} booths")
    if not booths:
        return None
    alliances = set()
    for b in booths:
        alliances.update(b["alliance_votes"].keys())
    # keep alliances with >=1% of total votes (drop the noise independents)
    tot = sum(b["total_valid"] for b in booths)
    alliance_tot = defaultdict(int)
    for b in booths:
        for a, v in b["alliance_votes"].items():
            alliance_tot[a] += v
    keep = sorted([a for a, v in alliance_tot.items() if v / tot >= 0.005],
                  key=lambda a: -alliance_tot[a])
    print(f"    alliances kept (>=0.5% of votes): {keep}")

    result = {"year": year, "n_booths": len(booths), "alliances": keep,
              "alliance_vote_shares": {a: round(alliance_tot[a] / tot, 4) for a in keep},
              "intervals": {}, "method": "Goodman ecological regression",
              "note": "beta = party vote-share gained per unit of cohort presence; "
                      "estimated_support = predicted party share in a 100%-cohort booth. "
                      "R^2 is the honesty signal (low R^2 -> weak inference). "
                      "Illustrative association, NOT proven individual vote choice."}
    for cohort in COHORTS:
        result["intervals"][cohort] = {}
        for alliance in keep:
            fit = goodman_for(booths, cohort, alliance)
            result["intervals"][cohort][alliance] = fit
    out = DATA / f"ei_ac018_{year}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"    -> {out.name}")
    return result


def main():
    print("Computing Goodman ecological regression for AC018...")
    for year in (2026, 2024, 2021):
        r = compute_all(year)
        if r and year == 2026:
            print("\n  2026 — estimated cohort support rate per alliance (R^2 in parens):")
            print(f"    {'cohort':<10}", end="")
            for a in r["alliances"]:
                print(f"{a:>14}", end="")
            print()
            for cohort in COHORTS:
                print(f"    {cohort:<10}", end="")
                for a in r["alliances"]:
                    f = r["intervals"][cohort][a]
                    if f is None:
                        print(f"{'--':>14}", end="")
                    else:
                        print(f"  {f['estimated_support']*100:>4.0f}%({f['r2']:.2f})", end="")
                print()
            print(f"\n  2026 overall alliance vote shares: {r['alliance_vote_shares']}")


if __name__ == "__main__":
    main()

