# Fire District and Drinking Water Service Area Analysis

## Project Overview

The geographic area served by a drinking water system often does not align perfectly with the political boundaries of fire districts or municipalities. Currently, the extent of properties within water districts that are **not served** by fire districts is not fully known.

This project aims to address this gap by conducting a **pilot mapping project**. Specifically, we will reach out to select fire districts to map their current political boundaries and compare them to drinking water service areas. Service areas are defined by property parcels that intersect drinking water lines, as visualized in this [ANR map](https://www.arcgis.com/apps/dashboards/978310184fd2420bb682b26c8a32afab).

> **Read first:** [`District_Boundary_Data_Caveats.docx`](District_Boundary_Data_Caveats.docx) consolidates every known limitation in this dataset, and is published as a web page at [`docs/caveats.html`](docs/caveats.html). The headline: **the political boundaries this project set out to deliver do not exist as a statewide dataset anywhere.** Everything assembled so far is either a service boundary (where water flows) or an enumeration (which districts exist). Both are useful inputs; neither is the political boundary.

## Current Status: Inventory, Not Boundaries

The fire-district boundary layer now exists as [`data/vt_fire_districts.gpkg`](data/vt_fire_districts.gpkg) — see [`build_fire_districts.py`](#build_fire_districtspy). It holds **4 confirmed boundaries plus 1 approximate extent**, so the framing below still stands: the near-term deliverable is the inventory, and this layer is the container that inventory is gradually filled into.

The first deliverable is **a coverage map of the problem, not the boundaries themselves**. Before anyone can quote a digitizing estimate, we need to know how many districts exist, which already have a service-area polygon to start from, and which need boundary work from scratch. That inventory now exists in [`data/vt_district_crosswalk.csv`](data/vt_district_crosswalk.csv).

### The district roster: 80 districts

Compiled from the Vermont Rural Water Association's September 2025 *Fire Districts and Special Use Districts* enumeration ([`data/1- VRWA - Fire Districts and Special Use Districts - 2025 update.pdf`](data/)), crosswalked against the EPA service-area data.

| Breakdown | Count |
| --- | --- |
| Fire Districts | 73 |
| Water Districts | 7 |
| **Total** | **80** |

By service provided: 71 water-only, 7 water & wastewater, 2 wastewater-only.
Population served per district ranges from **29 to 8,300** — that column survived PDF extraction intact and matches the source document's own stated range, so it is reliable for prioritizing by size.

### Where the work actually is

This is the finding that should drive scoping:

- **46 districts are the only district in their town.** For these, the service-area-as-proxy is defensible — district political boundary ≈ EPA service area ≈ town settlement. These are close to done, and are tagged `political_bnd_proxy = service_area_proxy`.
- **34 districts sit in one of 15 multi-district towns.** These **cannot be proxied**, because several districts carve up a single town. This is the actual digitizing backlog — roughly 34 districts, not 200.

Multi-district towns: Rutland Town (5), Barnet (3), and two each in Alburgh, Canaan, Castleton, Dorset, Fairfield, Grand Isle, Greensboro, Lunenburg, Pownal, South Burlington, St George, Stowe, and Wilmington.

### Read this before trusting the CSV

**`has_service_polygon` is `Y` for all 80 rows, and that is falsely reassuring.** The matcher assigned every district its closest EPA name, but "closest" is not "correct." Four matches are visibly wrong:

| District | Town | Matched to | Score |
| --- | --- | --- | --- |
| North Branch Fire District 1 | Dover | BRANDON FIRE DISTRICT 1 | 62 |
| Highgate Fire District 1 | Highgate | HUNTINGTON FIRE DISTRICT 1 | 64 |
| Sherburne Fire District 1 | Killington | SHELBURNE FARMS | 69 |
| South Alburgh Fire District 2 | Alburgh | ALBURGH FIRE DISTRICT 1 | 73 |

So the true "matched to a polygon" count is lower than 80. **Treat every match below ~85 as unverified regardless of the `Y` flag.** The problem bites hardest in the multi-district towns, where district names within a town are near-identical ("Rutland Town Fire District 1/4/5/6/11") and name-matching genuinely cannot resolve five same-named districts. Those need a **spatial** check — which EPA polygon falls inside which district's area — not a name check.

Before this goes to the Bond Bank: swap the name-match for a spatial match on the multi-district towns, and hand-verify the flagged misses. The 46 single-district proxies are trustworthy as-is, because with only one district in the town even a weak name match resolves to the right place.

**Update — the spatial matcher has now been run**, and it both confirms and complicates this. It rescued two of the four visible misses (Sherburne, North Branch), found the `has_service_polygon = Y` column to be wrong on at least one district, and disagreed with the name pass on **9** rows rather than 4. It also introduced two regressions of its own. See [`spatial_match_districts.py`](#spatial_match_districtspy) for the measured results and the three issues to fix before the output is trustworthy.

**On provenance:** the VRWA document is the best enumeration in existence, but it is one nonprofit's compilation, not a legal registry. State that plainly to the Bond Bank rather than implying it is authoritative.

### Where to look up a district's PWSID by hand

**The EPA polygon layer is the wrong place to look.** It holds 392 mapped service areas; Vermont has **1,356 active public water systems**. A district missing from the polygon layer usually still has a PWSID — it just has no mapped boundary. Looking only at the 392 makes real systems look nonexistent.

The authoritative registry is **SDWIS**, queryable without a key via EPA Envirofacts:

```text
https://data.epa.gov/efservice/WATER_SYSTEM/PRIMACY_AGENCY_CODE/VT/JSON
```

4,415 Vermont rows (1,356 with `pws_activity_code = A`), carrying `pwsid`, `pws_name`, `population_served_count`, `pws_type_code` (CWS / NTNCWS / TNCWS), and activity status. Filter to active, then match on name **and** population — the VRWA roster's population figures come from the same reporting chain, so an exact population match is strong corroboration of a name match.

For a browser instead of an API:

- **VT DEC Drinking Water Watch** — <https://anrweb.vt.gov/DEC/DWW/> — search by system name, town, or PWSID; the state's own front end on the same data.
- **EPA ECHO** — <https://echo.epa.gov/> — detailed facility report per PWSID (the crosswalk already links these).
- **The town clerk**, for who actually operates what. Contacts are in [`contacts.html`](docs/contacts.html).

Two important distinctions this exposes, which the crosswalk currently conflates in one column:

| Question | Source | Meaning |
| --- | --- | --- |
| Does this district exist as a water system? | SDWIS | it has a PWSID |
| Does it have a mapped service area? | EPA polygon layer | it has geometry |

A district can answer yes to the first and no to the second. Splitting `matched_pwsid` into a system identity and a separate "has a polygon" flag would make the roster considerably clearer.

## Legislative Charters (Title 24 Appendix)

The Title 24 Appendix index is scrapeable, and the chapters follow a clean pattern — `Chapter NNN: <District Name>` — with fire districts clustered in the 500s and water districts/corporations in the 700s.

Critically, individual charters contain a `§ ...-1 Boundaries` section (visible in the Village of Essex Junction charter, chapter 213). **For legislatively-chartered districts, the charter text itself carries the boundary description** — narrative metes-and-bounds, not geometry, but it is the authoritative political boundary definition. That is the seed for eventual digitizing.

Two hard limits on how far this gets us:

1. **The charters are a minority of the real universe.** The whole 500s/700s fire-and-water cluster is maybe a couple dozen districts, and only **6 of the 80** districts in our roster are flagged `has_legal_charter`: Fairfax FD 1, St George FD 1, St George FD 2, Cold Brook FD 1, Champlain Water District, and North Branch FD 1. VLCT confirmed that most districts formed by local action never got a legislative charter and file nothing with the state. The charter index gives you the authoritative-but-small core; the EPA water systems give you the "has a service area" reality; **the gap between them is the actual project.**

2. **The district chapters' Boundaries sections mostly cite a record rather than describe one.** Of the 10 district chapters, most point to a plat in town land records. But see the correction below: this is true of the *district* chapters specifically, not of the Appendix as a whole, and even within them the first pass under-reported.

> **Superseded in part.** The two sections below were written from a 10-chapter pull whose regex missed real content. [`scrape_charter_boundaries.py`](#scrape_charter_boundariespy) now covers all 114 chapters and finds genuine metes-and-bounds descriptions plus usable boundary sections in chapters previously reported as empty. Read that section for the corrected picture.

### What the 10 charters actually say

All 10 chapters were fetched and parsed on 2026-08-14. Results:

| Outcome | Count | Meaning |
| --- | --- | --- |
| Record pointer | 5 | Cites a plat in town land records |
| Text, but not geometry | 2 | Prose that defines the boundary by reference |
| Nothing extracted | 3 | No Boundaries section found |
| **Metes-and-bounds description** | **0** | — |

The representative case, Cold Brook Fire District No. 1 (ch. 507):

> "The boundaries of Cold Brook Fire District No. 1 shall be as recorded in Book 111, page 184 et seq. of the land records of the Town of Wilmington and in Book 86, page 5 et seq. of the land records of the Town of Dover."

**The charter does not contain the boundary — it points to it, in a town clerk's office.** That is still useful: it tells a digitizer exactly which recorded plat to go pull. But it is a reference-to-a-reference, not geometry.

Set expectations with the Bond Bank accordingly: **"chartered" does not mean "boundary in hand."** It means "boundary is findable in a specific town record."

The two non-pointer results are worth distinguishing, because one is useful and one is not:

- **Edward Farrar Utility District (ch. 705)** — *"The boundaries of the District are coextensive with the current boundaries of the Village of Waterbury."* This is genuinely actionable: it resolves to an existing, already-mapped municipal boundary. No digitizing needed.
- **Fairfax Fire District No. 1 (ch. 511)** — *"within the corporate limits presently established"* — circular, and it came from the `Creation` fallback pattern rather than a real Boundaries section. It defines nothing.

Chapters returning nothing: 505 Williamstown, 509 North Branch, 703 Champlain Water District.

**The charter set and the roster's chartered flag are different sets.** `CHARTERS` in the script lists 10 chapters; the VRWA roster flags only 6 rows `has_legal_charter`, and the overlap is partial. Milton, Bolton, Williamstown, Morristown Corners, and Edward Farrar have chapters but are not flagged in the roster; St George Fire District 2 is flagged in the roster but has no chapter in the script. Reconciling these two lists is an open task.

## Scripts

```bash
python script/pull_vt_water_boundaries.py   # EPA service areas -> data/vt_water_boundaries.gpkg
python script/merge_clerk_contacts.py       # SoS clerk xlsx -> data/vt_town_clerk_contacts_filled.csv
python script/build_fire_districts.py       # pilot shapefiles -> data/vt_fire_districts.gpkg
python script/scrape_charter_boundaries.py  # Title 24 App -> data/vt_charter_boundary_sections.csv
python script/build_site_data.py            # all of the above -> docs/data/
python script/build_district_crosswalk.py --epa vt_water_boundaries.csv [--vlct vlct_list.csv]
python script/spatial_match_districts.py    # repair name-matches spatially
python script/pull_charter_boundaries.py    # charter Boundaries text -> charter_boundaries.csv
```

Run `merge_clerk_contacts.py` before `build_site_data.py`; the latter falls back to the
unfilled skeleton and prints a warning if the filled CSV is absent.

> **Working directory:** `spatial_match_districts.py`, `pull_charter_boundaries.py`, and `merge_clerk_contacts.py` reference their inputs as bare filenames (`vt_water_boundaries.gpkg`, `vt_district_crosswalk.csv`, `vt_town_clerk_contacts.csv`), but those files live in `data/`. Run them from inside `data/`, or change the path constants. `pull_charter_boundaries.py` fails *silently* here — it catches the missing crosswalk and skips the join, still writing `charter_boundaries.csv`, so a run can look successful while producing no joined output. `build_site_data.py` uses absolute paths and runs from anywhere.

### `build_fire_districts.py`

Builds **`data/vt_fire_districts.gpkg`** (layer `fire_districts`, EPSG:32145) plus a `vt_fire_districts.csv` attribute sidecar. This is the layer the whole project is trying to produce — the political/taxing boundaries that [caveat 10](docs/caveats.html) says exist nowhere statewide. It currently holds **3 pilot polygons out of 80 districts**. It is the seed, not the deliverable.

**Joining to the water data.** Every row carries `pwsid`, so the layer joins 1:1 to `data/vt_water_boundaries.gpkg` on `PWSID`:

```python
fd  = gpd.read_file("data/vt_fire_districts.gpkg", layer="fire_districts")
epa = gpd.read_file("data/vt_water_boundaries.gpkg", layer="all_public_water_systems")
fd.merge(epa, left_on="pwsid", right_on="PWSID")     # verified: 3 of 3 join
```

`district_name` + `town` join to `data/vt_district_crosswalk.csv`; `town` joins to the clerk contact sheet. Roster attributes (population, `district_type`, `services`, `districts_in_town`, `single_district_town`, `has_legal_charter`, `match_score`) and the town clerk's name and email are denormalized onto each row, so the file works as a standalone digitizing worklist.

**CRS is inferred, not read.** The pilot shapefiles have no `.prj` ([caveat 11](docs/caveats.html)), so the script reprojects each file under every candidate CRS and keeps whichever lands the polygon on its own town — the town is the ground truth. It independently recovered **EPSG:4326** for Danville and Hardwick and **EPSG:32145** for Peacham, the three CRSs the caveats document noted. Rows record `source_crs` and `crs_inferred = Y` so a guess is never mistaken for a declaration. The same mechanism will handle the next partner submission that arrives without a projection.

#### Provenance: every polygon cites its source

Any boundary in this layer can be defended. Each row carries:

| Field | Purpose |
| --- | --- |
| `source_type` | partner shapefile / statute (town-wide) / statute (road-bounded) |
| `source_citation` | e.g. `24 V.S.A. App. ch. 505, § 2` |
| `source_url` | direct link to the statute section or submission |
| `source_text` | **the verbatim text that authorizes the polygon** |
| `derivation` | how the geometry was actually produced |
| `district_website` | the district's own site, where one exists |

The map popup renders the citation, the quoted statute, and the derivation, so a reviewer can see *why* a polygon is shaped the way it is without opening the CSV.

#### The five current boundaries

| District | Source | Area | Extent | Verified |
| --- | --- | --- | --- | --- |
| Danville FD 1 | partner shapefile | 158.03 km² | coextensive with town | Y |
| East Hardwick FD 1 | partner shapefile | 100.24 km² | coextensive with town | Y |
| Peacham FD 1 | partner shapefile | 94.72 km² | sub-town (76.6%) | N |
| **Williamstown FD** | **24 V.S.A. App. ch. 505, § 2** | 104.53 km² | coextensive with town | Y |
| **Fairfax FD 1** | **24 V.S.A. App. ch. 511, § 2** | 2.65 km² | **approximate** | N |

**Williamstown Fire District** is exact, not an approximation. The statute reads: *"The corporate limits shall be the boundary lines of the Town of Williamstown…"* — so the VCGI town polygon **is** the district boundary, copied unmodified.

Williamstown also exposes a roster gap: it is **not among the 80 VRWA districts**, and SDWIS shows it operates no public water system (Williamstown's water is a town department, VT0005186). The VRWA roster is *water-system-scoped*, so a chartered fire district that provides no water falls outside it. **The true universe of Vermont fire districts is larger than 80** — worth stating to the Bond Bank alongside [caveat 3](docs/caveats.html).

**Fairfax FD 1 is approximate, and I over-promised it earlier.** I described it as digitizable from its four named roads without a clerk visit. Testing that: the roads exist in the VT E911 centerline layer, but they **do not close a ring** — gaps of 163 m, 825 m, and 1,072 m sit between them. So the polygon is the convex hull of the four centerlines, `geometry_status = approximate`, `extent = approximate_from_statute`, `verified = N`, drawn dotted teal on the map. Two things support it as a starting estimate: it is 2.65 km², a plausible scale for an 80-person district, and it contains **98.6%** of that district's EPA service area. But the statute itself says *"as recorded with the Town of Fairfax"* — the authoritative geometry is a town record, same as Cold Brook.

#### North Branch Fire District 1 — no polygon yet

The district publishes a boundary map at <https://www.northbranchfiredistrict.com/>, but it is a raster image on a Wix page: no GeoJSON, KML, or ArcGIS layer, and the site's 10 PDFs are ordinances and minutes rather than georeferenced maps. Tracing pixels off a screenshot would fabricate coordinates, so no geometry was created. Its charter ([ch. 509, § 1](https://legislature.vermont.gov/statutes/section/24APPENDIX/509/00001)) is circular — *"within the corporate limits presently established"* — and gives nothing either.

It is tracked in **`data/vt_fire_districts_pending.csv`** so it stays visible. Ask the district for the source GIS file or a georeferenced PDF; the map exists, so someone has the underlying data.

#### Two of the three pilot districts are coextensive with their town

The script measures each polygon against its own **unsimplified** VCGI town boundary and records the result as `extent`:

| District | Source CRS | Area | IoU vs town | `extent` | Verified |
| --- | --- | --- | --- | --- | --- |
| Danville Fire District 1 | EPSG:4326 | 158.03 km² | 99.93% | `coextensive_with_town` | Y |
| East Hardwick Fire District 1 | EPSG:4326 | 100.24 km² | 99.80% | `coextensive_with_town` | Y |
| Peacham Fire District 1 | EPSG:32145 | 94.72 km² | 76.62% | `sub_town` | N |

Danville and East Hardwick genuinely cover their whole town — **confirmed by the project lead**. A Title 20 fire district can be coextensive with its municipality, so a boundary equal to the town outline is a real district extent, not a mis-filed town shape. All **3 of 80** are usable.

**This matters for how the metrics are computed.** For a town-wide district the *area difference against the town* is zero by definition — that is the answer, not a missing result. The meaningful comparison for those districts is against the **water service area**, where the gap is large:

| District | Political boundary | Water service area | Ratio |
| --- | --- | --- | --- |
| Danville FD 1 | 158.03 km² | 6.80 km² | 23× |
| East Hardwick FD 1 | 100.24 km² | 1.56 km² | 64× |
| Peacham FD 1 | 94.72 km² | 0.69 km² | 138× |

That gap is the quantity this project exists to measure, and it is why a service area cannot proxy for a political boundary.

`geometry_status` stays as a separate field for boundaries that equal their town but have **not** been confirmed as town-wide — those come through as `unconfirmed_townwide`, since without confirmation an equal-to-town polygon is genuinely ambiguous between a town-wide district and a mis-filed town outline. Add confirmed districts to `TOWNWIDE_CONFIRMED` in the script as they are checked off.

### `scrape_charter_boundaries.py`

Scrapes **all 114 chapters** of Title 24 Appendix and extracts, verbatim, every section that describes a district's or municipality's boundaries.

```bash
python script/scrape_charter_boundaries.py
python script/scrape_charter_boundaries.py --chapter 127        # one chapter
python script/scrape_charter_boundaries.py --cache-dir .cache   # reclassify without refetching
```

Outputs:

- **`data/vt_charter_boundary_sections.csv`** — 165 matching sections across **72 municipalities**, with `municipality`, `municipality_type`, `chapter`, `section_number`, `section_heading`, `match_reason`, `char_count`, a direct `section_url`, and `section_text`.
- **`data/vt_charter_chapters.csv`** — all 114 chapters with section counts and hit counts, so the 41 chapters with no boundary section are visible rather than silently absent.

`section_text` is the statute's own words. Tags are stripped and entities decoded, and the source's layout line-wrapping is normalized to one line per paragraph — no summarizing, truncation, or rewording. `char_count` lets you spot anything suspiciously short. CSV is UTF-8 with BOM so Excel opens the `§` correctly, and multi-paragraph text is quoted (77 rows contain paragraph breaks).

**Why the whole Appendix, not just the district chapters.** District provisions live inside *town* charters too. Chapter 127 (Town of Middlebury) carries [§ 1505 "Fire District No. 1 East Middlebury"](https://legislature.vermont.gov/statutes/section/24APPENDIX/127/01505), which no scan of the 500s would ever reach.

Three independent match rules, recorded per row so you can filter by confidence:

| `match_reason` | Rows | Rule |
| --- | --- | --- |
| `boundary_language` | 105 | body has "beginning at", "thence north", "metes and bounds", "land records of"… |
| `boundary_heading\|boundary_language` | 28 | both |
| `district_heading` | 23 | heading names a fire/water/sewer/lighting district |
| `boundary_heading` | 8 | heading says Boundaries / Territory / corporate limits |

#### This corrects two earlier findings

**1. Metes-and-bounds descriptions do exist in the Appendix.** The earlier claim of zero was drawn from only the 10 district chapters. Across all 114, real survey prose is common in city and village charters. [St. Albans § 2 Boundaries](https://legislature.vermont.gov/statutes/section/24APPENDIX/011/00002) runs **12,566 characters**:

> "(1) Beginning at the southeasterly corner of Aldis Hill playground, thence northerly, westerly, southerly, and again westerly in the bounds of said playground to the northwesterly corner thereof. (2) Thence northerly, in a line parallel to High Street, to a point on the southerly boundary of property owned or formerly owned by Adhemard and Amanda Bertrand…"

That is digitizable — by hand, per district, as previously scoped.

**2. `pull_charter_boundaries.py` under-reported.** It found "nothing" for three chapters and only a circular Creation clause for Fairfax. Those were regex failures, not empty statutes. This scraper finds real sections in all of them:

| Chapter | Old result | Actually contains |
| --- | --- | --- |
| 511 Fairfax FD 1 | circular Creation clause | **§ 2 Boundaries** — bounded by four named roads |
| 505 Williamstown FD | nothing | § 2 Body corporate and corporate limits |
| 703 Champlain Water District | nothing | § 2, § 5, § 17 |
| 509 North Branch FD 1 | nothing | § 1 — genuinely circular |

**Fairfax Fire District No. 1 § 2** is immediately usable geometry:

> "The boundaries of Fairfax Fire District No. 1, as recorded with the Town of Fairfax, are bounded on the north by Bessette Road, the west by Highland Road, the south by Brick Church Road, and the east by VT Route 104."

Four named roads — that can be digitized from the road centerline layer without a trip to the town clerk.

**Williamstown Fire District § 2 confirms town-wide districts are a real, statutory pattern:**

> "The corporate limits shall be the boundary lines of the Town of Williamstown, being bounded as follows: easterly by the line of Washington; southerly by the lines of Chelsea and Brookfield; westerly by the lines of Northfield and Berlin; and northerly by the lines of Berlin and Barre."

A fire district whose corporate limits are its town's boundary lines, stated in statute. That is independent corroboration for treating Danville and East Hardwick as `coextensive_with_town` rather than as mis-filed town outlines, and it means Williamstown's boundary can be populated today by copying the VCGI town polygon.

`pull_charter_boundaries.py` is superseded by this script for boundary text; keep it only for its `boundary_is_record_pointer` flag.

### `build_district_crosswalk.py`

Scrapes the Title 24 Appendix index, keeps only fire/water/sewer districts, fuzzy-matches each against the EPA `PWS_Name` field, and writes `district_crosswalk.csv` (chartered districts, charter links, matched PWSIDs, plus EPA systems that matched nothing) and `district_review_queue.csv` (the 70–89 score rows needing human confirmation). Names are normalized before matching — "No. 1" stripped, corporation/incorporated noise removed — so "Cold Brook Fire District No. 1" has a chance of hitting the right system.

Match policy: `>=90` auto_confident, `70–89` review, `<70` none.

**Known issue — the charter scrape currently parses zero charters.** The current [`district_crosswalk.csv`](district_crosswalk.csv) in the repo root is 392 rows, all `unmatched_system` (i.e. EPA systems only), and [`district_review_queue.csv`](district_review_queue.csv) is empty. The scrape is regex against rendered HTML and that is the fragile part: the live index markup evidently does not match the `Chapter NNN: Name` pattern the script expects. Fixing that regex is the open task on this script. It is superseded for roster purposes by the VRWA-derived inventory, but the charter URLs it would produce are still wanted.

The VLCT list is not automated because there is no clean endpoint — VLCT built theirs by hand from Fire Academy records, membership rolls, and DEC permits. If it can be obtained as a CSV (worth an email; they may simply send it), pass it via `--vlct` and it folds into the same crosswalk.

> **Resolved:** `data/vt_district_crosswalk.csv` used to have no committed generator. [`build_district_roster.py`](#build_district_rosterpy) now derives the roster from the source workbook, so it is reproducible.

### `build_district_roster.py`

Builds **`data/vt_district_roster.csv`** from `data/4 - VT PWS Fire District List - Updated Sept 2025 (1).xlsx` — the machine-readable version of the VRWA enumeration that the hand-extracted crosswalk was based on. This closes the "no generator" gap: the roster can now be refreshed when VRWA/DEC reissue the list.

The workbook has two sheets:

- **`Water`** — 79 named water-providing districts (Type, System Name, System Town, Pop Served, Services). Reconciles **78/79** against the existing crosswalk.
- **`WW`** — 9 wastewater systems with 37 columns: discharge permit, NPDES id, treatment type and capacity, ownership, plus **named operator and administrative contacts**. Seven also appear on the Water sheet as `FD-both`; two (North Branch, Sherburne) are wastewater-only, which is why they are absent from the Water sheet.

Output is 81 rows — the existing 80 plus one candidate the crosswalk omits (below) — carrying the PWSID and charter flags already established in the crosswalk, so it is a superset rather than a replacement.

**New: a candidate 81st district.** `Cold Brook Fire District Base Area` (Wilmington, pop 762) is typed **`FD?`** in the workbook — VRWA itself is unsure whether it is a distinct district. It is separate from Cold Brook Fire District 1, and at 762 people it is not trivial. Flagged `unconfirmed = Y`. Worth resolving, and further evidence for [caveat 3](docs/caveats.html) that the roster is a working compilation rather than a census.

**New: wastewater as a dimension.** The project had no wastewater data. The roster now carries discharge permits (e.g. `3-1296`), NPDES ids (`VT0101214`), treatment type and capacity for 9 districts — new join keys into DEC's wastewater permitting records.

**New: named district contacts.** Nine districts now have a real operator or administrator with an email and phone, versus the generic "look up the PWSID in Drinking Water Watch" placeholder. These are written to the roster CSV but are **deliberately not published to the site** — several are personal addresses (gmail/comcast/yahoo) from a working spreadsheet, unlike the town clerk directory which comes from a published state list. Publishing them should be a conscious decision, not a side effect.

#### Population cross-check — two real drinking-water corrections

The workbook's `Pop Served` and the EPA polygon layer's `Population_Served_Count` are independent reports of the same number, so the generator compares them. **67 of 69 agree exactly.** The two that disagree are both actionable, and are written to `data/vt_district_population_check.csv`:

| District | Workbook | EPA layer | Finding |
| --- | --- | --- | --- |
| Rutland Town FD 11 | 29 | 401 | **Wrong PWSID.** `VT0005534` is Rutland Town Fire District **1** in SDWIS (pop 401). FD 11 is **`VT0021007`**, pop **29** — matching the workbook exactly. |
| Pownal FD 2 | 682 | 400 | **Stale EPA attribute.** SDWIS confirms `VT0020734` = 682. The workbook is right; the EPA polygon's population is out of date. |

The Rutland Town FD 11 error was already suspected from the SDWIS name sweep; the workbook confirms it independently on population, in the five-district town where name matching is least reliable. That is a genuine drinking-water data correction, not just a wastewater addition.


### `spatial_match_districts.py`

Repairs the name-based matches by geography instead of strings. It loads the EPA polygons, pulls VCGI town boundaries, spatially tags each EPA polygon with the town it physically sits in (largest-overlap, not centroid), then re-resolves each district's match **constrained to its own town** — a district can only match polygons actually in its town, with name similarity breaking ties among same-town candidates.

Output `vt_district_crosswalk_spatial.csv` adds `spatial_town`, `polygons_in_town`, `spatial_pwsid`, `spatial_pws_name`, `name_vs_spatial_agree`, and `spatial_status`.

**Measured results from an actual run (2026-08-14, 392 EPA polygons × 256 towns):**

| `spatial_status` | Count |
| --- | --- |
| `needs_review_multi` | 53 |
| `confirmed_single` | 22 |
| `no_polygon_in_town` | 5 |

`name_vs_spatial_agree = N` on **9** rows — nine matches the name pass got differently.

These numbers are **not** the expected 46 confirmed / 34 review split, and the reason is a design issue worth knowing before anyone reads the CSV:

1. **`needs_review_multi` keys off polygon count, not district count.** Any town containing more than one EPA polygon triggers it — including towns with a single district that merely happen to contain unrelated small systems (mobile home parks, schools, campgrounds). One town holds 18 polygons. The result: **21 of the 46 single-district towns land in the review pile**, inflating it from 34 to 53. The status conflates "several districts share this town" with "this town has several unrelated water systems." Splitting those two conditions is the fix.

2. **Three of the five `no_polygon_in_town` rows are false alarms from `St.` abbreviation handling.** St George FD 1, St George FD 2, and St Johnsbury Center FD 1 all have exact-name EPA matches (score 100, 100, and 94) — the polygons exist. `norm_town()` collapses whitespace and title-cases but does not normalize `St` vs `St.`, so the roster town never joins the VCGI town. Tri Town Water District is a fourth false alarm of a different kind: it is a regional district whose polygon's majority overlap lands outside its listed town. Only Highgate FD 1 is a genuine miss.

3. **The tie-break can overwrite a correct name match with a worse one.** Two of the nine disagreements are spatial-pass regressions, not fixes:

| District | Name match (score) | Spatial pick | Verdict |
| --- | --- | --- | --- |
| Sherburne FD 1 (Killington) | SHELBURNE FARMS (69) | PICO VILLAGE WATER CORP | **fixed** |
| North Branch FD 1 (Dover) | BRANDON FIRE DISTRICT 1 (62) | BOULDER RIDGE AT MT SNOW | **fixed** |
| Passumpsic FD 1 (Barnet) | PASSUMPSIC FIRE DISTRICT 1 (100) | MCINDOE FALLS FIRE DISTRICT 3 | **regression** |
| Canaan FD 2 (Canaan) | CANAAN FD #2 (100) | CANAAN FIRE DISTRICT 1 | **regression** |

   The spatial pass correctly rescued the two worst cross-town errors. But where the name match already scored 100, the town-constrained tie-break replaced it with a different polygon — because the correctly-named polygon's majority overlap fell in a neighboring town, so it was never a candidate. **A 100-score name match should win over the spatial tie-break.** Until that guard is added, treat `name_vs_spatial_agree = N` on a high-scoring row as suspect in *both* directions.

The VCGI endpoint hard-coded in the script is **confirmed correct** (`FS_VCGI_OPENDATA_Boundary_BNDHASH_poly_towns_SP_v1`, field `TOWNNAME` present) — the run above fetched all 256 towns without a URL change, so the caveat about needing a one-line URL swap can be closed.

### `pull_charter_boundaries.py`

Fetches all 10 Title 24 Appendix charter chapters, extracts the `§ 1. Boundaries` section (falling back to `Creation`/`District`/`Territory`), flags whether the text is a land-records pointer, and writes `charter_boundaries.csv` plus `vt_district_crosswalk_charters.csv`. Verified working against the live site — see [What the 10 charters actually say](#what-the-10-charters-actually-say) for results.

**Known issue — the crosswalk join matches 1 row out of 10.** `norm()` strips `No. N` from the charter-side names ("Cold Brook Fire District No. 1" → `cold brook fire district`) but the VRWA roster uses bare trailing numbers ("Cold Brook Fire District 1" → `cold brook fire district 1`), so the keys never align. Only `Champlain Water District`, which has no number, joins. `vt_district_crosswalk_charters.csv` therefore comes out with charter text on one row instead of six. The fix is to strip bare trailing digits on both sides in `norm()`.

Minor: the fetch does not set an explicit response encoding, so `§` arrives mojibake'd in the extracted text.

### `merge_clerk_contacts.py`

Fills the town-clerk contact sheet from the Vermont Secretary of State's maintained *Town Clerk Contact Information* workbook — the one authoritative, actively maintained list. Scraping 250-odd town websites instead would produce a sheet that is largely wrong.

**Why this matters to a boundaries project:** [caveat 6](#what-the-10-charters-actually-say) — chartered districts define their boundary by citing a plat recorded in town land records. The clerk is who holds that plat. The contact sheet turns "Book 111, page 184, Town of Wilmington" into an actionable request.

Verified run against the live SoS file (stamped June 12, 2026): **247 of 272 municipalities have a clerk contact.** The 25 without are villages, gores, and unincorporated places that have no separate town clerk — expected, not missing data.

Three bugs were found and fixed while wiring this into the site:

1. **The workbook has four banner rows before the headers.** A plain `read_excel` picked up the title as the sole named column and everything else as `Unnamed: N`, so the first run matched 12 of 269 towns and filled **zero** emails while reporting success. The loader now scans for the header row and also captures the file's "Last Updated" stamp for provenance.
2. **The SoS spells them "Saint", the skeleton uses "St."** — St. Johnsbury, St. George, and St. Albans all silently failed to match. Both sides now fold `Saint` → `St`.
3. **Stripping the trailing City/Town word collapsed four City/Town pairs onto one key** (Barre, Newport, Rutland, Saint Albans), silently handing the Town the City clerk's contact. **Rutland Town — the five-district town at the centre of the digitizing backlog — was getting Rutland City's clerk.** The suffix is now kept as a `kind` and matched explicitly; a bare SoS name acts as a wildcard so cities like Burlington still resolve.

The script also appends municipalities the SoS carries but the skeleton lacks. On the current data that is exactly three — **Newport Town, Rutland Town, Saint Albans Town** — the Town halves of City/Town pairs the skeleton only listed once.

Regenerate: `cd data && python ../script/merge_clerk_contacts.py`, then `python script/build_site_data.py`.

## Web Map

An interactive site is published from the `docs/` folder via GitHub Pages.

To enable it: **Settings → Pages → Source: Deploy from a branch → `main` / `/docs`.**

Three pages:

| Page | What it is |
| --- | --- |
| `index.html` | Map of the 392 EPA service areas, 3 fire district boundaries, and 256 VCGI town boundaries, with layer toggles, a provenance filter, and system search. Leads with the headline caveat so nobody mistakes service areas for political boundaries. |
| `caveats.html` | The full contents of `District_Boundary_Data_Caveats.docx` as a web page — the at-a-glance matrix, all 12 severity-tagged caveats, and the deliverable framing. |
| `contacts.html` | Searchable town clerk directory, filterable by county, with an "has an email" filter. |

**The three pages are wired to each other, not just co-located.** Clicking a town on the map opens its clerk's contact, because the charter-cited plats live in that office. Caveat 6 links to the clerk directory; caveat 7 links back to the map's authoritative-only filter; the clerk directory explains its own existence by pointing at caveat 6.

`build_site_data.py` reprojects to WGS84, simplifies geometry for the browser, and writes `water_service_areas.geojson`, `town_boundaries.geojson`, `town_clerks.json`, and `meta.json` into `docs/data/`. The clerk payload is `{municipalities: [...], byTown: {key: index}}`; `byTown` is resolved at build time against the VCGI town names so the browser only has to recompute a simple key. It currently joins **254 of 256** town polygons — the two misses are Avery's Gore and Lewis, both unincorporated with no clerk.

**Basemap:** standard OpenStreetMap tiles (`tile.openstreetmap.org`), with Esri World Imagery as the aerial option. OSM carries its own labels and colour, so overlay fill opacity is kept low (service areas 0.18) to keep street names readable underneath. Note OSM's [tile usage policy](https://operations.osmfoundation.org/policies/tiles/) if traffic ever grows beyond light use.

The fire district layer draws in its own pane between towns and water, so districts read as containers with their service areas legible on top. Real district geometry is solid purple; town-outline placeholders are dashed grey and their popup says why they cannot be used. To add a further layer, write another GeoJSON into `docs/data/` and add one entry to the `LAYERS` registry in `docs/app.js` plus a checkbox in `docs/index.html`.

> **Corrected on the site:** the earlier text said roughly 60% of the service-area boundaries are authoritative and 40% EPA-modeled. That is the *national* figure. Vermont is **89% authoritative / 11% modeled** (348 of 392), as the caveats document notes. `meta.json` now carries `authoritative_pct` so the page cannot drift from the data again.

## Metrics

The analysis will focus on the following metrics:

1. **Area Difference** – The spatial difference between the political boundaries of each fire district and the properties served by the water system (as shown in the ANR map).
2. **Coverage Percentage** – The proportion of the town's area (as defined by VCGI town boundaries) that falls within the fire district. Town boundary data is available from [VCGI VT Data – Town Boundaries](https://geodata.vermont.gov/datasets/VCGI::vt-data-town-boundaries-1/about).

## Pilot Fire Districts

The following fire districts are included in the pilot project:

- **Peacham Fire District 1** — [Website](https://peacham.org/peacham-fire-district/)
- **Westford Fire District 1**
- **Greensboro Bend Fire District 2**
- **Danville Fire District 1**
- **Burke Fire District 1 (East Burke)**
- **East Hardwick Fire District 1** — [Website](https://ehfd.mystrikingly.com/)

## Background: The Lead & Copper Rule

Under the EPA's updated Lead & Copper Rule Improvements, Vermont public water systems must prepare a Service Line Inventory—documenting every connection from the water main to the building—including material type (lead, galvanized, copper, plastic, or unknown)—by October 16, 2024. To support this regulatory effort, the DEC maintains guidance and templates on its website requiring submission in standardized formats. However, Vermont lacks a comprehensive statewide service-area GIS layer linking water systems, their boundaries, and service-line inventory data—this undermines planning for lead replacement, capital needs, and financing.

Beyond regulatory compliance, the Vermont Bond Bank would be able to leverage this mapped data to inform strategic capital planning and municipal bond financing. By overlaying service area boundaries with past and current infrastructure investments, Bond Bank staff could identify capital gaps, assess where previous funding has been allocated, and proactively plan future State Revolving Fund (SRF)-backed projects. The map would also highlight regions with aging infrastructure and elevated risk, which can be used to guide outreach and offer technical assistance through programs like the Small System Capacity and Resiliency Program. Scenario modeling would become more sophisticated as well—for instance, municipalities with multiple flagged service areas could be bundled together in financing packages, improving project readiness and execution.

This system would also contribute meaningfully to risk management and equity. Mapping service line materials alongside system boundaries and demographic data would help ensure that funding is targeted toward under-served and disproportionately affected communities. It would also mitigate the risk of delays or escalating project costs by giving municipalities clearer visibility into the scope and urgency of service line replacement needs—particularly helpful in the early planning stages, including during bond-readiness sessions.

## Data & Contacts

- **Water service areas** — EPA Office of Research and Development, [Public Water System Service Area Boundaries](https://services.arcgis.com/cJ9YHowT8TU7DUyn/arcgis/rest/services/Water_System_Boundaries/FeatureServer), filtered to Vermont PWSIDs. **89% authoritative** (state/utility sourced), 11% EPA-modeled — well above the ~60% national average.
- **Town clerk contacts** — Vermont Secretary of State, Elections Division, [Town Clerk Contact Information](https://outside.vermont.gov/dept/sos/Elections_Division/voters/vermont_town_clerk_contact_information.xlsx) (xlsx, stamped June 12, 2026).
- **Town boundaries** — [VCGI VT Data – Town Boundaries](https://geodata.vermont.gov/datasets/VCGI::vt-data-town-boundaries-1/about).
- **District roster** — VRWA, *Fire Districts and Special Use Districts*, September 2025 update.
- **Legislative charters** — Vermont Statutes Title 24 Appendix, [legislature.vermont.gov](https://legislature.vermont.gov).
- **Service line inventory (SLI)** — Vermont DEC [LCRR webpage](https://dec.vermont.gov/water/drinking-water/water-quality-monitoring/lead-and-copper-rule-revisions#ServiceLineMap), contact Rachel O'Reilly (<Rachel.OReilly@vermont.gov>).
- **Project lead** — Michael Gaughan, Executive Director, [Vermont Bond Bank](https://vtbondbank.org) (<michael@vtbondagency.org>).

## Open Tasks

### Fix before the crosswalk is trustworthy

1. `spatial_match_districts.py` — separate "town has multiple *districts*" from "town has multiple *polygons*"; `needs_review_multi` currently conflates them and over-reports by ~19 rows.
2. `spatial_match_districts.py` — normalize `St` / `St.` in `norm_town()`; three districts are falsely reported as `no_polygon_in_town`.
3. `spatial_match_districts.py` — let a 100-score name match win over the town-constrained tie-break, to stop the Passumpsic and Canaan FD 2 regressions.
4. `pull_charter_boundaries.py` — strip bare trailing digits in `norm()` so the crosswalk join matches 6 rows instead of 1.
5. Point `spatial_match_districts.py`, `pull_charter_boundaries.py`, and `merge_clerk_contacts.py` at `data/` rather than the working directory.
6. Reconcile the script's 10 charter chapters against the roster's 6 `has_legal_charter` rows.
7. Fix the Title 24 charter-index regex in `build_district_crosswalk.py` (currently parses zero charters).
8. Hand-verify the remaining flagged mismatches (Highgate, South Alburgh, and the 9 `name_vs_spatial_agree = N` rows).

### Data gathering

1. Commit a generator script for `data/vt_district_crosswalk.csv`.
2. Request the VLCT compiled district list as CSV.
3. Obtain the plat "recorded with the Town of Fairfax" to replace the approximate Fairfax FD 1 hull with the real boundary, and ask North Branch FD for the GIS source behind the map on its website.
4. Triage the 165 rows in `data/vt_charter_boundary_sections.csv` for the remaining districts; `char_count` and `match_reason` sort the survey descriptions from the one-line citations.
5. Add `Rutland Town`, `Newport Town`, and `Saint Albans Town` to `data/vt_town_clerk_contacts.csv` so the skeleton stops depending on the merge script to append them.
6. Fill `town_website` for the 35 municipalities missing one.
7. Have Peacham confirm its 94.72 km² boundary, then add it to `TOWNWIDE_CONFIRMED`/set `verified = Y`. Clerk: Rebecca Washington (<townclerk@peacham.org>).
8. Fix the partner intake spec ([caveat 11](docs/caveats.html)): require zipped shapefile sets or GeoPackage/GeoJSON with attributes and a defined CRS, so CRS never has to be inferred again.
9. Pull the cited plats from town land records for the 5 charter districts whose boundary is a record pointer.

### The actual project

1. Grow `data/vt_fire_districts.gpkg` from 4 confirmed boundaries toward 80 (and beyond — see the Williamstown roster gap). Add each new district as a row with its `pwsid` so it stays joinable to the water data.
2. Digitize political boundaries for the districts in multi-district towns — the multi-month ORCA-student-scale project. Hand the Bond Bank the inventory first and let it drive the estimate, rather than quoting the digitizing blind. The remaining boundaries are genuine manual GIS work (parcel data, town maps, the charter-cited plats) that no script pulls.
