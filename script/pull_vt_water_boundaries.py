#!/usr/bin/env python3
"""
Pull Vermont drinking-water SERVICE-AREA polygons from the EPA Public Water
System Service Area Boundaries feature service, filtered to VT only, then
repair, tag, and split into analysis-ready layers.

IMPORTANT -- what this is and is NOT:
  This dataset is SERVICE AREAS: the geographic extent where each public water
  system delivers water, keyed on PWSID. It is NOT the political / taxing
  boundary of a Title 24 water district or a Title 20 fire district. Those
  political boundaries are not in EPA or SDWIS and must be assembled
  separately (see the companion registry-crosswalk script).

Source:
  EPA CWS service areas (v3):
    https://services.arcgis.com/cJ9YHowT8TU7DUyn/arcgis/rest/services/Water_System_Boundaries/FeatureServer

Outputs:
  vt_water_boundaries.gpkg   (EPSG:32145) with three layers:
      - all_public_water_systems   every VT system, tagged
      - community_water_systems    residential/community subset
      - community_authoritative    community systems w/ VT-sourced (non-modeled) boundary
  vt_water_boundaries.csv    attribute table with boundary_source + is_community flags

Run:
  # WSL2 / anywhere uv is installed:
  uv run --with geopandas --with requests pull_vt_water_boundaries.py
  # managed Windows w/ plain Python:
  pip install geopandas requests
  python pull_vt_water_boundaries.py
"""

import json
import sys
import time
import requests
import geopandas as gpd
from shapely.geometry import shape

# --- config ---------------------------------------------------------------
SERVICE = (
    "https://services.arcgis.com/cJ9YHowT8TU7DUyn/arcgis/rest/services/"
    "Water_System_Boundaries/FeatureServer"
)
STATE_PREFIX = "VT"
OUT_GPKG = "vt_water_boundaries.gpkg"
OUT_CSV = "vt_water_boundaries.csv"
TARGET_CRS = "EPSG:32145"   # VT State Plane meters
PAGE_SIZE = 500
TIMEOUT = 120

# Service_Area_Type values treated as community/district-level (vs. single
# facilities like schools, hotels, mobile home parks).
COMMUNITY_TYPES = {
    "Residential Area",
    "Other Residential",
    "Homeowners Association",
    "Wholesaler of Water",
}
# --------------------------------------------------------------------------


def get_json(url, params):
    for attempt in range(4):
        r = requests.get(url, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        try:
            return r.json()
        except json.JSONDecodeError:
            if attempt == 3:
                print("Non-JSON response:\n", r.text[:500], file=sys.stderr)
                raise
            time.sleep(2 * (attempt + 1))


def find_polygon_layer():
    meta = get_json(SERVICE, {"f": "json"})
    for lyr in meta.get("layers", []):
        if lyr.get("geometryType") == "esriGeometryPolygon":
            print(f"Using layer {lyr['id']}: {lyr['name']}")
            return lyr["id"]
    raise RuntimeError("No polygon layer found in service.")


def pwsid_field(layer_url):
    meta = get_json(layer_url, {"f": "json"})
    names = [f["name"] for f in meta.get("fields", [])]
    for cand in ("PWSID", "pwsid", "PWS_ID", "pwsid_12"):
        if cand in names:
            return cand
    for n in names:
        if "pwsid" in n.lower():
            return n
    print("Fields:", ", ".join(names), file=sys.stderr)
    raise RuntimeError("Could not identify a PWSID field; inspect the list above.")


def fetch_all(layer_url, where):
    feats, offset = [], 0
    while True:
        params = {
            "where": where,
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": 4326,
            "f": "geojson",
            "resultOffset": offset,
            "resultRecordCount": PAGE_SIZE,
        }
        data = get_json(f"{layer_url}/query", params)
        batch = data.get("features", [])
        if not batch:
            break
        feats.extend(batch)
        print(f"  fetched {len(feats)} features...")
        if len(batch) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return feats


def tag_source(row):
    prov = row.get("Original_Data_Provider")
    if isinstance(prov, str) and "EPA" in prov:
        return "EPA-modeled"
    return "Authoritative (VT/local)"


def main():
    layer_id = find_polygon_layer()
    layer_url = f"{SERVICE}/{layer_id}"

    id_field = pwsid_field(layer_url)
    where = f"{id_field} LIKE '{STATE_PREFIX}%'"
    print(f"Querying: {where}")

    features = fetch_all(layer_url, where)
    if not features:
        print("No Vermont features returned. Check PWSID field / prefix.",
              file=sys.stderr)
        sys.exit(1)

    geoms = [shape(f["geometry"]) for f in features]
    records = [f["properties"] for f in features]
    gdf = gpd.GeoDataFrame(records, geometry=geoms, crs="EPSG:4326").to_crs(TARGET_CRS)
    print(f"\nTotal Vermont water systems: {len(gdf)}")

    # repair invalid geometries
    bad = ~gdf.geometry.is_valid
    if bad.any():
        gdf.loc[bad, "geometry"] = gdf.loc[bad, "geometry"].buffer(0)
        print(f"Repaired {int(bad.sum())} invalid geometries")

    # tags
    gdf["boundary_source"] = gdf.apply(tag_source, axis=1)
    gdf["is_community"] = gdf.get("Service_Area_Type").isin(COMMUNITY_TYPES)

    # write layers
    gdf.to_file(OUT_GPKG, layer="all_public_water_systems", driver="GPKG")
    community = gdf[gdf["is_community"]]
    community.to_file(OUT_GPKG, layer="community_water_systems", driver="GPKG")
    auth_comm = community[community["boundary_source"] == "Authoritative (VT/local)"]
    auth_comm.to_file(OUT_GPKG, layer="community_authoritative", driver="GPKG")

    gdf.drop(columns="geometry").to_csv(OUT_CSV, index=False)

    print(f"\nWrote {OUT_GPKG}")
    print(f"  all_public_water_systems : {len(gdf)}")
    print(f"  community_water_systems  : {len(community)}")
    print(f"  community_authoritative  : {len(auth_comm)}")
    print(f"Wrote {OUT_CSV}")


if __name__ == "__main__":
    main()
