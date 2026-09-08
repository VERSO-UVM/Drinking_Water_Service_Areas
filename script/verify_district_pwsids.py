"""
Verify every district's PWSID against EPA SDWIS.

The name-based crosswalk assigned a PWSID to each district by fuzzy matching,
which fails quietly: "Sherburne Fire District 1" (Killington) was matched to
"SHELBURNE FARMS" (Shelburne) on a one-letter difference, and two districts
that provide no drinking water at all were handed drinking-water identifiers.

Name similarity alone cannot catch those, so this checks six independent axes
and reports which ones disagree:

  exists      the PWSID is in SDWIS at all
  name        district name vs. the SDWIS system name
  town        district town vs. the SDWIS city
  population  roster population vs. SDWIS population_served_count
  active      the SDWIS activity code
  service     a district that supplies no water should hold no PWSID
  unique      two districts sharing one PWSID is a signature of a bad match

Output: data/vt_district_pwsid_check.csv, one row per district with a verdict
of OK, CHECK or WRONG and the specific axes that failed.

Usage:
  python script/verify_district_pwsids.py [--apply]

--apply writes the confirmed corrections back into
data/vt_district_crosswalk.csv (clearing spurious ids, correcting known ones)
and prints a diff. Without it, nothing is modified.
"""

import argparse
import csv
import json
import re
import sys
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CROSSWALK = ROOT / "data" / "vt_district_crosswalk.csv"
ROSTER = ROOT / "data" / "vt_district_roster.csv"
OUT = ROOT / "data" / "vt_district_pwsid_check.csv"
CACHE = ROOT / "data" / "sdwis_vt.json"

SDWIS_URL = "https://data.epa.gov/efservice/WATER_SYSTEM/PRIMACY_AGENCY_CODE/VT/JSON"

# Corrections established by evidence outside this script and recorded here so
# --apply is reproducible rather than a one-off edit.
KNOWN_FIXES = {
    # district_name: (new_pwsid_or_empty, why)
    "Sherburne Fire District 1": (
        "", "Municipal sewer district, supplies no drinking water. VT0005602 is "
            "SHELBURNE FARMS in Shelburne -- a one-letter name collision."),
    "North Branch Fire District 1": (
        "", "Wastewater-only district. VT0005211 belongs to Brandon Fire "
            "District 1, which already holds it."),
    "Rutland Town Fire District 11": (
        "VT0021007", "VT0005534 is Rutland Town Fire District 1 (SDWIS pop 401). "
                     "FD 11 is VT0021007, pop 29, matching the VRWA workbook."),
}

NAME_STOP = re.compile(
    r"\b(fire district|water district|water system|water co|company|"
    r"town of|village of|city of|fd|wd|no|number|inc|the)\b")


def norm(s):
    s = (s or "").lower()
    s = NAME_STOP.sub(" ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def load_sdwis(refresh=False):
    if CACHE.exists() and not refresh:
        data = json.loads(CACHE.read_text(encoding="utf-8"))
    else:
        print("  fetching SDWIS (Vermont)...")
        r = requests.get(SDWIS_URL, timeout=300)
        r.raise_for_status()
        data = r.json()
        CACHE.write_text(json.dumps(data), encoding="utf-8")
    # The efservice endpoint returns lowercase keys; earlier code assumed upper
    # case and silently matched nothing. Normalise once, here.
    out = {}
    for row in data:
        low = {k.lower(): v for k, v in row.items()}
        if low.get("pwsid"):
            out[low["pwsid"]] = low
    print(f"  {len(out)} Vermont systems in SDWIS")
    return out


def load_districts():
    rows = list(csv.DictReader(CROSSWALK.open(encoding="utf-8-sig")))
    pops = {}
    if ROSTER.exists():
        for r in csv.DictReader(ROSTER.open(encoding="utf-8-sig")):
            if r.get("population", "").strip():
                pops[r["district_name"].strip()] = r["population"].strip()
    return rows, pops


def as_int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def check(rows, sdwis, pops):
    dupes = Counter(r["matched_pwsid"].strip() for r in rows
                    if r["matched_pwsid"].strip())
    results = []

    for r in rows:
        name = r["district_name"].strip()
        pwsid = r["matched_pwsid"].strip()
        services = r.get("services", "").strip()
        town = r.get("town", "").strip()
        supplies_water = "water" in services.lower()

        fails, notes = [], []

        if not pwsid:
            results.append(dict(district_name=name, town=town, services=services,
                                assigned_pwsid="", sdwis_pws_name="",
                                sdwis_city="", sdwis_population="",
                                sdwis_activity="", verdict="NO_PWSID",
                                failed_checks="", notes="No PWSID assigned."))
            continue

        sys_row = sdwis.get(pwsid)
        if not sys_row:
            results.append(dict(district_name=name, town=town, services=services,
                                assigned_pwsid=pwsid, sdwis_pws_name="",
                                sdwis_city="", sdwis_population="",
                                sdwis_activity="", verdict="WRONG",
                                failed_checks="exists",
                                notes="PWSID does not appear in SDWIS."))
            continue

        pws_name = sys_row.get("pws_name") or ""
        city = (sys_row.get("city_name") or "").strip()
        sd_pop = as_int(sys_row.get("population_served_count"))
        activity = (sys_row.get("pws_activity_code") or "").strip()

        score = SequenceMatcher(None, norm(name), norm(pws_name)).ratio()
        if score < 0.60:
            fails.append("name")
            notes.append(f"name similarity {score:.2f}")

        if city and town and norm(town) not in norm(city) \
                and norm(city) not in norm(town):
            fails.append("town")
            notes.append(f"district town {town!r} vs SDWIS city {city!r}")

        roster_pop = as_int(pops.get(name))
        if roster_pop and sd_pop and roster_pop != sd_pop:
            # Small drift is normal; an order of magnitude is not.
            if abs(roster_pop - sd_pop) > max(25, 0.25 * max(roster_pop, sd_pop)):
                fails.append("population")
                notes.append(f"roster {roster_pop} vs SDWIS {sd_pop}")

        if activity and activity != "A":
            fails.append("active")
            notes.append(f"SDWIS activity code {activity}")

        if not supplies_water:
            fails.append("service")
            notes.append(f"district services are {services!r} -- "
                         f"no drinking water, so a PWSID is unexpected")

        if dupes[pwsid] > 1:
            others = [x["district_name"] for x in rows
                      if x["matched_pwsid"].strip() == pwsid
                      and x["district_name"] != name]
            fails.append("unique")
            notes.append(f"PWSID also assigned to {', '.join(others)}")

        # SDWIS city_name is a mailing address, not a municipality: a district
        # in Barnet legitimately posts from McIndoe Falls, one in Barre Town
        # from Graniteville. On its own a town mismatch means nothing, so it
        # only counts as corroboration alongside another failure.
        substantive = [f for f in fails if f != "town"]

        if "service" in fails or "exists" in fails or len(substantive) >= 2:
            verdict = "WRONG"
        elif substantive:
            verdict = "CHECK"
        else:
            verdict = "OK"
            if "town" in fails:
                notes.append("mailing city differs from the town, which is "
                             "normal where the system serves a named village")

        results.append(dict(
            district_name=name, town=town, services=services,
            assigned_pwsid=pwsid, sdwis_pws_name=pws_name, sdwis_city=city,
            sdwis_population="" if sd_pop is None else sd_pop,
            sdwis_activity=activity, verdict=verdict,
            failed_checks="|".join(fails), notes="; ".join(notes)))

    return results


def apply_fixes(rows):
    changed = []
    for r in rows:
        name = r["district_name"].strip()
        if name in KNOWN_FIXES:
            new, why = KNOWN_FIXES[name]
            old = r["matched_pwsid"].strip()
            if old != new:
                r["matched_pwsid"] = new
                # These fields described the old, wrong match.
                for f in ("matched_pws_name", "match_score", "match_status"):
                    if f in r:
                        r[f] = "" if f != "match_status" else "corrected_2026-09-08"
                changed.append((name, old, new or "(cleared)", why))

    if not changed:
        print("  nothing to change")
        return

    with CROSSWALK.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"\n  applied {len(changed)} corrections to "
          f"{CROSSWALK.relative_to(ROOT)}:")
    for name, old, new, why in changed:
        print(f"    {name}")
        print(f"      {old} -> {new}")
        print(f"      {why}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="write the known corrections into the crosswalk")
    ap.add_argument("--refresh", action="store_true", help="re-download SDWIS")
    args = ap.parse_args()

    if not CROSSWALK.exists():
        sys.exit(f"Missing {CROSSWALK}")

    print("Verifying district PWSIDs against SDWIS:")
    sdwis = load_sdwis(args.refresh)
    rows, pops = load_districts()
    results = check(rows, sdwis, pops)

    fields = ["district_name", "town", "services", "assigned_pwsid",
              "sdwis_pws_name", "sdwis_city", "sdwis_population",
              "sdwis_activity", "verdict", "failed_checks", "notes"]
    with OUT.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(results)

    tally = Counter(r["verdict"] for r in results)
    print(f"\n  {len(results)} districts checked -> "
          + ", ".join(f"{v} {k}" for k, v in tally.most_common()))
    print(f"  wrote {OUT.relative_to(ROOT)}")

    for verdict in ("WRONG", "CHECK"):
        bad = [r for r in results if r["verdict"] == verdict]
        if not bad:
            continue
        print(f"\n  {verdict} ({len(bad)}):")
        for r in bad:
            print(f"    {r['district_name'][:38]:<38} {r['assigned_pwsid']:<11} "
                  f"[{r['failed_checks']}]")
            print(f"        {r['notes'][:110]}")

    if args.apply:
        apply_fixes(rows)


if __name__ == "__main__":
    main()
