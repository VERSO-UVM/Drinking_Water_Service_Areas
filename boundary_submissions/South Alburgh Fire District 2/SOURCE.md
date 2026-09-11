# South Alburgh Fire District 2 — submission record

This is a per-folder provenance note, not yet a repo-wide standard (see
`README.md` under `boundary_submissions/`). It exists so a submission can be
traced back to who sent it, when, and in what form, independent of the
`source_citation`/`derivation` fields carried in `vt_fire_districts.gpkg`,
which describe what *authorizes* the polygon rather than who *sent* it.

## Received

- **Date:** 2026-09-11
- **From:** John Kiernan, VT State Manager, Community & Environmental
  Resources, RCAP Solutions, Inc.
  1145 Route 74E, Shoreham, VT 05770
  <jkiernan@rcapsolutions.org> · cell 802-377-5938 · <https://www.rcapsolutions.org>
- **To:** Kendall Fortney
- **Method:** Email attachment (a zipped shapefile)

## Email text (verbatim)

> Kendall,
>
> Here is a shapefile of the boundary of the South Alburgh Fire District No. 2
> for you to add to the VBB/RPC map project. Let me know if this works for
> you.
> If I come across others, I'll send them your way.
>
> Best,
> John

## Files as received

The zip contained a full shapefile set — the first partner submission to
include one (the pilot shapefiles arrived as a bare `.shp`/`.shx` with no
`.dbf` or `.prj`):

| File | Purpose |
| --- | --- |
| `SAFD2 Boundary.shp` | geometry |
| `SAFD2 Boundary.shx` | shape index |
| `SAFD2 Boundary.dbf` | attribute table — present but empty (no fields, no attribute data; the boundary carries no district name, id, or other metadata of its own) |
| `SAFD2 Boundary.prj` | CRS: NAD83 / Vermont (ftUS), EPSG:5646 |
| `SAFD2 Boundary.sbn` / `.sbx` | spatial index (ESRI) |
| `SAFD2 Boundary.idx` | attribute index (ESRI) |

**Geometry note:** the shapefile stores the boundary as a single closed
**LineString** (a ring), not a filled Polygon. `script/build_fire_districts.py`
converts closed rings to polygons before use (`close_rings_to_polygons`) —
see that script for why this matters (`buffer(0)` silently empties a
LineString rather than erroring).

## What this is not

No attribute data, no district name/ID field, no accompanying map, ordinance,
or contact sheet — just the one boundary geometry. If further districts come
from John Kiernan ("if I come across others, I'll send them your way"), reuse
this file's shape for the next one rather than inventing a new format each
time.
