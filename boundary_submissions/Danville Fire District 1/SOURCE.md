# Danville Fire District 1 — submission record

Per-folder provenance record, following the data standard's §9
(`docs/METADATA_STANDARD.md`). South Alburgh FD 2's `SOURCE.md` is the model.

## Received

- **Created by:** VERSO Program Office, through the ORCA student internship
  program, as one of the three pilot boundaries. Not supplied by the district.
- **Date:** 2025-10-20. This is when the file was first committed to this repository
  (in the old `pilotData/` folder). The date it was digitized wasn't recorded.
- **Method:** not recorded. The source the interns digitized from (plat,
  parcels, tax map, a paper map from the district, the town line) is an open
  question in `data/boundary_followup.md`.

Individual interns aren't named here: the program is credited, not the students.

## Files as received

Only the geometry arrived: no `.dbf` (attributes) and no `.prj` (coordinate
system). The `.shx` index files were added to the repository on 2026-08-14.

| File | Purpose |
| --- | --- |
| `Danville Fire District.shp` | district boundary geometry (used by `build_fire_districts.py`) |
| `Danville Fire District.shx` | shape index |
| `Danville Water Service Area.shp` | water service area geometry, drawn alongside the district boundary |
| `Danville Water Service Area.shx` | shape index |

**CRS:** none declared. `build_fire_districts.py` inferred EPSG:4326 (WGS 84) by testing
which candidate CRS lands the polygon on its own town (`crs_inferred = Y`).

**Extent:** coextensive with the Town of Danville (99.9% IoU).

## What this is not

Not verified by the district: no one with knowledge of the district's legal
records has confirmed this boundary yet (`verification_status = Not Verified`).
The legal authority for the boundary — the vote, order or charter that
established it — hasn't been identified (`legal_citation = unknown`).
