#!/usr/bin/env python3
"""
Pull the "Boundaries" section text from Title 24 Appendix charters for the
Vermont water/fire districts that were formed by legislative charter.

WHAT you get (and its limits):
  Each charter's Boundaries section is fetched and attached to the crosswalk.
  IMPORTANT: many charters do NOT contain a metes-and-bounds description --
  they POINT to a recorded plat in town land records, e.g. Cold Brook:
    "boundaries ... as recorded in Book 111, page 184 ... Town of Wilmington".
  So this gives a digitizer the exact record to go pull, not geometry itself.
  A few older charters do carry a full survey description; those come through
  as the full text.

INPUT:  vt_district_crosswalk.csv (or _spatial version) -- optional; used only
        to left-join the boundary text onto matching district rows.
OUTPUT: charter_boundaries.csv          (chapter, district, boundary_text, url)
        vt_district_crosswalk_charters.csv (crosswalk + charter_boundary_text)

Run:
  pip install pip-system-certs requests pandas
  python pull_charter_boundaries.py
"""

import re, sys, time, html as htmllib
import requests
import pandas as pd

# Title 24 Appendix chapters for chartered water/fire districts.
# (chapter, canonical district name)
CHARTERS = {
    "501": "Milton Fire District No. 1",
    "503": "St. George Fire District No. 1",
    "504": "Bolton Fire District No. 1",
    "505": "Williamstown Fire District",
    "507": "Cold Brook Fire District No. 1",
    "509": "North Branch Fire District No. 1",
    "511": "Fairfax Fire District No. 1",
    "701": "Morristown Corners Water Corporation",
    "703": "Champlain Water District",
    "705": "Edward Farrar Utility District",
}
URL = "https://legislature.vermont.gov/statutes/fullchapter/24APPENDIX/{chap}"
XWALK = "vt_district_crosswalk.csv"
TIMEOUT = 60


def fetch(url):
    for attempt in range(4):
        try:
            r = requests.get(url, timeout=TIMEOUT)
            r.raise_for_status()
            return r.text
        except requests.RequestException:
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))


def extract_boundaries(html):
    """Return the text of the section titled 'Boundaries', or '' if none."""
    text = re.sub(r"<[^>]+>", "\n", html)
    text = htmllib.unescape(text)
    lines = [ln.strip() for ln in text.splitlines()]
    text = "\n".join(lines)

    # Find "§ N. Boundaries" and capture until the next "§ N. <Something>".
    m = re.search(r"§\s*\d+\.?\s*Boundaries\b(.*?)(?=§\s*\d+\.?\s+[A-Z])",
                  text, re.S | re.I)
    if not m:
        # Some charters fold boundaries into a "Creation" or "District" section.
        m = re.search(r"§\s*\d+\.?\s*(?:Creation|District|Territory)\b(.*?)"
                      r"(?=§\s*\d+\.?\s+[A-Z])", text, re.S | re.I)
        if not m:
            return ""
    body = re.sub(r"\n{2,}", " ", m.group(1)).strip()
    return re.sub(r"\s{2,}", " ", body)


def main():
    rows = []
    for chap, name in CHARTERS.items():
        url = URL.format(chap=chap)
        try:
            b = extract_boundaries(fetch(url))
        except Exception as e:
            b = f"[fetch error: {e}]"
        pointer = bool(re.search(r"recorded in Book|land records|page \d+", b, re.I))
        rows.append({"charter_chapter": chap, "district_name": name,
                     "charter_url": url,
                     "boundary_is_record_pointer": "Y" if pointer else "N",
                     "charter_boundary_text": b})
        print(f"Ch {chap} {name}: {'pointer' if pointer else ('text' if b else 'NONE')}")
        time.sleep(0.5)

    cb = pd.DataFrame(rows)
    cb.to_csv("charter_boundaries.csv", index=False)
    print("\nWrote charter_boundaries.csv")

    # optional join onto the crosswalk
    try:
        xw = pd.read_csv(XWALK)
        def norm(s):
            s = str(s).lower().replace(".", "")
            return re.sub(r"\s+", " ", re.sub(r"\bno\s*\d+\b", "", s)).strip()
        cb["_k"] = cb["district_name"].map(norm)
        xw["_k"] = xw["district_name"].map(norm)
        merged = xw.merge(
            cb[["_k", "charter_chapter", "charter_url",
                "boundary_is_record_pointer", "charter_boundary_text"]],
            on="_k", how="left").drop(columns="_k")
        merged.to_csv("vt_district_crosswalk_charters.csv", index=False)
        print("Wrote vt_district_crosswalk_charters.csv "
              f"({merged['charter_chapter'].notna().sum()} rows got charter text)")
    except FileNotFoundError:
        print(f"({XWALK} not found -- skipped join; charter_boundaries.csv still written)")


if __name__ == "__main__":
    main()
