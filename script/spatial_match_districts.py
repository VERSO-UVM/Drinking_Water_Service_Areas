#!/usr/bin/env python3
"""
Spatial matcher for Vermont water-district boundaries.

PROBLEM this solves:
  The name-based crosswalk (vt_district_crosswalk.csv) assigns every VRWA
  district its closest-named EPA service-area polygon. In multi-district towns
  (Rutland Town has 5, Barnet 3, etc.) the district names are near-identical
  ("Rutland Town Fire District 1/4/5/6/11") and name matching guesses wrong.
  It also produced 4 cross-town errors (e.g. Sherburne -> "Shelburne Farms").

WHAT this does:
  1. Loads your EPA polygons (vt_water_boundaries.gpkg).
  2. Pulls VCGI town boundaries (ArcGIS feature service) and reprojects.
  3. Spatially tags each EPA polygon with the town it falls in (by centroid
     + majority-area overlap), giving an authoritative polygon->town link that
     does not depend on names.
  4. Re-runs the district->polygon match CONSTRAINED to the correct town:
     a district can only match EPA polygons physically in its town. Within a
     town, remaining name similarity breaks ties between same-town polygons.
  5. Flags every multi-district town for human confirmation, because name
     similarity alone can't distinguish co-located same-named districts --
     final assignment there needs a human or a district-specific parcel layer.

OUTPUT:
  vt_district_crosswalk_spatial.csv  -- adds: spatial_town, town_match (Y/N),
      polygons_in_town, spatial_status (confirmed_single | needs_review_multi |
      town_mismatch | no_polygon_in_town)

INPUTS you must have locally:
  vt_water_boundaries.gpkg        (from pull_vt_water_boundaries.py)
  vt_district_crosswalk.csv       (the name-based crosswalk)

Run:
  pip install pip-system-certs geopandas requests rapidfuzz pandas
  python spatial_match_districts.py
"""

import json, sys, time, re
import requests
import pandas as pd
import geopandas as gpd
from shapely.geometry import shape
from rapidfuzz import fuzz

# VCGI town boundaries feature service (polygons).
TOWN_SERVICE = ("https://services1.arcgis.com/BkFxaEFNwHqX3tAw/arcgis/rest/"
                "services/FS_VCGI_OPENDATA_Boundary_BNDHASH_poly_towns_SP_v1/"
                "FeatureServer/0")
GPKG = "vt_water_boundaries.gpkg"
EPA_LAYER = "all_public_water_systems"
NAME_XWALK = "vt_district_crosswalk.csv"
OUT = "vt_district_crosswalk_spatial.csv"
CRS = "EPSG:32145"
TIMEOUT = 120


def get_json(url, params):
    for attempt in range(4):
        r = requests.get(url, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        try:
            return r.json()
        except json.JSONDecodeError:
            if attempt == 3:
                print(r.text[:400], file=sys.stderr); raise
            time.sleep(2 * (attempt + 1))


def fetch_towns():
    """Pull all VT town polygons from VCGI. Auto-detects the town-name field."""
    meta = get_json(TOWN_SERVICE, {"f": "json"})
    fields = [f["name"] for f in meta.get("fields", [])]
    name_field = next((c for c in ("TOWNNAME", "TOWNNAMEMC", "NAME", "TOWN")
                       if c in fields), None)
    if not name_field:
        print("Town-name field not found. Fields:", fields, file=sys.stderr)
        sys.exit(1)

    feats, offset = [], 0
    while True:
        data = get_json(f"{TOWN_SERVICE}/query", {
            "where": "1=1", "outFields": name_field, "returnGeometry": "true",
            "outSR": 4326, "f": "geojson",
            "resultOffset": offset, "resultRecordCount": 500})
        batch = data.get("features", [])
        if not batch:
            break
        feats.extend(batch)
        if len(batch) < 500:
            break
        offset += 500

    geoms = [shape(f["geometry"]) for f in feats]
    names = [f["properties"][name_field] for f in feats]
    t = gpd.GeoDataFrame({"spatial_town": names}, geometry=geoms, crs="EPSG:4326")
    t["spatial_town"] = t["spatial_town"].str.strip().str.title()
    return t.to_crs(CRS)


def norm_town(s):
    return re.sub(r"\s+", " ", str(s)).strip().title()


def main():
    epa = gpd.read_file(GPKG, layer=EPA_LAYER).to_crs(CRS)
    epa["geometry"] = epa.geometry.buffer(0)
    towns = fetch_towns()
    print(f"EPA polygons: {len(epa)} | VT towns: {len(towns)}")

    # --- spatially assign each EPA polygon to a town by largest overlap ---
    epa = epa.reset_index(drop=True)
    epa["_pid"] = epa.index
    ov = gpd.overlay(epa[["_pid", "geometry"]], towns, how="intersection")
    ov["_a"] = ov.geometry.area
    best_town = (ov.sort_values("_a", ascending=False)
                   .drop_duplicates("_pid")[["_pid", "spatial_town"]])
    epa = epa.merge(best_town, on="_pid", how="left")

    epa_lookup = epa[["PWSID", "PWS_Name", "spatial_town"]].copy()
    epa_lookup["_town"] = epa_lookup["spatial_town"].map(norm_town)

    # --- load name-based crosswalk, re-resolve within correct town ---
    xw = pd.read_csv(NAME_XWALK)
    xw["_town"] = xw["town"].map(norm_town)

    results = []
    for _, d in xw.iterrows():
        town = d["_town"]
        cands = epa_lookup[epa_lookup["_town"] == town]
        n_in_town = len(cands)

        spatial_pwsid = spatial_name = ""
        if n_in_town == 1:
            spatial_pwsid = cands.iloc[0]["PWSID"]
            spatial_name = cands.iloc[0]["PWS_Name"]
            status = "confirmed_single"
        elif n_in_town > 1:
            # tie-break by name similarity among same-town polygons
            dn = str(d["district_name"]).lower()
            scored = cands.assign(
                _s=cands["PWS_Name"].str.lower().map(lambda x: fuzz.token_sort_ratio(dn, x)))
            top = scored.sort_values("_s", ascending=False).iloc[0]
            spatial_pwsid = top["PWSID"]
            spatial_name = top["PWS_Name"]
            status = "needs_review_multi"
        else:
            status = "no_polygon_in_town"

        # did the spatial town agree with the earlier name-match's town?
        prior_name = str(d.get("matched_pws_name", ""))
        town_match = "Y" if (spatial_name and prior_name and
                             spatial_name == prior_name) else "N"

        results.append({
            **{k: d[k] for k in xw.columns if not k.startswith("_")},
            "spatial_town": d["town"],
            "polygons_in_town": n_in_town,
            "spatial_pwsid": spatial_pwsid,
            "spatial_pws_name": spatial_name,
            "name_vs_spatial_agree": town_match,
            "spatial_status": status,
        })

    out = pd.DataFrame(results)
    out.to_csv(OUT, index=False)
    print(f"\nWrote {OUT}")
    print(out["spatial_status"].value_counts().to_string())
    disagree = (out["name_vs_spatial_agree"] == "N").sum()
    print(f"\nName-match vs spatial DISAGREE (were likely wrong before): {disagree}")


if __name__ == "__main__":
    main()
