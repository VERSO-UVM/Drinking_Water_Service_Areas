# Drinking Water Service Area & District Boundary Data Standard

**Version 0.1 (draft for review), October 2026.** Prepared for the Vermont Bond Bank boundaries project, VERSO / UVM.

This standard covers what to include when you create or share a GIS boundary for a public water system or for the district that governs one. It is written for Vermont fire districts, water districts, towns, regional planning commissions and technical-assistance providers. Nothing in it is Vermont-only except the examples, so other states can adopt it as is.

It builds on the [EPA Community Water System Service Area Boundaries Data Standard](https://www.epa.gov/system/files/documents/2024-04/cws-service-area-boundaries-data-standard.pdf) (v1.1, October 2024). EPA's national [Public Water System Service Areas](https://www.epa.gov/ground-water-and-drinking-water/public-water-system-service-areas) dataset (v3.0, March 2026) and EPIC's [SAB State Playbook](https://www.policyinnovation.org/sab-state-playbook) both follow that standard. Wherever a field here has an EPA equivalent, the EPA element name is listed, so data built to this standard can feed the national layer without re-coding.

> **The one distinction that matters most.** A *service area* is where a system actually delivers water. A *political district boundary* is the legal, taxing extent of the district that governs it. They often differ, and every EPA and state dataset reviewed is a service-area dataset. This standard therefore makes `boundary_type` a required field. It also adds a section ([§6](#6-political-district-fields)) for what service-area standards leave out: the legal authority for a boundary, and its change history.

---

## 1. Obligation levels

| Level | Meaning |
| --- | --- |
| **Required** | A submission without it can't be used or traced. Ask for it before accepting the data. |
| **Recommended** | Expected whenever the information exists. Leave blank rather than guess. |
| **Optional** | Useful where available. |

EPA's standard has only Recommended and Optional. This standard adds Required because this project's own partner submissions show the cost of missing basics. Several pilot shapefiles arrived with no `.prj` and no attribute table, so their coordinate systems had to be inferred and their names re-attached by hand.

**Blank versus unknown.** Leave a field empty when the value doesn't apply. Use `Unknown` (coded fields) or the word `unknown` (free text) when the value applies but nobody knows it. These are different facts, and downstream users need to tell them apart.

---

## 2. Files, geometry and coordinate system

| Requirement | Level | Detail |
| --- | --- | --- |
| File format | Required | **GeoPackage (`.gpkg`)** preferred; GeoJSON accepted. A shapefile must be a **complete, zipped set**: `.shp`, `.shx`, `.dbf` and `.prj` at minimum. A bare `.shp` can't be used. |
| Coordinate system declared | Required | The CRS must be stated in the file (`.prj`, GeoPackage SRS, or GeoJSON's default WGS 84). Undeclared CRSs get inferred, recorded as inferred, and flagged. |
| Preferred CRS | Recommended | Vermont: **EPSG:32145**, NAD83 / Vermont State Plane (meters). For national exchange, EPA recommends **EPSG:4326** (WGS 84). Any declared CRS is accepted. |
| Geometry type | Required | **Polygon or MultiPolygon**, closed and valid (no self-intersections). Don't submit boundary *lines*: a closed ring has to be converted before use, and some tools silently empty it. |
| One feature per boundary | Required | One row per district (or per system, for service areas). A district made of separate pieces is one MultiPolygon, not several rows. |
| Gaps and overlaps | Recommended | Districts that legally share an edge should share it exactly. Real overlaps (e.g. two districts that both claim a parcel) belong in `notes`, not in silent geometry edits. |
| Attributes | Required | Attributes may be carried in the file, or in the [submission form](#appendix-a-submission-form) when the sender's tools can't edit attributes. A small district shouldn't be turned away for lack of GIS skills, but the information is still required. |

**Shapefile field names.** Shapefiles truncate field names to 10 characters, which garbles several names below. This is another reason to prefer GeoPackage. If a shapefile is unavoidable, put the attributes in the submission form instead.

---

## 3. Core fields (every boundary)

| Field | Level | Type | Description | EPA element |
| --- | --- | --- | --- | --- |
| `boundary_id` | Required | text | Stable, unique ID that never changes when the geometry is edited. Vermont districts use `VTFD-0001`; service areas may use the PWSID. | — |
| `boundary_type` | Required | coded | `service_area` or `political_district`. See [§8](#8-coded-value-lists). | (v1.0 *Service Area Type*) |
| `name` | Required | text | Official name, e.g. *Danville Fire District 1*. For water systems, use the name as registered in SDWIS. | PWS Name |
| `state` | Required | text(2) | Two-letter postal code. | Primacy Agency |
| `towns` | Required | text | Town(s) the boundary falls in, separated by semicolons. | — |
| `county` | Recommended | text | County or counties, separated by semicolons. | — |
| `pwsid` | Required for service areas; Recommended for districts | text(9) | Public Water System ID: two letters plus seven digits, e.g. `VT0005037`. A district that runs several systems lists them all, separated by semicolons. One district is **not** always one system. | PWSID |
| `status` | Required | coded | `Active`, `Inactive`, `Dissolved`, `Merged`. | — |
| `area_sqkm` | Recommended | number | Area computed in an equal-area or state-plane CRS, not in degrees. | — |
| `notes` | Optional | text | Anything a user should know that fits nowhere else. | — |

---

## 4. Provenance fields (where the boundary came from)

These answer *who made this, from what, and how*. They follow the EPA standard's element set, and its Method and Method Basis lists are reused in [§8](#8-coded-value-lists) so values stay comparable nationally.

| Field | Level | Type | Description | EPA element |
| --- | --- | --- | --- | --- |
| `original_data_provider` | Required | text | Entity that created the boundary, e.g. *Danville Fire District*, *RCAP Solutions*, *VT ANR*. | Original Data Provider |
| `data_provider_type` | Required | coded | Type of that entity. | Data Provider Type |
| `method` | Required | coded | How the geometry was produced: GIS data, heads-up digitization, manual digitization, modeled, other. | Method |
| `method_basis` | Required | coded | What it was produced from: a plat, a legal description, parcels, a town boundary, water lines, and so on. | Method Basis |
| `method_details` | Recommended | text | Plain-language account of the steps, e.g. *"Traced from 1962 plat, Book 40 p. 112, georeferenced to VCGI parcels."* | Method Details |
| `source_document` | Recommended | text | The specific source used: map title, plat book and page, survey name, file name. | (Feature Type) |
| `source_url` | Recommended | URL | Link to the source document or dataset. | Data Source Link |
| `source_date` | Recommended | date | Date of the **source material**, e.g. when the plat was drawn. This is often decades before the GIS file. | — |
| `date_created` | Required | date | Date the GIS boundary was first created. | Date Created |
| `date_modified` | Recommended | date | Date the geometry or attributes last changed. | Date Modified |
| `publisher` | Recommended | text | Who distributes the dataset, if different from the provider. | Publisher (Owner) |
| `submitted_by` | Required | text | Person and organization who sent the file. | — |
| `submission_date` | Required | date | Date it was received. | — |
| `source_crs` | Required | text | CRS of the file as received, e.g. `EPSG:5646`. | — |
| `crs_inferred` | Required | Y/N | `Y` if no CRS was declared and it had to be worked out. | — |

**Why `source_date` and `date_created` are separate.** Utah, Washington, Florida (SJRWMD) and the Internet of Water schema all split these. A boundary digitized in 2026 from a 1962 plat is a 1962 boundary unless someone has confirmed nothing changed since.

---

## 5. Verification and accuracy fields

| Field | Level | Type | Description | EPA element |
| --- | --- | --- | --- | --- |
| `verification_status` | Required | coded | `Verified`, `Not Verified`, `Pending`, `Unknown`. | Verification Status |
| `verification_date` | Recommended | date | Date it was verified; blank if not verified. | Verification Date |
| `verification_process` | Recommended | text | How it was verified, e.g. *"Prudential committee reviewed printed map against district records."* | Verification Process |
| `verifier_type` | Recommended | coded | Type of entity that verified it. | Verifier Type |
| `verifier_name` | Recommended | text | Person and role, e.g. *"Jane Doe, district clerk."* (California records this.) | — |
| `verification_schedule` | Optional | text | Planned re-check, e.g. *"After each annexation"*, *"Every 5 years"*. | Verification Schedule |
| `positional_accuracy_m` | Optional | number | Estimated horizontal accuracy in meters; `-1` means unknown. (Adapted from Oregon's admin-boundary standard.) | — |
| `source_scale` | Optional | integer | Scale denominator of a paper source, e.g. `24000`. (From Missouri.) | — |

**What "Verified" means here.** For a political district, only an entity with legal knowledge of the boundary can verify it: the district itself, the town clerk who holds its records, or the state body that chartered it. A GIS analyst confirming that a polygon looks right is a QA check, not verification. Record that in `method_details` instead.

---

## 6. Political district fields

These apply when `boundary_type = political_district`. Service-area standards have no equivalents. They are drawn from the Census Boundary and Annexation Survey (BAS), FGDC's Governmental Unit Boundaries standard, Oregon's Administrative Boundary standard, Colorado DOLA's special-district layers, California LAFCo boundary-change layers and TCEQ's Texas water districts layer.

| Field | Level | Type | Description |
| --- | --- | --- | --- |
| `district_type` | Required | coded | `Fire District`, `Water District`, `Consolidated Water District`, `Other Special District`. |
| `services` | Recommended | coded | `Water`, `Wastewater`, `Water & Wastewater`, `Fire`, `Other`, separated by semicolons. |
| `legal_authority_type` | Required | coded | What legally establishes the boundary: legislative charter, municipal vote/order, ordinance, resolution, court order, other, unknown. |
| `legal_citation` | Required | text | Citation for that authority, e.g. `24 V.S.A. App. ch. 505, § 2`, or *"Town of Danville selectboard order, 1948"*. Write `unknown` if none has been found. |
| `legal_text` | Recommended | text | **Verbatim** boundary language from the authority, if any, e.g. *"The corporate limits shall be the boundary lines of the Town of Williamstown…"* |
| `recorded_document` | Recommended | text | Land-records reference for a recorded plat or description, e.g. *"Book 111, page 184, Town of Wilmington land records."* |
| `extent` | Required | coded | Relation to the town: `coextensive_with_town`, `sub_town`, `multi_town`, `approximate`. |
| `formation_date` | Recommended | date | Date the district was legally formed. (Colorado and TCEQ record this.) |
| `effective_date` | Recommended | date | Date the **current** boundary took legal effect: the formation date, or the date of the most recent annexation. Not the GIS edit date. (Oregon's standard is explicit on this.) |
| `previous_names` | Optional | text | Earlier names, separated by semicolons. (From Colorado.) |
| `governing_body` | Optional | text | E.g. *Prudential Committee*, *Board of Water Commissioners*. |
| `district_website` | Optional | URL | The district's own site. |
| `census_govid` | Optional | text | Census of Governments ID, if the district appears there. |
| `recorded_area_sqkm` | Optional | number | Area stated in the legal record, if any. Compare with `area_sqkm`; a large gap signals a digitizing problem. (TCEQ and Ventura LAFCo record both.) |

### 6.1 Boundary change history

A district boundary is a legal record that changes over time. A single polygon can't show how it got that way. Keep a **separate table** (`boundary_changes`), one row per legal change, modeled on BAS change polygons and LAFCo boundary-change layers.

| Field | Level | Description |
| --- | --- | --- |
| `change_id` | Required | Unique ID. |
| `boundary_id` | Required | The district changed. |
| `change_type` | Required | `Formation`, `Annexation`, `Detachment`, `Merger`, `Dissolution`, `Name Change`, `Correction`. |
| `effective_date` | Required | Date the change took legal effect. |
| `legal_authority_type` | Required | Same list as in §6. |
| `legal_citation` | Required | Vote, order, resolution or act number. |
| `document_url` | Recommended | Link to the scanned record. |
| `change_area_sqkm` | Optional | Area added or removed. |
| `geometry` | Optional | The area added or removed, as its own polygon. |

**`Correction` is different from the others.** It fixes the *digital* boundary to match a legal one that never changed (e.g. a line digitized on the wrong side of a road). It needs no legal citation, but `method_details` must explain it. Never record an annexation as a correction, or a correction as an annexation. (BAS and FGDC both draw this line.)

---

## 7. Service area fields

These apply when `boundary_type = service_area`. They follow the EPA standard directly. Population, connections and system type are joined from SDWIS by PWSID, not re-typed.

| Field | Level | Type | Description | EPA element |
| --- | --- | --- | --- | --- |
| `service_area_scope` | Required | coded | `Current service area`, `Jurisdictional area`, `Wholesale`, `Future/planned`, `Other`. | (v1.0 *Service Area Type*) |
| `secondary_id` | Optional | text | State or utility system ID. | Secondary ID |
| `secondary_id_source` | Optional | text | Who issued that ID. | Secondary ID Source |
| `population_served` | Recommended | integer | From SDWIS, at `date_modified`. | Population Served Count |
| `service_connections` | Recommended | integer | From SDWIS. | Service Connections Count |

`Jurisdictional area` here means the area a system is *obligated* to serve on request (EPIC's playbook definition). It is **not** the same as a political district boundary. Use `boundary_type = political_district` for that.

---

## 8. Coded value lists

Use these values exactly. EPA's national layer has no enforced value lists, and its free-text fields have drifted: `Data_Provider_Type` has more than 30 spellings, and `Verification_Status` contains both "Verified" and "Verified" with a trailing space. In a GeoPackage or geodatabase, set these up as domains.

**`boundary_type`:** `service_area` · `political_district`

**`data_provider_type`, `verifier_type`** (EPA list, plus two values this project needs):
`Water system` · `Federal agency` · `Tribal` · `State agency` · `Municipal agency` · `Private` · `Mixed` · `Academic` · `Other` · *`Nonprofit`* · *`District`*

> *Italicized values* extend EPA's list. Technical-assistance nonprofits (VRWA, RCAP) and the districts themselves supply most Vermont district boundaries. When exporting to EPA, map `Nonprofit` → `Other` and `District` → `Water system` (or `Municipal agency` if the district runs no water system).

**`method`** (EPA):

| Value | Meaning |
| --- | --- |
| `GIS data` | Built directly as a GIS feature, or copied from an existing GIS layer (e.g. a town boundary). |
| `Heads-up digitization` | Traced on screen from a scanned map, PDF or image. |
| `Manual digitization` | Digitized by hand, e.g. on a digitizing table, or from coordinates or bearings in a legal description. |
| `Modeled` | Estimated by a statistical or machine-learning model. |
| `Other` | Explain in `method_details`. |

**`method_basis`** (EPA list, plus district-specific values):

| Value | Meaning |
| --- | --- |
| `Service area` | A service-area map or file from the system. |
| `Service lines` | Water mains or service lines, usually buffered. |
| `Written description` | A legal description, metes and bounds, or written notes. |
| `Verbal description` | A phone call or interview. |
| `Geocoded locations` | Meter or billing addresses. |
| `Parcel boundaries` | Parcels of served or district properties. |
| `Municipal boundary` | A town or village boundary. |
| `County boundary` | A county boundary. |
| `Census Place` | A Census incorporated place or CDP. |
| *`Recorded plat`* | A plat or map recorded in land records. |
| *`Statute`* | A boundary stated in statute or charter text. |
| *`Feature-bounded`* | Roads, rivers or other named features, as named in an authority. |
| `Other` | Explain in `method_details`. |

**`verification_status`:** `Verified` · `Not Verified` · `Pending` · `Unknown`

**`service_area_scope`:** `Current service area` · `Jurisdictional area` · `Wholesale` · `Future/planned` · `Other`

**`district_type`:** `Fire District` · `Water District` · `Consolidated Water District` · `Other Special District`

**`legal_authority_type`:** `Legislative charter` · `Municipal vote/order` · `Ordinance` · `Resolution` · `Court order` · `Other` · `Unknown`

**`extent`:** `coextensive_with_town` · `sub_town` · `multi_town` · `approximate`

**`status`:** `Active` · `Inactive` · `Dissolved` · `Merged`

**`change_type`:** `Formation` · `Annexation` · `Detachment` · `Merger` · `Dissolution` · `Name Change` · `Correction`

**Dates:** ISO 8601, `YYYY-MM-DD`. If only the year is known, use `YYYY` and say so in `notes`.

---

## 9. Dataset-level documentation

Every published dataset, as opposed to a single submission, needs a README or metadata record covering the items below. These merge EPA's required dataset documentation with the core of FGDC CSDGM / ISO 19115.

1. **Title, purpose and boundary type.** Say plainly whether the layer holds service areas, political boundaries or both.
2. **Publisher and contact,** including how to report an error and how corrections are handled.
3. **Coverage and completeness.** How many boundaries are included out of how many exist (e.g. *"6 of 80 districts"*).
4. **Methods summary,** with a count of records by `method` and `method_basis`.
5. **Review and verification procedures,** and how many records are `Verified`.
6. **Known limitations and caveats.** For this project, see [Data caveats](caveats.html).
7. **Age of records** (range of `date_modified` and `source_date`) and the planned next update.
8. **Coordinate system, and the units of area fields.**
9. **Field list,** with a link to this standard and any local deviations from it.
10. **Use constraints.** E.g. *"Not a legal survey; does not establish jurisdiction."*

**Per-submission record.** Keep a short `SOURCE.md` next to each partner submission. It should record who sent it and when, the email or cover note verbatim, a manifest of the files received, and what was missing. [`boundary_submissions/South Alburgh Fire District 2/SOURCE.md`](https://github.com/VERSO-UVM/Drinking_Water_Service_Areas/blob/main/boundary_submissions/South%20Alburgh%20Fire%20District%202/SOURCE.md) is the model.

---

## 10. Intake checklist

Before accepting a boundary:

- [ ] Complete file set (GeoPackage, GeoJSON, or a zipped shapefile with `.shp`/`.shx`/`.dbf`/`.prj`)
- [ ] CRS declared; if not, inferred, recorded (`crs_inferred = Y`) and flagged to the sender
- [ ] Polygon geometry, valid and closed; one feature per district
- [ ] `boundary_type` stated: service area or political district?
- [ ] Name, town(s), and PWSID(s) where the district runs a water system
- [ ] Provider, method and method basis recorded
- [ ] For a political district: legal authority and citation, or an explicit `unknown`
- [ ] Verification status, and who would be able to verify it
- [ ] `SOURCE.md` written

---

## Appendix A. Submission form

For senders who can't edit GIS attributes. Copy this into an email or a `SOURCE.md`, fill it in, and send it with the boundary file.

```text
District / system name:
Town(s):
PWSID(s), if any:
Is this the service area (where water is delivered) or the
  district's legal/political boundary?
Who created the boundary, and when:
What it was drawn from (plat, legal description, parcels, water lines, town line...):
Source document reference (title, plat book/page, date):
How it was drawn (GIS, traced from a scan, from a description...):
Legal authority for the boundary (charter, town vote, ordinance...), with citation:
Annexations or changes since formation, with dates:
Has someone with knowledge of the district's records confirmed it? Who, and when?
Coordinate system of the file, if known:
Your name, organization, email:
```

---

## Appendix B. How this project's current layers map to this standard

`data/vt_fire_districts.gpkg` predates this standard. It covers most of the same ground under different field names. Nothing has been renamed yet; this table shows how the layer would migrate.

| Current field | Standard field | Notes |
| --- | --- | --- |
| `fd_id` | `boundary_id` | |
| `district_name` | `name` | |
| `town` | `towns` | Single town today; multi-town districts need a list. |
| `pwsid` | `pwsid` | |
| `district_type`, `services` | `district_type`, `services` | |
| `source_type` | `method` + `method_basis` | One free-text field currently stands in for two coded fields. |
| `source_citation` | `legal_citation` | |
| `source_text` | `legal_text` | |
| `source_url` | `source_url` | |
| `derivation` | `method_details` | |
| `source_file` | `source_document` | |
| `extent` | `extent` | Same values, plus `multi_town`. |
| `geometry_status` | `method = Modeled` / `extent = approximate` | |
| `verified`, `confirmed_by` | `verification_status`, `verifier_name` | Y/N becomes the coded list; add `verification_date`. |
| `source_crs`, `crs_inferred` | same | |
| `submitted_by`, `submission_date` | same | |
| `area_sqkm` | `area_sqkm` | |
| — | `boundary_type` | Always `political_district` in this layer. |
| — | `legal_authority_type`, `formation_date`, `effective_date` | Not yet collected. |

The EPA service-area layer (`data/vt_water_boundaries.gpkg`) already uses EPA element names. In Vermont's copy, `Verification_Status` and `Method_Details` are blank on all 392 features.

---

## Appendix C. Sources reviewed

Field lists were taken from published standards and from the live ArcGIS REST services (`?f=pjson`) on 2026-10-01.

| Source | Publisher | Type | Ideas adopted |
| --- | --- | --- | --- |
| [CWS Service Area Boundaries Data Standard v1.1](https://www.epa.gov/system/files/documents/2024-04/cws-service-area-boundaries-data-standard.pdf) | US EPA | Service area | Core element set; Method and Method Basis lists; verification fields; dataset documentation |
| [PWS Service Areas v3.0 data dictionary](https://www.epa.gov/system/files/documents/2026-03/data-dictionary_v3_03162026.pdf) and [ORD_SAB_Model metadata](https://github.com/USEPA/ORD_SAB_Model/tree/main/Metadata) | US EPA | Service area | Field names, SDWIS joins, modeled vs. system-sourced flag |
| [CWS State Dataset Summaries](https://www.epa.gov/system/files/documents/2024-04/cws-service-area-boundaries-state-dataset-summaries.pdf) | US EPA | Service area | Survey of 23 state schemas |
| [SAB State Playbook, Methods](https://www.policyinnovation.org/sab-state-playbook/methods) | EPIC | Service area | Current vs. jurisdictional definitions; open-format preference |
| [ref_pws contribution schema](https://github.com/cgs-earth/ref_pws) | Internet of Water | Service area | Separate source date and contribution date; contact email |
| [California Drinking Water System Area Boundaries](https://gispublic.waterboards.ca.gov/portalserver/rest/services/Drinking_Water/California_Drinking_Water_System_Area_Boundaries/FeatureServer/0) | CA SWRCB | Service area | Enforced value lists; `Pending` status; verifier name and type |
| [Drinking Water Service Areas](https://services8.arcgis.com/rGGrs6HCnw87OFOT/arcgis/rest/services/Drinking_Water_Service_Areas/FeatureServer/0) | WA DOH | Service area | Source type and source date (and the drift that comes without value lists) |
| [Culinary Water Service Areas](https://services.arcgis.com/ZzrwjTRez6FJiOq4/arcgis/rest/services/CulinaryWaterServiceAreas/FeatureServer/0) | Utah DWRe | Service area | Source date separate from edit date; inactive boundaries retained |
| [Public Drinking Water Districts](https://services2.arcgis.com/kNS2ppBA4rwAQQZy/arcgis/rest/services/MO_Public_Drinking_Water_Districts/FeatureServer/0) | Missouri DNR | Service area | Source map scale |
| [Public Water Service Areas](https://services.twdb.texas.gov/arcgis/rest/services/PWS/Public_Water_Service_Areas/FeatureServer/0) | Texas TWDB | Service area | Annual review cycle |
| [Public Water Supplier Service Areas](https://gis.dep.pa.gov/depgisprd/rest/services/emappa/eMapPA_External/MapServer/302) and [Purveyor Service Areas](https://mapsdep.nj.gov/arcgis/rest/services/Features/Utilities/MapServer/13) | PA DEP, NJ DEP | Service area | Service vs. wholesale type; last map received date |
| [Public-Supply Water Service Areas](https://www.sciencebase.gov/catalog/item/608035dcd34e8564d6835790) | USGS | Service area | Separate issues table for known problems |
| [Boundary and Annexation Survey guides](https://www2.census.gov/geo/pdfs/partnerships/bas/BAS_Technical_Guide.pdf) | US Census Bureau | Political | Change table; legal authority type; effective date; correction vs. legal change |
| [Framework Standard Part 5: Governmental Unit Boundaries](https://www.fgdc.gov/standards/projects/framework-data-standard) | FGDC | Political | Official description; effective date; expansion/contraction/reshape |
| [Administrative Boundaries Standard v2.0](https://ftp.gis.oregon.gov/framework/ZZ_SHARE/Standards/AdminBound/Administrative%20Boundaries%20Standard,%20v2.0.pdf) | Oregon GIC | Political | Effective date ≠ GIS edit date; positional accuracy; owner vs. steward |
| [Special district boundaries](https://gis.dola.colorado.gov/CO_SpecialDistrict) | Colorado DOLA | Political | Formation and dissolution dates; previous names; annual statutory map filing |
| [Special district boundary changes](https://maps.ventura.org/arcgis/rest/services/LAFCo/SpecialDistricts_BoundaryChanges/FeatureServer/430) | Ventura LAFCo (CA) | Political | Change records with resolution, recording date, document link |
| [Water Districts](https://gisweb.tceq.texas.gov/arcgis/rest/services/iwud/WaterDistricts_PRD/MapServer/0) | Texas TCEQ | Political | Recorded vs. calculated area; creation and boundary-change dates; method and source |

---

*Comments and proposed changes are welcome via [GitHub issues](https://github.com/VERSO-UVM/Drinking_Water_Service_Areas/issues). The version number will change when fields are added or redefined.*
