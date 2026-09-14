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
  mistakes a guess for a declaration. When a submission DOES carry a real .prj
  (South Alburgh FD 2 is the first), that declared CRS is trusted directly --
  `crs_inferred = N` -- and only checked against the town for QA, not guessed.

EXTENT, NOT QUALITY:
  `extent` records whether a district's boundary is coextensive with its town or
  covers only part of it. Danville and East Hardwick are town-wide -- confirmed
  by the project lead -- so their boundary legitimately equals the town outline.
  That is a real finding, not a data error: for those districts the political
  boundary matches the town, and the area difference against the town is zero
  while the difference against the *water service area* stays large.

INPUTS:
  boundary_submissions/<district_name>/*.shp  (one folder per partner
                                        submission; pilot files arrived as a
                                        bare .shp with sidecars missing, later
                                        submissions like South Alburgh FD 2
                                        arrive as a full shapefile set with a
                                        real .prj)
  boundary_submissions/<district_name>/SOURCE.md  (optional: who sent the
                                        submission, when, and how -- see
                                        South Alburgh FD 2's for the pattern.
                                        Not required by this script; it's
                                        human provenance, not an input the
                                        build reads. `submitted_by` /
                                        `submission_date` in SOURCES below
                                        are the machine-readable echo of it,
                                        shown on the map.)
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
from shapely.geometry import LineString, MultiLineString, Polygon, box, shape
from shapely.ops import polygonize, unary_union

ROOT = Path(__file__).resolve().parent.parent
BOUNDARY_DIR = ROOT / "boundary_submissions"
CROSSWALK = ROOT / "data" / "vt_district_crosswalk.csv"
CLERKS = ROOT / "data" / "vt_town_clerk_contacts_filled.csv"
OUT_GPKG = ROOT / "data" / "vt_fire_districts.gpkg"
OUT_CSV = ROOT / "data" / "vt_fire_districts.csv"
OUT_PENDING = ROOT / "data" / "vt_fire_districts_pending.csv"
LAYER = "fire_districts"
CRS = "EPSG:32145"

TOWNS_URL = (
    "https://services1.arcgis.com/BkFxaEFNwHqX3tAw/arcgis/rest/services/"
    "FS_VCGI_OPENDATA_Boundary_BNDHASH_poly_towns_SP_v1/FeatureServer/0/query"
)

# CRSs seen in partner submissions so far. Order is preference on a tie.
CANDIDATE_CRS = [32145, 4326, 3857, 26918, 2852]

# VT E911 road centerlines, used to build statute road-bounded extents.
ROADS_URL = (
    "https://services1.arcgis.com/BkFxaEFNwHqX3tAw/arcgis/rest/services/"
    "FS_VCGI_OPENDATA_Emergency_RDS_line_SP_v1/FeatureServer/0/query"
)

# Every district records WHERE its polygon came from and WHY, so any boundary
# here can be defended: `source_citation` + `source_url` + the verbatim
# `source_text` that justified it, plus `derivation` for how it was built.
#
# `kind` selects the geometry builder:
#   shapefile   -- partner-supplied .shp from boundary_submissions/
#   town_polygon-- statute says the district equals its town; copy VCGI town
#   road_bounded-- statute names bounding roads; hull of those centerlines
#
# `district_name` must match data/vt_district_crosswalk.csv exactly.
SOURCES = [
    {
        "kind": "shapefile",
        "file": "Danville Fire District 1/Danville Fire District.shp",
        "district_name": "Danville Fire District 1",
        "town": "Danville",
        "source_type": "Partner-supplied shapefile",
        "source_citation": "Danville Fire District, pilot submission",
        "source_url": "",
        "source_text": "",
        "derivation": "Partner shapefile; CRS inferred (no .prj supplied).",
        "district_website": "",
    },
    {
        "kind": "shapefile",
        "file": "East Hardwick Fire District 1/HardwickFD.shp",
        "district_name": "East Hardwick Fire District 1",
        "town": "Hardwick",
        "source_type": "Partner-supplied shapefile",
        "source_citation": "East Hardwick Fire District 1, pilot submission",
        "source_url": "https://ehfd.mystrikingly.com/",
        "source_text": "",
        "derivation": "Partner shapefile; CRS inferred (no .prj supplied).",
        "district_website": "https://ehfd.mystrikingly.com/",
    },
    {
        "kind": "shapefile",
        "file": "Peacham Fire District 1/Peacham_FD1.shp",
        "district_name": "Peacham Fire District 1",
        "town": "Peacham",
        "source_type": "Partner-supplied shapefile",
        "source_citation": "Peacham Fire District 1, pilot submission",
        "source_url": "https://peacham.org/peacham-fire-district/",
        "source_text": "",
        "derivation": "Partner shapefile; CRS inferred (no .prj supplied).",
        "district_website": "https://peacham.org/peacham-fire-district/",
    },
    {
        "kind": "shapefile",
        "file": "South Alburgh Fire District 2/SAFD2 Boundary.shp",
        "district_name": "South Alburgh Fire District 2",
        "town": "Alburgh",
        "source_type": "Partner-supplied shapefile",
        "source_citation": "South Alburgh Fire District No. 2, "
                           "partner-supplied boundary shapefile.",
        "source_url": "",
        "source_text": "",
        "derivation": "Partner shapefile; CRS supplied via .prj "
                      "(NAD83 / Vermont (ftUS), EPSG:5646) -- not inferred.",
        "district_website": "http://www.safd2.org/",
        # Who sent this and when -- distinct from `source_citation` (what
        # authorizes the polygon) so a submission can be traced even when
        # there's no statute or citable document behind it, and so future
        # submissions have a field to fill without overloading citation
        # prose. See boundary_submissions/<district>/SOURCE.md for the
        # full email.
        "submitted_by": "John Kiernan, RCAP Solutions "
                        "(jkiernan@rcapsolutions.org)",
        "submission_date": "2026-09-11",
    },
    {
        "kind": "town_polygon",
        "district_name": "Williamstown Fire District",
        "town": "Williamstown",
        "source_type": "Statute — district declared coextensive with its town",
        "source_citation": "24 V.S.A. App. ch. 505, § 2 "
                           "(Williamstown Fire District Charter)",
        "source_url": "https://legislature.vermont.gov/statutes/section/"
                      "24APPENDIX/505/00002",
        "source_text": "(a) The legal voters of the District shall be a body "
                       "corporate. The corporate limits shall be the boundary "
                       "lines of the Town of Williamstown, being bounded as "
                       "follows: easterly by the line of Washington; southerly "
                       "by the lines of Chelsea and Brookfield; westerly by "
                       "the lines of Northfield and Berlin; and northerly by "
                       "the lines of Berlin and Barre.",
        "derivation": "Statute defines the corporate limits as the Town of "
                      "Williamstown's boundary lines, so the VCGI town polygon "
                      "IS the district boundary. Copied unmodified.",
        "district_website": "",
    },
    {
        "kind": "road_bounded",
        "district_name": "Fairfax Fire District 1",
        "town": "Fairfax",
        "roads": ["BESSETTE RD", "HIGHLAND RD", "BRICK CHURCH RD"],
        "route_numbers": ["104"],
        "source_type": "Statute — bounding roads named (approximate extent)",
        "source_citation": "24 V.S.A. App. ch. 511, § 2 "
                           "(Fairfax Fire District No. 1)",
        "source_url": "https://legislature.vermont.gov/statutes/section/"
                      "24APPENDIX/511/00002",
        "source_text": "The boundaries of Fairfax Fire District No. 1, as "
                       "recorded with the Town of Fairfax, are bounded on the "
                       "north by Bessette Road, the west by Highland Road, the "
                       "south by Brick Church Road, and the east by VT Route "
                       "104.",
        "derivation": "Convex hull of the four named VT E911 road centerlines "
                      "within Fairfax. APPROXIMATE: the four roads do not form "
                      "a closed ring (gaps of 163-1072 m), so the hull is a "
                      "bounding estimate, not the recorded boundary. The "
                      "statute itself defers to the plat 'recorded with the "
                      "Town of Fairfax' -- obtain that for the true geometry.",
        "district_website": "",
    },
]

# Districts whose boundary is known but has no usable digital source yet.
# Tracked here so they are visible in the CSV rather than silently absent.
PENDING = [
    {
        "district_name": "North Branch Fire District 1",
        "town": "Dover",
        "district_website": "https://www.northbranchfiredistrict.com/",
        "source_type": "District website — raster map only",
        "source_citation": "North Branch Fire District, district map "
                           "(web page image)",
        "source_url": "https://www.northbranchfiredistrict.com/",
        "note": "The district publishes a boundary map, but as a raster image "
                "on a Wix page -- no GeoJSON/KML/ArcGIS layer, and the site's "
                "10 PDFs are ordinances and minutes, not georeferenced maps. "
                "Tracing pixels would fabricate coordinates. Request the "
                "source GIS file or a georeferenced PDF from the district. "
                "Note 24 V.S.A. App. ch. 509, § 1 is circular ('within the "
                "corporate limits presently established') and gives no "
                "geometry.",
    },
]

# At or above this IoU against its own town, the district is coextensive with
# the town rather than a village-scale district inside it.
TOWNWIDE_IOU = 0.97

# Districts confirmed town-wide by the project lead. Without this, a boundary
# that equals its town looks like a mis-filed town outline; these are the cases
# where it is genuinely the district's extent.
TOWNWIDE_CONFIRMED = {
    "Danville Fire District 1": "Project lead, 2026-08-14",
    "East Hardwick Fire District 1": "Project lead, 2026-08-14",
}

ATTRS = [
    "fd_id", "district_name", "town", "county", "district_type", "services",
    "population", "pwsid", "pws_name", "match_score", "match_status",
    "districts_in_town", "single_district_town", "has_legal_charter",
    "area_sqkm", "town_iou", "geometry_status", "extent", "verified",
    "confirmed_by", "district_website",
    # Provenance: why this polygon exists and what authorizes it.
    "source_type", "source_citation", "source_url", "source_text",
    "derivation", "source_file", "source_crs", "crs_inferred",
    "submitted_by", "submission_date",
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


def close_rings_to_polygons(geom):
    """Some partner exports draw a district as a closed boundary LINE rather
    than a filled polygon (South Alburgh FD 2 is the first). `buffer(0)` on
    a LineString silently collapses to an empty geometry, not an error, so
    this has to be caught before that -- convert any closed ring to the
    polygon it encloses; pass real polygons through unchanged.
    """
    if isinstance(geom, LineString) and geom.is_ring:
        return Polygon(geom.coords)
    if isinstance(geom, MultiLineString):
        rings = [Polygon(g.coords) for g in geom.geoms if g.is_ring]
        if rings:
            return unary_union(rings)
    return geom


def infer_crs(path, town_geom):
    """Pick the CRS under which this polygon actually lands on its town.

    Returns (epsg, gdf_in_CRS, iou, declared). Without a .prj there is
    nothing to read, so the town itself is the ground truth and `declared`
    is False. When the shapefile DOES carry a real .prj, that declared CRS
    is trusted directly rather than guessed -- `declared` is True -- and the
    town IoU is computed only as a QA check, not to pick among candidates.
    """
    raw = gpd.read_file(path)
    raw["geometry"] = raw.geometry.apply(close_rings_to_polygons)
    if raw.crs is not None:
        epsg = raw.crs.to_epsg(min_confidence=20)
        if epsg is not None:
            g = raw.to_crs(CRS)
            geom = g.geometry.buffer(0).union_all()
            union = geom.union(town_geom).area
            iou = geom.intersection(town_geom).area / union if union else 0.0
            return epsg, g, iou, True

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
    return best + (False,)


def fetch_roads(where):
    r = requests.get(ROADS_URL, params={
        "where": where, "outFields": "PRIMARYNAME", "returnGeometry": "true",
        "outSR": 32145, "f": "geojson", "resultRecordCount": 2000}, timeout=180)
    r.raise_for_status()
    return [shape(f["geometry"]) for f in r.json().get("features", [])]


def road_bounded_extent(src):
    """Convex hull of the statute's named roads, within the district's town.

    The named roads rarely close a ring, so this is an APPROXIMATE extent --
    a bounding estimate a digitizer can start from, not the recorded boundary.
    Returns (geometry, note) or (None, reason).
    """
    town = src["town"].upper().replace("'", "''")
    town_filter = f"(LTWN='{town}' OR RTWN='{town}')"

    names = ", ".join("'" + n.replace("'", "''") + "'" for n in src["roads"])
    named = fetch_roads(f"{town_filter} AND PRIMARYNAME IN ({names})")
    if not named:
        return None, "none of the named roads were found in the town"
    named_u = unary_union(named)

    # Clip numbered routes to the named roads' neighbourhood; VT-104 runs 28 km
    # across the county and would otherwise dominate the hull.
    minx, miny, maxx, maxy = named_u.bounds
    clip = box(minx - 400, miny - 400, maxx + 400, maxy + 400)
    routes = []
    for num in src.get("route_numbers", []):
        routes += [g.intersection(clip)
                   for g in fetch_roads(f"{town_filter} AND RTNUMBER='{num}'")
                   if g.intersects(clip)]

    network = unary_union([named_u] + routes)
    faces = list(polygonize(network))
    if faces:
        geom = max(faces, key=lambda f: f.area)
        return geom, "roads closed a ring; enclosed face used"

    gaps = []
    for i, a in enumerate(named):
        for b in named[i + 1:]:
            gaps.append(a.distance(b))
    worst = max(gaps) if gaps else 0
    return network.convex_hull, (
        f"roads do not close (largest gap {worst:.0f} m); convex hull used "
        f"as an approximate extent")


def main():
    towns = fetch_towns([s["town"] for s in SOURCES])

    roster = pd.read_csv(CROSSWALK) if CROSSWALK.exists() else pd.DataFrame()
    clerks = (pd.read_csv(CLERKS, dtype=str).fillna("")
              if CLERKS.exists() else pd.DataFrame())

    rows, geoms = [], []
    for i, src in enumerate(SOURCES, start=1):
        kind = src.get("kind", "shapefile")
        town_geom = towns.get(src["town"])
        if town_geom is None:
            print(f"  no VCGI town for {src['town']}", file=sys.stderr)
            continue

        epsg, source_file, crs_inferred = "", "", ""
        build_note = ""

        if kind == "shapefile":
            path = BOUNDARY_DIR / src["file"]
            if not path.exists():
                print(f"  MISSING {path}", file=sys.stderr)
                continue
            epsg_num, gdf, _iou, declared = infer_crs(path, town_geom)
            if epsg_num is None:
                print(f"  could not infer a CRS for {src['file']}",
                      file=sys.stderr)
                continue
            geom = gdf.geometry.buffer(0).union_all()
            epsg = f"EPSG:{epsg_num}"
            source_file = f"boundary_submissions/{src['file']}"
            crs_inferred = "N" if declared else "Y"

        elif kind == "town_polygon":
            # Statute declares the district coextensive with its town, so the
            # town polygon is the boundary -- copied, not approximated.
            geom = town_geom
            epsg = "EPSG:32145"
            source_file = "VCGI VT Data - Town Boundaries"
            crs_inferred = "N"
            build_note = "VCGI town polygon copied unmodified per statute."

        elif kind == "road_bounded":
            geom, build_note = road_bounded_extent(src)
            if geom is None:
                print(f"  {src['district_name']}: {build_note}", file=sys.stderr)
                continue
            epsg = "EPSG:32145"
            source_file = "VT E911 Road Centerlines (VCGI)"
            crs_inferred = "N"

        else:
            print(f"  unknown source kind {kind!r}", file=sys.stderr)
            continue

        geom = geom.buffer(0)
        area = geom.area / 1e6
        union = geom.union(town_geom).area
        iou = geom.intersection(town_geom).area / union if union else 0.0

        # A boundary equal to its town is a town-wide district, provided someone
        # has confirmed that is really the district's extent.
        confirmed = TOWNWIDE_CONFIRMED.get(src["district_name"], "")
        if kind == "road_bounded":
            # Statute names bounding roads but defers to a recorded plat; the
            # hull is a starting estimate, never a verified boundary.
            extent = "approximate_from_statute"
            status, verified = "approximate", "N"
            note = (f"Approximate extent from the roads named in statute. "
                    f"{build_note}. {area:.2f} km2, "
                    f"{iou:.1%} of the Town of {src['town']}.")
        elif kind == "town_polygon":
            extent = "coextensive_with_town"
            status, verified = "district", "Y"
            confirmed = confirmed or src["source_citation"]
            note = (f"Statute defines the district's corporate limits as the "
                    f"Town of {src['town']}'s boundary lines. {build_note} "
                    f"Area difference against the town is zero by definition; "
                    f"compare against the water service area instead.")
        elif iou >= TOWNWIDE_IOU:
            extent = "coextensive_with_town"
            if confirmed:
                status, verified = "district", "Y"
                note = (f"District is coextensive with the Town of "
                        f"{src['town']} ({iou:.1%} IoU). Confirmed town-wide, "
                        f"so area difference against the town is ~0 by "
                        f"definition; compare against the water service area "
                        f"instead.")
            else:
                status, verified = "unconfirmed_townwide", "N"
                note = (f"Equals the VCGI {src['town']} town boundary "
                        f"({iou:.1%} IoU). Either a town-wide district or a "
                        f"town outline filed under a district name -- confirm "
                        f"with the district before use.")
        else:
            extent = "sub_town"
            status, verified = "district", "Y" if confirmed else "N"
            note = (f"Covers part of the Town of {src['town']} "
                    f"({iou:.1%} IoU, {area:.1f} of "
                    f"{town_geom.area / 1e6:.1f} km2 town).")

        rec = {
            "fd_id": f"VTFD-{i:04d}",
            "district_name": src["district_name"],
            "town": src["town"],
            "area_sqkm": round(area, 4),
            "town_iou": round(iou, 4),
            "geometry_status": status,
            "extent": extent,
            "verified": verified,
            "confirmed_by": confirmed,
            "district_website": src.get("district_website", ""),
            "source_type": src.get("source_type", ""),
            "source_citation": src.get("source_citation", ""),
            "source_url": src.get("source_url", ""),
            "source_text": src.get("source_text", ""),
            "derivation": src.get("derivation", ""),
            "source_file": source_file,
            "source_crs": epsg,
            "crs_inferred": crs_inferred,
            "submitted_by": src.get("submitted_by", ""),
            "submission_date": src.get("submission_date", ""),
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
                # The VRWA roster is water-system-scoped, so a chartered
                # district that provides no water is simply absent from it.
                rec["notes"] = (rec.get("notes", "") + " Not in the VRWA "
                                "80-district roster: that roster lists "
                                "water-providing districts, and this district "
                                "has no public water system in SDWIS.").strip()
                print(f"  no roster row for {src['district_name']} "
                      f"(not a water provider)", file=sys.stderr)

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
              f"IoU={iou:6.1%}  {extent:22} {status}")

    if not rows:
        sys.exit("No boundaries could be built.")

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

    # Districts with a known boundary but no usable digital source yet.
    if PENDING:
        pend = pd.DataFrame([{
            "district_name": p["district_name"], "town": p["town"],
            "district_website": p.get("district_website", ""),
            "source_type": p.get("source_type", ""),
            "source_citation": p.get("source_citation", ""),
            "source_url": p.get("source_url", ""),
            "notes": p.get("note", ""),
        } for p in PENDING])
        pend.to_csv(OUT_PENDING, index=False)
        print(f"\n{len(pend)} pending (boundary known, no digital source): "
              f"{', '.join(pend['district_name'])}")
        print(f"  -> {OUT_PENDING.relative_to(ROOT)}")

    usable = int((gdf["geometry_status"] == "district").sum())
    townwide = int((gdf["extent"] == "coextensive_with_town").sum())
    approx = int((gdf["geometry_status"] == "approximate").sum())
    print(f"\nWrote {OUT_GPKG.relative_to(ROOT)} (layer '{LAYER}') and "
          f"{OUT_CSV.relative_to(ROOT)}")
    print(f"{len(gdf)} boundaries: {usable} confirmed "
          f"({townwide} town-wide, {usable - townwide} sub-town), "
          f"{approx} approximate, {len(gdf) - usable - approx} unconfirmed.")
    print(f"Coverage: {usable} of 80 districts have a confirmed political "
          f"boundary ({usable + approx} have some geometry).")


if __name__ == "__main__":
    main()
