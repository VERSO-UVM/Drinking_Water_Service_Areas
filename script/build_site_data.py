"""
Build the web-map data for the GitHub Pages site in docs/.

Inputs:
  data/vt_water_boundaries.gpkg           (written by pull_vt_water_boundaries.py)
  data/vt_town_clerk_contacts_filled.csv  (written by merge_clerk_contacts.py;
                                           falls back to the unfilled skeleton)
  data/vt_district_crosswalk.csv          (the 80-district inventory)
  data/vt_district_websites.csv           (hand-maintained district URLs)
  VCGI "VT Data - Town Boundaries" feature service (fetched live)

Outputs (GeoJSON in EPSG:4326, simplified + coordinate-rounded for the browser):
  docs/data/water_service_areas.geojson
  docs/data/town_boundaries.geojson
  docs/data/districts.json
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
CROSSWALK = ROOT / "data" / "vt_district_crosswalk.csv"
WEBSITES = ROOT / "data" / "vt_district_websites.csv"
ROSTER = ROOT / "data" / "vt_district_roster.csv"
CHARTER_CHAPTERS = ROOT / "data" / "vt_charter_chapters.csv"
CHARTER_SECTIONS = ROOT / "data" / "vt_charter_boundary_sections.csv"
ORDINANCES = ROOT / "docs" / "data" / "ordinances.json"
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
    "verified", "confirmed_by", "district_website", "source_type",
    "source_citation", "source_url", "source_text", "derivation",
    "source_file", "source_crs", "crs_inferred",
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


# The six districts that agreed to the boundary-mapping pilot. Names must match
# data/vt_district_crosswalk.csv exactly; the build asserts that they do.
PILOT = {
    "Peacham Fire District 1",
    "Westford Fire District 1",
    "Greensboro Bend Fire District 2",
    "Danville Fire District 1",
    "Burke Fire District 1",
    "East Hardwick Fire District 1",
}


def load_websites():
    """district_name -> url, from the hand-maintained website sheet.

    The sheet is a fill-in worklist: every district gets a row, most of them
    blank. Only non-blank rows end up on the site.
    """
    if not WEBSITES.exists():
        print("  no vt_district_websites.csv -- district links will be blank")
        return {}
    df = pd.read_csv(WEBSITES, encoding="utf-8-sig").fillna("")
    return {
        str(r["district_name"]).strip(): str(r["district_website"]).strip()
        for _, r in df.iterrows()
        if str(r["district_website"]).strip()
    }


# Longest charter excerpt carried into the browser. The full text is one click
# away on the legislature's site, and St. Albans's § 2 alone runs 12,566 chars.
EXCERPT_CHARS = 1500

# ECHO is the only per-system federal report with a stable, guessable URL.
ECHO_URL = "https://echo.epa.gov/detailed-facility-report?fid={pwsid}&sys=SDWIS"
SDWIS_URL = ("https://data.epa.gov/efservice/WATER_SYSTEM/PWSID/{pwsid}/JSON")


def norm_district(name):
    """Fold the naming variants across the roster, charters and crosswalk.

    "Fairfax Fire District No. 1", "Fairfax FD 1" and "Fairfax Fire District 1"
    all have to land on the same key.
    """
    s = str(name or "").lower()
    s = re.sub(r"\[.*?\]", "", s)          # "[Repealed.]"
    s = re.sub(r"\(.*?\)", "", s)
    s = s.replace("#", "").replace(".", "")
    s = re.sub(r"\bno\s*(\d)", r"\1", s)   # "No. 1" -> "1"
    s = re.sub(r"\bcharter\b", "", s)
    s = re.sub(r"\bfd\s*(\d)", r"fire district \1", s)
    s = re.sub(r"\bfd\b", "fire district", s)
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return s


def load_charters():
    """(by_district, by_municipality) -> charter chapter dicts with sections."""
    if not CHARTER_CHAPTERS.exists() or not CHARTER_SECTIONS.exists():
        print("  no charter CSVs -- district details will omit charters")
        return {}, {}

    chapters = pd.read_csv(CHARTER_CHAPTERS, encoding="utf-8-sig", dtype=str).fillna("")
    sections = pd.read_csv(CHARTER_SECTIONS, encoding="utf-8-sig", dtype=str).fillna("")

    by_chapter = {}
    for _, r in sections.iterrows():
        by_chapter.setdefault(r["chapter"], []).append({
            "number": r["section_number"],
            "heading": r["section_heading"],
            "url": r["section_url"],
            "why": r["match_reason"],
            "excerpt": r["section_text"][:EXCERPT_CHARS],
            "truncated": len(r["section_text"]) > EXCERPT_CHARS,
        })

    by_district, by_muni = {}, {}
    for _, r in chapters.iterrows():
        entry = {
            "chapter": r["chapter"],
            "title": r["chapter_title"],
            "url": f"https://legislature.vermont.gov/statutes/chapter/24APPENDIX/{r['chapter']}",
            "sections": by_chapter.get(r["chapter"], []),
        }
        title = r["chapter_title"].lower()
        if "fire district" in title or "water district" in title or "water corporation" in title:
            by_district[norm_district(r["chapter_title"])] = entry
        else:
            by_muni.setdefault(norm_district(r["municipality"]), entry)
    return by_district, by_muni


def load_roster_permits():
    """district key -> wastewater permit fields from the VRWA workbook."""
    if not ROSTER.exists():
        return {}
    df = pd.read_csv(ROSTER, encoding="utf-8-sig", dtype=str).fillna("")
    out = {}
    for _, r in df.iterrows():
        if any(r.get(c, "") for c in ("ww_permit", "ww_npdes", "ww_treatment_type")):
            out[norm_district(r["district_name"])] = {
                "permit": r.get("ww_permit", ""),
                "npdes": r.get("ww_npdes", ""),
                "permit_type": r.get("ww_permit_type", ""),
                "treatment": r.get("ww_treatment_type", ""),
                "capacity_mgd": r.get("ww_capacity_mgd", ""),
            }
    return out


def load_website_notes():
    """district name -> the research note recorded while hunting for a URL."""
    if not WEBSITES.exists():
        return {}
    df = pd.read_csv(WEBSITES, encoding="utf-8-sig", dtype=str).fillna("")
    return {
        str(r["district_name"]).strip(): {
            "note": str(r.get("notes", "")).strip(),
            "checked_on": str(r.get("checked_on", "")).strip(),
        }
        for _, r in df.iterrows()
    }


def load_ordinances():
    """district name -> its documents, newest-looking first.

    Written by script/fetch_district_ordinances.py. Metadata only -- the full
    extracted text stays in data/vt_district_ordinance_text.json, which is a
    research corpus rather than something the page renders.
    """
    if not ORDINANCES.exists():
        print("  no ordinances.json -- run script/fetch_district_ordinances.py")
        return {}
    payload = json.loads(ORDINANCES.read_text(encoding="utf-8"))
    out = {}
    for d in payload.get("documents", []):
        out.setdefault(d["district_name"], []).append({
            "title": d.get("title", ""),
            "type": d.get("doc_type", ""),
            "url": d.get("url", ""),
            "adopted": d.get("adopted", ""),
            "pages": d.get("pages", 0),
            "chars": d.get("chars", 0),
            "status": d.get("status", ""),
            "needs_ocr": bool(d.get("needs_ocr")),
            "refs": d.get("statutory_refs", []),
            "source_page": d.get("source_page", ""),
        })
    for docs in out.values():
        docs.sort(key=lambda d: (d["type"], d["title"]))
    return out


def describe(rec):
    """A plain-language summary built only from fields we actually hold."""
    bits = []
    kind = rec["type"] or "District"
    where = f" in {rec['town']}" if rec["town"] else ""
    bits.append(f"{kind}{where}.")
    if rec["services"]:
        bits.append(f"Provides {rec['services'].lower()}.")
    if rec["population"]:
        bits.append(f"Serves about {rec['population']:,} people.")
    if rec["pwsid"]:
        bits.append(f"Public water system {rec['pwsid']}.")
    return " ".join(bits)


def attach_details(records, fire):
    """Hang a `details` block on each district for the site's Details panel.

    Every sub-block is allowed to come back empty -- the browser renders "In
    progress" for those rather than hiding the heading, so a gap reads as work
    still to do instead of as an absence of anything to find.
    """
    by_district, by_muni = load_charters()
    permits = load_roster_permits()
    notes_by_name = load_website_notes()
    ordinances = load_ordinances()

    boundary = {}
    if fire is not None:
        for _, r in fire.iterrows():
            boundary[str(r["district_name"]).strip()] = {
                "extent": str(r.get("extent", "") or ""),
                "status": str(r.get("geometry_status", "") or ""),
                "citation": str(r.get("source_citation", "") or ""),
                "url": str(r.get("source_url", "") or ""),
                "text": str(r.get("source_text", "") or "")[:EXCERPT_CHARS],
                "derivation": str(r.get("derivation", "") or ""),
                "verified": str(r.get("verified", "") or ""),
                "confirmed_by": str(r.get("confirmed_by", "") or ""),
            }

    charter_hits = permit_hits = 0
    for rec in records:
        key = norm_district(rec["name"])
        charter = by_district.get(key)
        if charter:
            charter_hits += 1

        notes = []
        wn = notes_by_name.get(rec["name"], {})
        if wn.get("note"):
            notes.append(wn["note"])
        if not rec["in_roster"]:
            notes.append("Has a boundary polygon but does not appear in the "
                         "VRWA district list or the roster workbook.")

        epa = {}
        if rec["pwsid"]:
            epa = {
                "pwsid": rec["pwsid"],
                "echo": ECHO_URL.format(pwsid=rec["pwsid"]),
                "sdwis": SDWIS_URL.format(pwsid=rec["pwsid"]),
            }
        ww = permits.get(key, {})
        if ww:
            permit_hits += 1

        rec["details"] = {
            "description": describe(rec),
            "charter": charter,
            # The town's own charter is context, not the district's authority.
            "town_charter": by_muni.get(norm_district(rec["town"])),
            "epa": epa,
            "ww": ww,
            "boundary": boundary.get(rec["name"], {}),
            "documents": ordinances.get(rec["name"], []),
            "notes": notes,
            "checked_on": wn.get("checked_on", ""),
        }

    doc_districts = sum(1 for r in records if r["details"]["documents"])
    doc_total = sum(len(r["details"]["documents"]) for r in records)
    print(f"  details: {charter_hits} with their own charter, "
          f"{permit_hits} with a wastewater permit, "
          f"{doc_total} documents across {doc_districts} districts")


def build_district_list(fire):
    """The full district roster the site lists under the map.

    Union of the 80-district crosswalk and any mapped fire-district polygon
    that the crosswalk does not know about -- Williamstown is one today, so a
    silent inner join would drop a district we have a boundary for.
    """
    print("District list:")
    if not CROSSWALK.exists():
        print("  no vt_district_crosswalk.csv -- skipping districts.json")
        return []

    xwalk = pd.read_csv(CROSSWALK, encoding="utf-8-sig").fillna("")
    websites = load_websites()

    # Mapped polygons, keyed by name, so the list can flag what is drawn and
    # let the browser zoom to it.
    mapped = {}
    if fire is not None:
        for _, r in fire.iterrows():
            mapped[str(r["district_name"]).strip()] = {
                "fd_id": str(r.get("fd_id", "")),
                "geometry_status": str(r.get("geometry_status", "")),
                "extent": str(r.get("extent", "")),
                "website": str(r.get("district_website", "") or ""),
            }

    missing_pilot = PILOT - set(xwalk["district_name"].astype(str).str.strip())
    if missing_pilot:
        print(f"  WARNING pilot names not in crosswalk: {sorted(missing_pilot)}")

    records = []
    seen = set()
    for _, r in xwalk.iterrows():
        name = str(r["district_name"]).strip()
        seen.add(name)
        geom = mapped.get(name, {})
        records.append({
            "name": name,
            "town": str(r["town"]).strip(),
            "type": str(r["district_type"]).strip(),
            "services": str(r["services"]).strip(),
            "population": num_or_none(r.get("population")),
            "pwsid": str(r.get("matched_pwsid", "")).strip(),
            # The polygon's own website field is the fallback so a link added
            # in build_fire_districts.py is never silently dropped.
            "website": websites.get(name) or geom.get("website", ""),
            "pilot": name in PILOT,
            "in_roster": True,
            "fd_id": geom.get("fd_id", ""),
            "geometry_status": geom.get("geometry_status", ""),
            "extent": geom.get("extent", ""),
        })

    for name, geom in sorted(mapped.items()):
        if name in seen:
            continue
        print(f"  NOTE mapped but absent from the crosswalk: {name}")
        row = fire[fire["district_name"] == name].iloc[0]
        records.append({
            "name": name,
            "town": str(row.get("town", "")).strip(),
            "type": "Fire District",
            "services": "Water",
            "population": num_or_none(row.get("population")),
            "pwsid": str(row.get("pwsid", "")).strip(),
            "website": websites.get(name) or geom.get("website", ""),
            "pilot": name in PILOT,
            "in_roster": False,
            "fd_id": geom.get("fd_id", ""),
            "geometry_status": geom.get("geometry_status", ""),
            "extent": geom.get("extent", ""),
        })

    attach_details(records, fire)

    records.sort(key=lambda d: (d["town"].lower(), d["name"].lower()))
    payload = {"districts": records}
    path = OUT_DIR / "districts.json"
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")

    linked = sum(1 for d in records if d["website"])
    drawn = sum(1 for d in records if d["geometry_status"] == "district")
    print(f"  {len(records)} districts in {len({d['town'] for d in records})} towns, "
          f"{linked} with a website, {drawn} with a mapped boundary")
    return records


def num_or_none(value):
    """CSV cell -> int, or None for blanks and non-numeric junk."""
    try:
        if value == "" or pd.isna(value):
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


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
    districts = build_district_list(fire)
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
        "districts": len(districts),
        "districts_with_website": sum(1 for d in districts if d["website"]),
        "clerks_with_email": sum(1 for r in clerks if r.get("clerk_email")),
        "fd_boundaries": 0 if fire is None else int(len(fire)),
        "fd_usable": 0 if fire is None else
                     int((fire["geometry_status"] == "district").sum()),
    }
    (OUT_DIR / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print("\nmeta.json:", json.dumps(meta))


if __name__ == "__main__":
    main()
