#!/usr/bin/env python3
"""
Build a Vermont water/fire DISTRICT coverage inventory by crosswalking three
sources, since no authoritative statewide district registry exists:

  1. Title 24 Appendix legislative charters  (authoritative, incomplete)
     -> scraped from legislature.vermont.gov; each chartered district, its
        chapter number, and a link to charter text (which contains a
        "Boundaries" section = the authoritative political boundary, in prose).
  2. EPA water SERVICE AREAS                  (your vt_water_boundaries.csv)
     -> the "has a known service-area polygon" spine, keyed on PWS_Name/PWSID.
  3. VLCT compiled district list              (optional, manual)
     -> VLCT publishes a compiled-but-non-authoritative list; there is no clean
        machine endpoint, so this script accepts an optional CSV you paste in
        (column: district_name) and folds it in. Leave it out to skip.

WHAT THIS PRODUCES (not boundaries -- an inventory that scopes the boundary work):
  district_crosswalk.csv   one row per district/system, with:
      - source              charter | epa_system | vlct
      - district_name       normalized name
      - charter_chapter     Title 24 App chapter # (if chartered)
      - charter_url         link to charter text w/ Boundaries section
      - matched_pwsid       EPA PWSID if matched
      - matched_pws_name    EPA PWS_Name if matched
      - match_score         0-100 fuzzy score
      - match_status        auto_confident | review | none
      - has_service_polygon Y/N  (does an EPA polygon exist)
      - has_political_bnd    N    (placeholder -- almost always N to start)
  district_review_queue.csv   just the rows needing human confirmation.

Matching policy (per your call): auto-match, flag low-confidence for review.
  >=90  auto_confident
  70-89 review
  <70   none

Run:
  uv run --with requests --with rapidfuzz --with pandas build_district_crosswalk.py
  # or:
  pip install requests rapidfuzz pandas
  python build_district_crosswalk.py --epa vt_water_boundaries.csv [--vlct vlct_list.csv]
"""

import argparse
import re
import sys
import time
import html as htmllib
import requests
import pandas as pd
from rapidfuzz import fuzz, process

INDEX_URL = "https://legislature.vermont.gov/statutes/title/24appendix"
CHAPTER_URL = "https://legislature.vermont.gov/statutes/chapter/24appendix/{chap}"
HEADERS = {"User-Agent": "VERSO-UVM district inventory (research; contact via github.com/VERSO-UVM)"}
TIMEOUT = 60

# Which chartered entities count as water/fire/sewer districts for this project.
DISTRICT_RE = re.compile(r"\b(fire district|water district|water corporation|"
                         r"water & sewer|water and sewer|sewer district|"
                         r"fire & water|consolidated water)\b", re.I)

AUTO = 90
REVIEW = 70


def fetch(url):
    for attempt in range(4):
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            r.raise_for_status()
            return r.text
        except requests.RequestException as e:
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))


def scrape_charter_index():
    """Return [(chapter, name, url), ...] for fire/water/sewer district charters."""
    txt = fetch(INDEX_URL)
    # The index renders chapter links as: Chapter 507: Cold Brook Fire District No. 1
    # Match both "Chapter 507:" and "Chapter 155A:" (alphanumeric chapter ids).
    pat = re.compile(r"Chapter\s+(\d+[A-Z]?)\s*[:\-]\s*([^<\n]+?)\s*(?:</|\n|Contains)", re.I)
    seen = {}
    for m in pat.finditer(txt):
        chap, name = m.group(1).strip(), htmllib.unescape(m.group(2).strip())
        if DISTRICT_RE.search(name):
            seen[chap] = name
    rows = [{"source": "charter",
             "district_name": name,
             "charter_chapter": chap,
             "charter_url": CHAPTER_URL.format(chap=chap)}
            for chap, name in sorted(seen.items())]
    if not rows:
        print("WARNING: no district charters parsed -- the index HTML shape may "
              "have changed. Inspect INDEX_URL by hand.", file=sys.stderr)
    return rows


def norm(s):
    s = str(s).lower()
    s = re.sub(r"\bno\.?\s*\d+\b", "", s)      # drop "No. 1"
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\b(the|inc|incorporated|charter|corporation|corp)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epa", default="vt_water_boundaries.csv",
                    help="EPA attribute CSV from pull_vt_water_boundaries.py")
    ap.add_argument("--vlct", default=None,
                    help="optional VLCT list CSV with a 'district_name' column")
    args = ap.parse_args()

    # --- load EPA systems (the match target) ---
    epa = pd.read_csv(args.epa)
    name_col = "PWS_Name" if "PWS_Name" in epa.columns else epa.columns[0]
    epa["_norm"] = epa[name_col].map(norm)
    epa_choices = epa["_norm"].tolist()

    # --- source 1: charters ---
    charters = scrape_charter_index()
    print(f"Chartered water/fire districts found: {len(charters)}")

    # --- source 3: VLCT (optional) ---
    vlct_rows = []
    if args.vlct:
        v = pd.read_csv(args.vlct)
        vcol = "district_name" if "district_name" in v.columns else v.columns[0]
        vlct_rows = [{"source": "vlct", "district_name": str(n),
                      "charter_chapter": "", "charter_url": ""}
                     for n in v[vcol].dropna().unique()]
        print(f"VLCT list entries: {len(vlct_rows)}")

    district_rows = charters + vlct_rows

    # --- fuzzy match each district to an EPA system ---
    out = []
    for d in district_rows:
        q = norm(d["district_name"])
        best = process.extractOne(q, epa_choices, scorer=fuzz.token_sort_ratio)
        score = best[1] if best else 0
        if score >= AUTO:
            status = "auto_confident"
        elif score >= REVIEW:
            status = "review"
        else:
            status = "none"

        matched_pwsid = matched_name = ""
        if best and score >= REVIEW:
            row = epa.iloc[best[2]]
            matched_pwsid = row.get("PWSID", "")
            matched_name = row.get(name_col, "")

        out.append({**d,
                    "matched_pwsid": matched_pwsid,
                    "matched_pws_name": matched_name,
                    "match_score": round(score),
                    "match_status": status,
                    "has_service_polygon": "Y" if matched_pwsid else "N",
                    "has_political_bnd": "N"})   # seed; fill during digitizing

    # --- also surface EPA systems NOT matched to any charter/VLCT district ---
    matched_ids = {r["matched_pwsid"] for r in out if r["matched_pwsid"]}
    for _, row in epa.iterrows():
        pid = row.get("PWSID", "")
        if pid and pid not in matched_ids:
            out.append({"source": "epa_system",
                        "district_name": row.get(name_col, ""),
                        "charter_chapter": "", "charter_url": "",
                        "matched_pwsid": pid,
                        "matched_pws_name": row.get(name_col, ""),
                        "match_score": "", "match_status": "unmatched_system",
                        "has_service_polygon": "Y", "has_political_bnd": "N"})

    df = pd.DataFrame(out)
    df.to_csv("district_crosswalk.csv", index=False)
    df[df["match_status"] == "review"].to_csv("district_review_queue.csv", index=False)

    print("\nWrote district_crosswalk.csv")
    print(df["match_status"].value_counts().to_string())
    print("\nWrote district_review_queue.csv (rows needing manual confirmation)")


if __name__ == "__main__":
    main()
