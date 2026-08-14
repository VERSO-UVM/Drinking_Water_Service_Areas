#!/usr/bin/env python3
"""
Build the fire-district political-boundary layer -- the thing the whole project
is actually trying to produce -- starting from the pilot shapefiles.

WHY THIS LAYER EXISTS SEPARATELY:
  EPA service areas say where water flows. This layer says where a district's
  legal/taxing boundary runs. They are different (caveat 1), and only this one
  answers the Bond Bank's question. Today it holds 3 pilot polygons out of 80
  districts; it is the seed, not the deliverable.

JOINING TO THE WATER DATA:
  Every row carries `pwsid`, the EPA/SDWIS public water system id, so this layer
  joins 1:1 to data/vt_water_boundaries.gpkg on PWSID and to the EPA CSV export.
  `district_name` + `town` join to data/vt_district_crosswalk.csv, and `town`
  joins to the clerk contact sheet.

CRS HANDLING:
  The pilot shapefiles arrived with no .prj (caveat 11), so the CRS is *inferred*
  by reprojecting under each candidate and keeping whichever lands the polygon on
  its own town. Rows record `source_crs` and `crs_inferred = Y` so nobody later
  mistakes a guess for a declaration.

QUALITY FLAG -- READ THIS:
  `geometry_status` distinguishes a real district boundary from a town outline
  filed under a district's name. Two of the three pilot files are the latter.
  Anything not `district` must not be used to compute area-difference metrics.

INPUTS:
  pilotData/*.shp                    (bare .shp, sidecars missing)
  data/vt_district_crosswalk.csv     (roster: PWSID, population, charter flags)
  data/vt_town_clerk_contacts_filled.csv  (optional: clerk contact per town)
  VCGI town boundaries               (fetched live, for CRS inference + QA)

OUTPUTS:
  data/vt_fire_districts.gpkg   (layer `fire_districts`, EPSG:32145)
  data/vt_fire_districts.csv    (attributes only, for review)

Run:
  python script/build_fire_districts.py
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("SHAPE_RESTORE_SHX", "YES")  # must precede the GDAL import

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parent.parent
PILOT_DIR = ROOT / "pilotData"
CROSSWALK = ROOT / "data" / "vt_district_crosswalk.csv"
CLERKS = ROOT / "data" / "vt_town_clerk_contacts_filled.csv"
OUT_GPKG = ROOT / "data" / "vt_fire_districts.gpkg"
OUT_CSV = ROOT / "data" / "vt_fire_districts.csv"
LAYER = "fire_districts"
CRS = "EPSG:32145"

TOWNS_URL = (
    "https://services1.arcgis.com/BkFxaEFNwHqX3tAw/arcgis/rest/services/"
    "FS_VCGI_OPENDATA_Boundary_BNDHASH_poly_towns_SP_v1/FeatureServer/0/query"
)

# CRSs seen in partner submissions so far. Order is preference on a tie.
CANDIDATE_CRS = [32145, 4326, 3857, 26918, 2852]

# The pilot files, and which district/town each is supposed to represent.
# `district_name` must match data/vt_district_crosswalk.csv exactly.
SOURCES = [
    {
        "file": "Danville Fire District.shp",
        "district_name": "Danville Fire District 1",
        "town": "Danville",
    },
    {
        "file": "HardwickFD.shp",
        "district_name": "East Hardwick Fire District 1",
        "town": "Hardwick",
    },
    {
        "file": "Peacham_FD1.shp",
        "district_name": "Peacham Fire District 1",
        "town": "Peacham",
    },
]

# Above this IoU against its own town, a "district" polygon is really just the
# town outline. Real village districts cover a fraction of their town.
TOWN_OUTLINE_IOU = 0.97

ATTRS = [
    "fd_id", "district_name", "town", "county", "district_type", "services",
    "population", "pwsid", "pws_name", "match_score", "match_status",
    "districts_in_town", "single_district_town", "has_legal_charter",
    "area_sqkm", "town_iou", "geometry_status", "verified",
    "boundary_source", "source_file", "source_crs", "crs_inferred",
    "clerk_name", "clerk_email", "notes",
]


def fetch_towns(names):
    """VCGI town polygons for the towns we need, unsimplified, in EPSG:32145."""
    quoted = ", ".join("'" + n.replace("'", "''") + "'" for n in sorted(set(names)))
    r = requests.get(TOWNS_URL, params={
        "where": f"TOWNNAMEMC IN ({quoted})",
        "outFields": "TOWNNAMEMC", "returnGeometry": "true",
        "outSR": 32145, "f": "geojson"}, timeout=180)
    r.raise_for_status()
    feats = r.json().get("features", [])
    if not feats:
        sys.exit("VCGI returned no towns; cannot infer CRS or run QA.")
    gdf = gpd.GeoDataFrame(
        [f["properties"] for f in feats],
        geometry=[shape(f["geometry"]) for f in feats], crs=CRS)
    gdf["geometry"] = gdf.geometry.buffer(0)
    return gdf.dissolve("TOWNNAMEMC").geometry


def infer_crs(path, town_geom):
    """Pick the CRS under which this polygon actually lands on its town.

    Returns (epsg, gdf_in_CRS, iou). Without a .prj there is nothing to read,
    so the town itself is the ground truth.
    """
    raw = gpd.read_file(path)
    best = (None, None, -1.0)
    for epsg in CANDIDATE_CRS:
        try:
            g = raw.set_crs(epsg, allow_override=True).to_crs(CRS)
            geom = g.geometry.buffer(0).union_all()
            if geom.is_empty:
                continue
            union = geom.union(town_geom).area
            iou = geom.intersection(town_geom).area / union if union else 0.0
        except Exception:
            continue
        if iou > best[2]:
            # `g` is already reprojected into CRS -- re-tagging it here would
            # transform it a second time and collapse the geometry.
            best = (epsg, g, iou)
    return best


def main():
    towns = fetch_towns([s["town"] for s in SOURCES])

    roster = pd.read_csv(CROSSWALK) if CROSSWALK.exists() else pd.DataFrame()
    clerks = (pd.read_csv(CLERKS, dtype=str).fillna("")
              if CLERKS.exists() else pd.DataFrame())

    rows, geoms = [], []
    for i, src in enumerate(SOURCES, start=1):
        path = PILOT_DIR / src["file"]
        if not path.exists():
            print(f"  MISSING {path}", file=sys.stderr)
            continue

        town_geom = towns.get(src["town"])
        if town_geom is None:
            print(f"  no VCGI town for {src['town']}", file=sys.stderr)
            continue

        epsg, gdf, iou = infer_crs(path, town_geom)
        if epsg is None:
            print(f"  could not infer a CRS for {src['file']}", file=sys.stderr)
            continue

        geom = gdf.geometry.buffer(0).union_all()
        area = geom.area / 1e6

        # A polygon that is essentially its own town is a town outline that was
        # filed under a district name -- not a district boundary.
        if iou >= TOWN_OUTLINE_IOU:
            status = "town_outline_not_district"
            note = (f"Matches the VCGI {src['town']} town boundary at "
                    f"{iou:.1%} IoU. This is the town outline, not the "
                    f"district's political boundary. Placeholder only -- "
                    f"request the real boundary before using.")
        else:
            status = "district"
            note = (f"Distinct from the town boundary "
                    f"({iou:.1%} IoU, {area:.1f} of "
                    f"{town_geom.area / 1e6:.1f} km2 town).")

        rec = {
            "fd_id": f"VTFD-{i:04d}",
            "district_name": src["district_name"],
            "town": src["town"],
            "area_sqkm": round(area, 4),
            "town_iou": round(iou, 4),
            "geometry_status": status,
            "verified": "N",
            "boundary_source": "Pilot submission (partner-supplied shapefile)",
            "source_file": f"pilotData/{src['file']}",
            "source_crs": f"EPSG:{epsg}",
            "crs_inferred": "Y",
            "notes": note,
        }

        # Roster attributes, including the PWSID that joins to the water data.
        if not roster.empty:
            m = roster[roster["district_name"] == src["district_name"]]
            if len(m):
                r = m.iloc[0]
                rec.update({
                    "district_type": r.get("district_type", ""),
                    "services": r.get("services", ""),
                    "population": r.get("population", ""),
                    "pwsid": r.get("matched_pwsid", ""),
                    "pws_name": r.get("matched_pws_name", ""),
                    "match_score": r.get("match_score", ""),
                    "match_status": r.get("match_status", ""),
                    "districts_in_town": r.get("districts_in_town", ""),
                    "single_district_town": r.get("single_district_town", ""),
                    "has_legal_charter": r.get("has_legal_charter", ""),
                })
            else:
                print(f"  no roster row for {src['district_name']}", file=sys.stderr)

        if not clerks.empty:
            c = clerks[clerks["town"].str.strip().str.lower()
                       == src["town"].strip().lower()]
            if len(c):
                rec["county"] = c.iloc[0].get("county", "")
                rec["clerk_name"] = c.iloc[0].get("clerk_name", "")
                rec["clerk_email"] = c.iloc[0].get("clerk_email", "")

        rows.append(rec)
        geoms.append(geom)
        print(f"  {src['district_name']:32} {rec['source_crs']:11} "
              f"IoU={iou:6.1%}  {status}")

    if not rows:
        sys.exit("No pilot boundaries could be read.")

    gdf = gpd.GeoDataFrame(rows, geometry=geoms, crs=CRS)
    for col in ATTRS:
        if col not in gdf.columns:
            gdf[col] = ""
    gdf = gdf[ATTRS + ["geometry"]]

    OUT_GPKG.parent.mkdir(parents=True, exist_ok=True)
    if OUT_GPKG.exists():
        OUT_GPKG.unlink()  # avoid appending a second copy of the layer
    gdf.to_file(OUT_GPKG, driver="GPKG", layer=LAYER)
    gdf.drop(columns="geometry").to_csv(OUT_CSV, index=False)

    usable = (gdf["geometry_status"] == "district").sum()
    print(f"\nWrote {OUT_GPKG.relative_to(ROOT)} (layer '{LAYER}') and "
          f"{OUT_CSV.relative_to(ROOT)}")
    print(f"{len(gdf)} pilot boundaries; {usable} usable as district geometry, "
          f"{len(gdf) - usable} town outlines needing the real boundary.")
    print(f"Coverage: {usable} of 80 districts have a political boundary.")


if __name__ == "__main__":
    main()
