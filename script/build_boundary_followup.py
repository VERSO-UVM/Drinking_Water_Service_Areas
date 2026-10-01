#!/usr/bin/env python3
"""
Turn the gaps in the fire-district layer into a follow-up worklist: for each
district, the questions only the district, its town clerk, or the project
team can answer, and who to ask.

WHY THIS EXISTS:
  build_fire_districts.py fills every field it can from what the repo already
  holds and writes `Unknown`/`unknown` (or leaves a date blank) for the rest,
  following docs/METADATA_STANDARD.md. Those remaining gaps are not build
  errors -- they're questions for people. This script reads the layer and
  phrases each gap as a question, using the standard's Appendix A submission
  form as the wording, so the list can go out to districts and clerks as is.

  Re-run it after updating SOURCES in build_fire_districts.py: answered
  questions drop off the list.

INPUTS:
  data/vt_fire_districts.gpkg                         (layer `fire_districts`)
  data/vt_fire_districts_pending.csv                  (districts with no polygon)
  data/vt_district_crosswalk_with_contacts(VT Districts).csv  (district contacts)
  boundary_submissions/<district>/SOURCE.md           (checked for presence)

OUTPUTS:
  data/boundary_followup.md    (one section per district, ready to send)
  data/boundary_followup.csv   (one row per open question)

Run:
  python script/build_boundary_followup.py
"""

from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
FIRE_GPKG = ROOT / "data" / "vt_fire_districts.gpkg"
PENDING = ROOT / "data" / "vt_fire_districts_pending.csv"
CONTACTS = ROOT / "data" / "vt_district_crosswalk_with_contacts(VT Districts).csv"
BOUNDARY_DIR = ROOT / "boundary_submissions"
OUT_MD = ROOT / "data" / "boundary_followup.md"
OUT_CSV = ROOT / "data" / "boundary_followup.csv"

STANDARD = "docs/METADATA_STANDARD.md"

DISTRICT, CLERK, PROJECT = "District", "Town clerk", "Project team"


def blank(v):
    return str(v).strip() in ("", "nan", "None")


def unknown(v):
    return blank(v) or str(v).strip().lower() == "unknown"


def questions(r):
    """(ask, field(s), question) for every gap in one district's record."""
    q = []
    statute = r["legal_authority_type"] == "Legislative charter"
    # Boundaries the project itself drew (the ORCA pilot files): questions
    # about how the file was made go to the project team, not the district.
    ours = "VERSO" in r["original_data_provider"]
    townwide_statute = statute and r["extent"] == "coextensive_with_town"

    if unknown(r["legal_citation"]) or unknown(r["legal_authority_type"]):
        q.append((DISTRICT, "legal_authority_type; legal_citation",
                  "What legally established the district and its boundary: "
                  "a town meeting vote, a selectboard order, a legislative "
                  "charter, an ordinance? Please give the date and where the "
                  "record is kept."))

    if blank(r["recorded_document"]) and not townwide_statute:
        q.append((CLERK, "recorded_document",
                  "Is a plat, map or written description of the district "
                  "boundary recorded in the town land records? If so, the "
                  "book and page (a copy or scan is ideal)."))
    elif "not yet identified" in str(r["recorded_document"]):
        q.append((CLERK, "recorded_document",
                  f"The district's charter, {r['legal_citation']}, says the "
                  f"boundary is recorded with the town. Which book and page, "
                  f"and can we get a copy or scan?"))

    if blank(r["formation_date"]):
        q.append((DISTRICT, "formation_date",
                  "When was the district formed (the date of the vote, order "
                  "or act)?"))

    if blank(r["effective_date"]):
        q.append((DISTRICT, "effective_date; boundary_changes",
                  "Has the boundary changed since the district was formed "
                  "(annexations, detachments, mergers)? For each change: the "
                  "date, and the vote or order that made it."))

    if unknown(r["method"]) or unknown(r["method_basis"]) \
            or unknown(r["original_data_provider"]) or blank(r["date_created"]):
        fields = ("original_data_provider; method; method_basis; "
                  "source_date; date_created")
        if ours:
            q.append((PROJECT, fields,
                      "Check the ORCA internship records for what the "
                      "interns digitized this boundary from (a recorded plat, "
                      "tax parcels, a paper map from the district, the town "
                      "line), how, and when."))
        else:
            sent = (f"the boundary file {r['submitted_by'].split(',')[0]} "
                    f"sent us" if not blank(r["submitted_by"])
                    else "the boundary file you sent")
            q.append((DISTRICT, fields,
                      f"Who drew {sent}, roughly when, and from what (a "
                      f"recorded plat, tax parcels, a paper map, a written "
                      f"description, the town line)?"))

    if r["verification_status"] != "Verified":
        who = CLERK if statute else DISTRICT
        q.append((who, "verification_status; verification_date; "
                       "verification_process; verifier_type; verifier_name",
                  "Please look over the attached map of the boundary and "
                  "confirm it matches the district's records, or mark what's "
                  "wrong. Who reviewed it (name and role), and on what date?"))

    if r["crs_inferred"] == "Y" and ours:
        q.append((PROJECT, "source_crs",
                  "Look for the interns' original project files (with the "
                  ".prj and .dbf) in the VERSO / ORCA records; the copy in "
                  "this repository has no coordinate system or attributes."))
    elif r["crs_inferred"] == "Y":
        q.append((DISTRICT, "source_crs",
                  "If you still have the original GIS file, please resend it "
                  "as a complete zipped shapefile (.shp, .shx, .dbf, .prj) or "
                  "a GeoPackage. The copy we have has no coordinate system or "
                  "attributes."))

    if blank(r["pwsid"]) and "Water" in str(r["services"]):
        q.append((DISTRICT, "pwsid",
                  "What is the district's public water system ID (PWSID, "
                  "e.g. VT0005037)? It isn't matched in our records."))

    if blank(r["submitted_by"]) or blank(r["submission_date"]):
        q.append((PROJECT, "submitted_by; submission_date",
                  "Record who sent this file and when (check the original "
                  "email)."))

    if r["source_document"].startswith("boundary_submissions/"):
        folder = BOUNDARY_DIR / Path(r["source_document"]).relative_to(
            "boundary_submissions").parts[0]
        if not (folder / "SOURCE.md").exists():
            q.append((PROJECT, "SOURCE.md",
                      f"Write boundary_submissions/{folder.name}/SOURCE.md "
                      f"(copy South Alburgh's)."))
    return q


def load_contacts():
    if not CONTACTS.exists():
        return {}
    c = pd.read_csv(CONTACTS, dtype=str).fillna("")
    return {r["District Name"].strip(): r["Contact Info"].strip()
            for _, r in c.iterrows()}


def main():
    fire = gpd.read_file(FIRE_GPKG, layer="fire_districts").fillna("")
    contacts = load_contacts()

    rows, sections = [], []
    for _, r in fire.sort_values("name").iterrows():
        qs = questions(r)
        for ask, field, text in qs:
            rows.append({"boundary_id": r["boundary_id"], "name": r["name"],
                         "towns": r["towns"], "ask": ask, "fields": field,
                         "question": text})

        lines = [f"## {r['name']} ({r['towns']})", ""]
        lines.append(f"- **District contact:** {contacts.get(r['name']) or 'none on file'}")
        if r["district_website"]:
            lines.append(f"- **Website:** {r['district_website']}")
        if r["clerk_email"]:
            lines.append(f"- **Town clerk:** {r['clerk_name']} <{r['clerk_email']}>")
        lines.append(f"- **What we have:** {r['extent'].replace('_', ' ')}, "
                     f"{r['area_sqkm']:.2f} km²; legal authority: "
                     f"{r['legal_citation']}; {r['verification_status']}.")
        lines.append("")
        for who in (DISTRICT, CLERK, PROJECT):
            mine = [t for a, _, t in qs if a == who]
            if mine:
                lines.append(f"**Ask the {who.lower()}:**")
                lines.append("")
                lines += [f"{i}. {t}" for i, t in enumerate(mine, start=1)]
                lines.append("")
        sections.append("\n".join(lines))

    if PENDING.exists():
        for _, p in pd.read_csv(PENDING, dtype=str).fillna("").iterrows():
            text = ("Please send the district boundary as a GIS file "
                    "(GeoPackage, or a complete zipped shapefile) or a "
                    "georeferenced PDF. The map on the website is an image "
                    "only and can't be used without guessing coordinates.")
            rows.append({"boundary_id": "", "name": p["district_name"],
                         "towns": p["town"], "ask": DISTRICT,
                         "fields": "geometry", "question": text})
            sections.append("\n".join([
                f"## {p['district_name']} ({p['town']}) — no boundary yet", "",
                f"- **District contact:** {contacts.get(p['district_name']) or 'none on file'}",
                f"- **Website:** {p['district_website']}", "",
                "**Ask the district:**", "", f"1. {text}", ""]))

    pd.DataFrame(rows).to_csv(OUT_CSV, index=False)

    counts = pd.DataFrame(rows)["ask"].value_counts()
    header = [
        "# District boundary follow-up",
        "",
        "Generated by `script/build_boundary_followup.py` from "
        "`data/vt_fire_districts.gpkg`. Do not edit by hand: answer a "
        "question by updating `SOURCES` in `script/build_fire_districts.py`, "
        "then re-run both scripts, and it drops off this list.",
        "",
        f"Each question fills a field in the [data standard](../{STANDARD}). "
        f"{len(rows)} open questions: "
        + ", ".join(f"{n} for the {k.lower()}" for k, n in counts.items())
        + ".",
        "",
        "Send each district its own section together with a map of its "
        "boundary. The standard's Appendix A form covers the same questions "
        "for districts that prefer to fill in a form.",
        "",
    ]
    OUT_MD.write_text("\n".join(header) + "\n" + "\n".join(sections),
                      encoding="utf-8")
    print(f"Wrote {OUT_MD.relative_to(ROOT)} and {OUT_CSV.relative_to(ROOT)}: "
          f"{len(rows)} questions across {len(sections)} districts")
    for k, n in counts.items():
        print(f"  {k}: {n}")


if __name__ == "__main__":
    main()
