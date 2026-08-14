"""
Build the web-map data for the GitHub Pages site in docs/.

Inputs:
  data/vt_water_boundaries.gpkg           (written by pull_vt_water_boundaries.py)
  data/vt_town_clerk_contacts_filled.csv  (written by merge_clerk_contacts.py;
                                           falls back to the unfilled skeleton)
  VCGI "VT Data - Town Boundaries" feature service (fetched live)

Outputs (GeoJSON in EPSG:4326, simplified + coordinate-rounded for the browser):
  docs/data/water_service_areas.geojson
  docs/data/town_boundaries.geojson
  docs/data/town_clerks.json
  docs/data/meta.json

Run:
  python script/build_site_data.py
"""

import json
import re
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
GPKG = ROOT / "data" / "vt_water_boundaries.gpkg"
FIRE_GPKG = ROOT / "data" / "vt_fire_districts.gpkg"
CLERKS_FILLED = ROOT / "data" / "vt_town_clerk_contacts_filled.csv"
CLERKS_SKELETON = ROOT / "data" / "vt_town_clerk_contacts.csv"
OUT_DIR = ROOT / "docs" / "data"

# Simplification tolerances in meters (data is in EPSG:32145, VT State Plane meters).
# Big enough to shrink the payload, small enough to stay honest at town zoom levels.
WATER_TOLERANCE_M = 10
TOWN_TOLERANCE_M = 20
COORD_PRECISION = 5  # ~1 m at Vermont's latitude

TOWNS_URL = (
    "https://services1.arcgis.com/BkFxaEFNwHqX3tAw/arcgis/rest/services/"
    "FS_VCGI_OPENDATA_Boundary_BNDHASH_poly_towns_SP_v1/FeatureServer/0/query"
)

# Attributes carried into the browser. Everything else is dropped to keep the file small.
WATER_FIELDS = [
    "PWSID",
    "PWS_Name",
    "Pop_Cat_5",
    "Population_Served_Count",
    "Service_Connections_Count",
    "Service_Area_Type",
    "Model_Method",
    "boundary_source",
    "is_community",
    "Area_SqKM",
    "Detailed_Facility_Report",
]
TOWN_FIELDS = ["TOWNNAMEMC", "CNTY", "FIPS6"]


def write_geojson(gdf, path, precision=COORD_PRECISION):
    path.parent.mkdir(parents=True, exist_ok=True)
    # to_json handles NaN -> null; keep_bbox off, we compute bounds ourselves.
    payload = json.loads(gdf.to_json(drop_id=True, to_wgs84=True))
    _round_coords(payload, precision)
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    kb = path.stat().st_size / 1024
    print(f"  wrote {path.relative_to(ROOT)}  ({len(gdf)} features, {kb:,.0f} KB)")


def _round_coords(obj, precision):
    """Recursively round every coordinate pair in a GeoJSON dict, in place."""
    if isinstance(obj, dict):
        if "coordinates" in obj:
            obj["coordinates"] = _round_nested(obj["coordinates"], precision)
        for v in obj.values():
            _round_coords(v, precision)
    elif isinstance(obj, list):
        for v in obj:
            _round_coords(v, precision)


def _round_nested(seq, precision):
    if seq and isinstance(seq[0], (int, float)):
        return [round(float(v), precision) for v in seq]
    return [_round_nested(s, precision) for s in seq]


def build_water_service_areas():
    print("Water service areas:")
    if not GPKG.exists():
        sys.exit(f"Missing {GPKG}. Run script/get_epa_map.py first.")

    gdf = gpd.read_file(GPKG, layer="all_public_water_systems")
    gdf["geometry"] = gdf.geometry.simplify(WATER_TOLERANCE_M, preserve_topology=True)
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]

    keep = [c for c in WATER_FIELDS if c in gdf.columns]
    gdf = gdf[keep + ["geometry"]].copy()
    gdf["is_community"] = gdf["is_community"].astype(bool)
    # Sort largest-first so small systems draw on top of the ones that contain them.
    gdf = gdf.sort_values("Area_SqKM", ascending=False)

    write_geojson(gdf, OUT_DIR / "water_service_areas.geojson")
    return gdf


def build_town_boundaries():
    print("Town boundaries (VCGI):")
    params = {
        "where": "1=1",
        "outFields": ",".join(TOWN_FIELDS),
        "returnGeometry": "true",
        "outSR": 32145,
        "f": "geojson",
    }
    r = requests.get(TOWNS_URL, params=params, timeout=180)
    r.raise_for_status()
    data = r.json()
    if "features" not in data:
        sys.exit(f"Unexpected response from VCGI towns service: {str(data)[:300]}")

    gdf = gpd.GeoDataFrame.from_features(data["features"], crs="EPSG:32145")
    print(f"  fetched {len(gdf)} towns")
    gdf["geometry"] = gdf.geometry.simplify(TOWN_TOLERANCE_M, preserve_topology=True)
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]

    keep = [c for c in TOWN_FIELDS if c in gdf.columns]
    gdf = gdf[keep + ["geometry"]].sort_values(keep[0] if keep else "geometry")

    write_geojson(gdf, OUT_DIR / "town_boundaries.geojson")
    return gdf


FIRE_FIELDS = [
    "fd_id", "district_name", "town", "county", "population", "pwsid",
    "pws_name", "area_sqkm", "town_iou", "geometry_status", "extent",
    "verified", "confirmed_by", "source_file", "source_crs", "crs_inferred",
    "clerk_name", "clerk_email", "notes",
]


def build_fire_districts():
    """Fire-district political boundaries -- the layer the project is building."""
    print("Fire district boundaries:")
    if not FIRE_GPKG.exists():
        print("  no vt_fire_districts.gpkg -- run script/build_fire_districts.py")
        return None

    gdf = gpd.read_file(FIRE_GPKG, layer="fire_districts")
    gdf["geometry"] = gdf.geometry.simplify(WATER_TOLERANCE_M, preserve_topology=True)
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]

    keep = [c for c in FIRE_FIELDS if c in gdf.columns]
    gdf = gdf[keep + ["geometry"]].sort_values("district_name")

    write_geojson(gdf, OUT_DIR / "fire_districts.geojson")
    usable = int((gdf["geometry_status"] == "district").sum())
    townwide = int((gdf["extent"] == "coextensive_with_town").sum())
    print(f"  {usable} confirmed district boundaries "
          f"({townwide} town-wide, {usable - townwide} sub-town), "
          f"{len(gdf) - usable} unconfirmed")
    return gdf


def split_name(name):
    """(base, kind) for a municipality name -- mirrors merge_clerk_contacts.py.

    Keeps the City/Town suffix as `kind` rather than discarding it, so Barre
    Town does not inherit Barre City's clerk, and folds Saint -> St so VCGI's
    "Saint Johnsbury" meets the contact sheet's "St. Johnsbury".
    """
    s = str(name).lower().strip()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\bsaint\b", "st", s)
    s = re.sub(r"\b(of|the)\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip()

    m = re.search(r"\b(city|town|village|gore)$", s)
    if m:
        return s[:m.start()].strip(), m.group(1)
    return s, ""


def map_key(name):
    """Key the browser can recompute from a VCGI town name."""
    base, kind = split_name(name)
    return f"{base}|{kind}" if kind else base


def build_town_clerks(towns):
    """Emit the clerk directory plus a lookup keyed to the town polygons."""
    print("Town clerk contacts:")
    src = CLERKS_FILLED if CLERKS_FILLED.exists() else CLERKS_SKELETON
    if not src.exists():
        print("  no clerk CSV found -- skipping")
        return []
    if src == CLERKS_SKELETON:
        print("  WARNING: using the unfilled skeleton. Run "
              "script/merge_clerk_contacts.py to populate contacts.")

    df = pd.read_csv(src, dtype=str).fillna("")
    fields = ["town", "municipality_type", "county", "town_website", "clerk_name",
              "clerk_email", "clerk_phone", "clerk_mailing_address", "source", "notes"]
    records = [{f: row.get(f, "") for f in fields if row.get(f, "")}
               for _, row in df.iterrows()]

    # Index every record by (base, kind) and by base alone.
    by_key, by_base, by_kind_of = {}, {}, {}
    for idx, (_, row) in enumerate(df.iterrows()):
        base, kind = split_name(row["town"])
        kind = kind or str(row.get("municipality_type", "")).strip().lower()
        by_key.setdefault((base, kind), idx)
        by_base.setdefault(base, []).append(idx)
        by_kind_of[idx] = kind

    # Resolve each town polygon to a record, preferring an exact kind match.
    by_town, missing = {}, []
    for name in towns["TOWNNAMEMC"]:
        base, kind = split_name(name)
        idx = by_key.get((base, kind or "town"))
        if idx is None:
            idx = by_key.get((base, ""))
        if idx is None:
            # Only fall back to a base-name match when the lone candidate does
            # not contradict the requested kind. Without this, "Rutland Town"
            # -- the five-district town at the centre of the backlog -- silently
            # picks up Rutland City's clerk.
            bucket = by_base.get(base, [])
            if len(bucket) == 1:
                cand_kind = by_kind_of[bucket[0]]
                if not kind or not cand_kind or cand_kind == kind:
                    idx = bucket[0]
        if idx is None:
            missing.append(name)
        else:
            by_town[map_key(name)] = idx

    payload = {"municipalities": records, "byTown": by_town}
    path = OUT_DIR / "town_clerks.json"
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")

    with_email = sum(1 for r in records if r.get("clerk_email"))
    print(f"  wrote {path.relative_to(ROOT)} ({len(records)} municipalities, "
          f"{with_email} with email)")
    print(f"  joins to {len(by_town)} of {len(towns)} town polygons")
    if missing:
        print(f"  no contact-sheet row for {len(missing)}: {', '.join(missing)}")
    return records


def main():
    water = build_water_service_areas()
    towns = build_town_boundaries()
    fire = build_fire_districts()
    clerks = build_town_clerks(towns)

    counts = water["boundary_source"].value_counts().to_dict()
    authoritative = int(counts.get("Authoritative (VT/local)", 0))
    meta = {
        "water_systems": int(len(water)),
        "community_systems": int(water["is_community"].sum()),
        "authoritative": authoritative,
        "authoritative_pct": round(100 * authoritative / max(len(water), 1)),
        "epa_modeled": int(counts.get("EPA-modeled", 0)),
        "population_served": int(water["Population_Served_Count"].fillna(0).sum()),
        "towns": int(len(towns)),
        "districts": 80,
        "clerks_with_email": sum(1 for r in clerks if r.get("clerk_email")),
        "fd_boundaries": 0 if fire is None else int(len(fire)),
        "fd_usable": 0 if fire is None else
                     int((fire["geometry_status"] == "district").sum()),
    }
    (OUT_DIR / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print("\nmeta.json:", json.dumps(meta))


if __name__ == "__main__":
    main()
