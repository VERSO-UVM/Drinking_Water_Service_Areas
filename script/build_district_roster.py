#!/usr/bin/env python3
"""
Build the district roster from the VRWA/DEC source workbook.

WHY THIS EXISTS:
  data/vt_district_crosswalk.csv had no committed generator -- the 80-district
  roster was extracted from the VRWA PDF by hand, so it could not be reproduced
  or refreshed. The workbook "4 - VT PWS Fire District List" is the machine-
  readable version of that same enumeration, so the roster is now derived.

WHAT THE WORKBOOK CONTAINS:
  Sheet "Water" -- 79 named water-providing districts (Type, System Name,
      System Town, Pop Served, Services).
  Sheet "WW"    -- 9 wastewater systems with far richer detail: discharge
      permit, NPDES id, treatment type and capacity, plus named operator (DO)
      and administrative (AC) contacts. Seven of these also appear on the Water
      sheet as "FD-both"; two (North Branch, Sherburne) are wastewater-only.

CONTACT HANDLING:
  The WW contacts are named individuals, several at personal addresses
  (gmail/comcast/yahoo). They are written to the roster CSV for project use but
  are deliberately NOT emitted to docs/ for the public site -- see
  build_site_data.py. Change that only as a conscious decision.

OUTPUT:
  data/vt_district_roster.csv

Run:
  python script/build_district_roster.py
"""

import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
XLSX = ROOT / "data" / "4 - VT PWS Fire District List - Updated Sept 2025 (1).xlsx"
CROSSWALK = ROOT / "data" / "vt_district_crosswalk.csv"
OUT = ROOT / "data" / "vt_district_roster.csv"

TYPE_LABEL = {
    "FD": "Fire District",
    "FD-both": "Fire District",
    "FD?": "Fire District (unconfirmed)",
    "Water Dist.": "Water District",
}


def norm(s):
    """Match keys across the workbook, the crosswalk and the WW sheet."""
    s = str(s).lower()
    s = re.sub(r"\(.*?\)", "", s)
    # Drop trailing descriptors: "Cold Brook FD 1 - Direct Discharge".
    s = re.split(r"\s+-\s+", s)[0]
    s = s.replace("#", "").replace(".", "")
    # "FD2" and "FD 2" must normalize identically.
    s = re.sub(r"\bfd\s*(\d)", r"fire district \1", s)
    s = re.sub(r"\bfd\b", "fire district", s)
    s = re.sub(r"\bdist\b", "district", s)
    s = re.sub(r"\bno\s*(\d)", r"\1", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def clean(v):
    if v is None:
        return ""
    s = str(v).replace("\xa0", " ").strip()
    return "" if s.lower() == "nan" else re.sub(r"\s+", " ", s)


def main():
    if not XLSX.exists():
        sys.exit(f"Missing {XLSX}")

    water = pd.read_excel(XLSX, sheet_name="Water", dtype=str)
    water = water[water["System Name"].notna()].copy()
    ww = pd.read_excel(XLSX, sheet_name="WW", dtype=str)

    ww_by_key = {norm(r["System"]): r for _, r in ww.iterrows()}
    ww_used = set()

    rows = []
    for _, r in water.iterrows():
        key = norm(r["System Name"])
        raw_type = clean(r["Type"])
        rec = {
            "district_name": clean(r["System Name"]),
            "town": clean(r["System Town"]),
            "district_type": TYPE_LABEL.get(raw_type, raw_type or "Unknown"),
            "source_type_code": raw_type,
            "services": clean(r["Services"]) or ("Water" if raw_type else ""),
            "population": clean(r["Pop Served"]),
            "provides_water": "Y",
            "provides_wastewater": "Y" if raw_type == "FD-both" else "N",
            "unconfirmed": "Y" if raw_type == "FD?" else "N",
        }
        w = ww_by_key.get(key)
        if w is not None:
            ww_used.add(key)
            rec.update(ww_fields(w))
        rows.append(rec)

    # Wastewater-only systems never appear on the Water sheet.
    for key, w in ww_by_key.items():
        if key in ww_used:
            continue
        rec = {
            "district_name": clean(w["System"]),
            "town": clean(w["Town"]),
            "district_type": "Fire District",
            "source_type_code": clean(w["System Type"]),
            "services": "WW",
            "population": "",
            "provides_water": "N",
            "provides_wastewater": "Y",
            "unconfirmed": "N",
        }
        rec.update(ww_fields(w))
        rows.append(rec)

    df = pd.DataFrame(rows)
    df["_k"] = df["district_name"].map(norm)

    # Carry the PWSID and charter flags already established in the crosswalk.
    if CROSSWALK.exists():
        xw = pd.read_csv(CROSSWALK, dtype=str)
        xw["_k"] = xw["district_name"].map(norm)
        carry = ["matched_pwsid", "matched_pws_name", "match_status",
                 "districts_in_town", "single_district_town",
                 "has_legal_charter", "political_bnd_proxy"]
        keep = ["_k"] + [c for c in carry if c in xw.columns]
        df = df.merge(xw[keep].drop_duplicates("_k"), on="_k", how="left")
        df["in_crosswalk"] = df["_k"].isin(set(xw["_k"])).map({True: "Y", False: "N"})
    else:
        df["in_crosswalk"] = ""

    df = df.drop(columns="_k").fillna("")
    df = df.sort_values(["town", "district_name"]).reset_index(drop=True)
    df.insert(0, "roster_id", [f"VTD-{i:03d}" for i in range(1, len(df) + 1)])
    df.to_csv(OUT, index=False)

    print(f"Wrote {OUT.relative_to(ROOT)} ({len(df)} districts)")
    print(f"  water-providing: {(df.provides_water == 'Y').sum()} | "
          f"wastewater: {(df.provides_wastewater == 'Y').sum()}")
    print(f"  with a WW permit record: {(df.ww_permit != '').sum()}")
    print(f"  with a named district contact: {(df.contact_name != '').sum()}")
    new = df[df.in_crosswalk == "N"]
    if len(new):
        print(f"\n  NOT in vt_district_crosswalk.csv ({len(new)}):")
        for _, r in new.iterrows():
            print(f"    {r.district_name} ({r.town}) pop={r.population} "
                  f"type={r.source_type_code}")

    population_check(df)


def population_check(df):
    """Cross-check workbook populations against the EPA polygon attributes.

    The workbook's Pop Served and the EPA layer's Population_Served_Count are
    independent reports of the same figure, so a disagreement means either the
    PWSID match is wrong or one side is stale. Either is worth knowing.
    """
    gpkg = ROOT / "data" / "vt_water_boundaries.gpkg"
    if not gpkg.exists():
        return
    import geopandas as gpd

    epa = gpd.read_file(gpkg, layer="all_public_water_systems")
    epa = epa[["PWSID", "PWS_Name", "Population_Served_Count"]]

    m = df[df.matched_pwsid.astype(str).str.strip() != ""].merge(
        epa, left_on="matched_pwsid", right_on="PWSID", how="left")
    m["roster_pop"] = pd.to_numeric(m["population"], errors="coerce")
    m["epa_pop"] = pd.to_numeric(m["Population_Served_Count"], errors="coerce")
    m = m[m.roster_pop.notna() & m.epa_pop.notna()].copy()
    m["difference"] = m.roster_pop - m.epa_pop

    bad = m[m.difference != 0][[
        "district_name", "town", "matched_pwsid", "matched_pws_name",
        "PWS_Name", "roster_pop", "epa_pop", "difference"]]
    print(f"\n  population cross-check: {len(m) - len(bad)}/{len(m)} agree "
          f"with the EPA layer")
    if len(bad):
        out = ROOT / "data" / "vt_district_population_check.csv"
        bad.to_csv(out, index=False)
        print(f"  {len(bad)} disagree -> {out.relative_to(ROOT)}")
        for _, r in bad.iterrows():
            print(f"    {r.district_name}: workbook={r.roster_pop:.0f} "
                  f"EPA={r.epa_pop:.0f} (EPA row is '{r.PWS_Name}')")


def ww_fields(w):
    """Wastewater permit detail plus the best available district contact."""
    name = clean(w["DO"]) or clean(w["AC"])
    title = clean(w["do title"]) if clean(w["DO"]) else clean(w["ac title"])
    email = clean(w["DO EMAIL"]) or clean(w["ac email"])
    phone = clean(w["DO PHONE"]) or clean(w["AC PHONE"])
    return {
        "ww_permit": clean(w["PERMIT"]),
        "ww_npdes": clean(w["NPDES"]),
        "ww_permit_type": clean(w["Permit Type"]),
        "ww_treatment_type": clean(w["ww treatment type"]),
        "ww_capacity_mgd": clean(w["ww capacity"]),
        "ww_ownership": clean(w["Ownership"]),
        "contact_name": name,
        "contact_title": title,
        "contact_email": email,
        "contact_phone": phone,
        "contact_source": "VT DEC / VRWA fire district workbook (Sept 2025)"
                          if (name or email) else "",
    }


if __name__ == "__main__":
    main()
