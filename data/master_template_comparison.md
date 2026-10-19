# Master template vs. site district list

This compares the *REVISED Water Systems-List-Master Template-V2-Final (MASTER TEMPLATE)* CSV, compiled by the RPCs (received 2026-10-19), with the 86 districts in `docs/data/districts.json`. The row-by-row results are in [`master_template_comparison.csv`](master_template_comparison.csv). The source CSV isn't in the repo.

## Method

- **Master rows:** 141 systems with a name (blank template rows dropped). The file is Windows-1252, not UTF-8.
- **Matching:** systems were matched on PWSID first and on the normalized name when the PWSID didn't match. Stowe Fire District 2 was matched by hand (see below).
- **SDWIS columns:** `sdwis_name`, `sdwis_activity` (A = active, I = inactive) and `sdwis_owner_type` (L = local government, P = private, M = public/private) are looked up in `data/sdwis_vt.json`. In master rows they describe the master's PWSID. In site-only rows they describe the site's PWSID.

## Summary

| `comparison` | Count | Meaning |
|---|---|---|
| `in_both` | 66 | On the site and in the master (62 by PWSID, 3 by name, 1 by hand) |
| `master_only` | 20 | Non-municipal systems in the master but not on the site |
| `master_only_municipal` | 55 | Systems the master types as Municipal |
| `site_only` | 20 | On the site but not in the master |

Most of the additions are municipal water departments (e.g. Montpelier, Winooski, Middlebury DPW). The site covers only fire districts and water districts, so these were left out on purpose. SDWIS lists 54 of them as local government and 1 as private (Lyman Meadows). Whether to add them is a scope decision.

## In the master, not on the site (non-municipal)

### Fire districts

| System | PWSID | Town | RPC | Notes |
|---|---|---|---|---|
| Randolph Fire District No. 1 | VT0005177 | Randolph | TRORC | Water and wastewater, pop. 1,138. SDWIS name is RANDOLPH CENTER WATER SYSTEM. Best candidate to add to the roster. |
| Ferrisburgh Fire District #1 | none | Panton | ACRPC | Master says "N/A - not in state list". It may not run a public water system. |

### Typed "Water District" in the master

Of these 16, 15 are in the TRORC region (the exception is Albany, in NVDA). Their names and SDWIS owner types suggest most are town or village departments, incorporated villages, or private companies and co-ops rather than districts formed under 24 V.S.A. ch. 89. That suggests TRORC filled in the Type column differently from the other RPCs. Each needs to be checked before it's added as a district.

| System | PWSID | Town | SDWIS owner | Pop. |
|---|---|---|---|---|
| Albany Water System | VT0005188 | Albany | L | 200 |
| Bethel Water Dept | VT0005315 | Bethel | L | 1,929 |
| Bradford Village Water System | VT0005170 | Bradford | L | 1,512 |
| Chelsea Water System | VT0005638 | Chelsea | L | 562 |
| East Thetford Water Co. | VT0005184 | Thetford | P | 250 |
| Fairlee Town Water | VT0005174 | Fairlee | L | 967 |
| Hartford Water Dept | VT0005319 | Hartford | L | 7,600 |
| North Hartland Coop Water System Inc | VT0005322 | Hartland | P | 262 |
| Newbury Village Inc. | VT0005175 | Newbury | L | 480 |
| Post Mills Water System | VT0021014 | Thetford | not in SDWIS extract | 0 |
| Quechee Central | VT0005320 | Hartford | M | 2,262 |
| Randolph Village | VT0005179 | Randolph | L | 2,700 |
| Rochester Water System | VT0005328 | Rochester | L | 440 |
| Thetford Water Coop Inc | VT0005181 | Thetford | P | 115 |
| Union Water Co | VT0005182 | Thetford | P | 61 |
| Wells River Water System | VT0005176 | Newbury | L | 400 |

### Other

| System | PWSID | Town | Notes |
|---|---|---|---|
| Belvidere Water System (new) | VT0020543 | Belvidere | In the SDWIS extract, this PWSID belongs to BELVIDERE CENTRAL SCHOOL (inactive). The ID may have been reassigned, or the extract may be out of date. |
| Putney Water System | VT0020934 | Putney | The master's Type column holds the system name. Local government per SDWIS. |

## On the site, not in the master

These 20 are missing from the master, so it can't replace the site's list.

- **Champlain Water District** (VT0005092): the largest water district in the state. The CCRPC section of the master leaves it out.
- **NVDA-area fire districts:** Barnet FD 2, Burke FD 1, Danville FD 1, Lyn Haven FD 1, McIndoe Falls FD 3, Passumpsic FD 1, Peacham FD 1, Ryegate FD 2, Sheffield FD 1, St Johnsbury Center FD 1, Wheelock FD 1. All of them have active PWSIDs.
- **Others with PWSIDs:** East Calais FD 1 (VT0005262), Washington Fire District (VT0005185).
- **No PWSID on the site** (wastewater-only, unconfirmed, or no public water system): Bolton FD 1, Milton FD 1, Morristown Corners Water Corporation, North Branch FD 1, Sherburne FD 1, Williamstown Fire District.

### Town-level check for possible matches

Each site-only district was checked against the master's *System Location/ Town* column. Every other master column (service areas, mailing addresses, notes) was also searched for the district's town and distinctive name words. Only two possible matches turned up. Both are still pending review, so neither has been moved to `in_both` in the CSV.

| Site district | Possible master match | Evidence | Leaning |
|---|---|---|---|
| Williamstown Fire District (no PWSID) | Williamstown Water Dept, VT0005186, typed Municipal, serves Williamstown, pop. 985 | The district's charter (24 App. V.S.A. ch. 505 §2(a)) sets its limits as the whole Town of Williamstown, and the site lists it as providing water. The master names the Town Manager as superintendent, which points to a town department. If the district owns the system and the town runs it, they're the same entity. | Same |
| Morristown Corners Water Corporation (no PWSID) | Morrisville Water & Light, VT0005160, Municipal, "Downtown Morrisville", pop. 2,935 | Same town, but the corporation's charter (24 App. V.S.A. ch. 701 §1) defines it as 47 residential parcels. Morrisville Water & Light is the village utility. | Different |

The other 18 have no candidate anywhere in the master:

- **Caledonia County (11):** Barnet FD 2, McIndoe Falls FD 3, Passumpsic FD 1, Burke FD 1, Danville FD 1, Lyn Haven FD 1, Peacham FD 1, Ryegate FD 2, Sheffield FD 1, St Johnsbury Center FD 1, Wheelock FD 1. None of these towns appears in the master. Of 141 systems, East Hardwick FD 1 is the only one in Caledonia County. NVDA's 19 rows are otherwise all Orleans and Essex County, so it looks like NVDA's Caledonia County systems were never submitted. That's a hole in the master, not a naming mismatch.
- **Champlain Water District:** nothing in the master mentions Champlain. The only South Burlington row is South Burlington FD 1 (Queen City Park), which is already matched to a different site district. CCRPC seems to have left out the regional wholesaler.
- **East Calais FD 1, Washington FD:** Calais doesn't appear in the master. Washington appears only as a county name.
- **Bolton FD 1, Milton FD 1, North Branch FD 1 (Dover), Sherburne FD 1 (Killington):** none of these towns has a system in the master. Milton appears only in South Georgia FD's mailing address. None of the four has a PWSID on the site, and North Branch and Sherburne are wastewater-only, so a drinking-water list wouldn't be expected to include them.

## Disagreements and fills for matched districts

- **Stowe Fire District 2:** the master gives VT0005439, which SDWIS lists as *inactive* ("STOWE FD 2 GBII"). The site's "Stowe Fire District 2 Gold Brook Circle" uses the active VT0005168. Keep the site's ID.
- **PWSIDs the master can supply:** these three matched by name because the site has no PWSID for them. Check each against SDWIS before adding.
  - Edward Farrar Utility District: VT0005284
  - Highgate Fire District 1: VT0008276
  - Cold Brook Fire District Base Area: VT0005649

## Possible next steps

1. Add Randolph Fire District No. 1 to the roster.
2. Check the three PWSIDs above and add them to the site's records.
3. Ask TRORC how it assigned "Water District" in the Type column.
4. Confirm the Williamstown and Morristown Corners pairs above.
5. Ask NVDA whether its Caledonia County systems were left out on purpose, and ask CCRPC about Champlain Water District.
6. Decide whether municipal systems are in scope for the site.
7. The master also has contacts, connection counts, and concerns/vulnerability ratings for each system. These weren't compared here, but they could fill contact gaps in `data/vt_district_roster.csv`.
