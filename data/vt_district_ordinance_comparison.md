# Ordinance & bylaws comparison: what's common, what differs

A close read of every substantive document in the ordinance corpus — the ordinances, bylaws, policies, permits, rate documents, and the one CCR that has usable extracted text. Routine meeting minutes are excluded; they were skimmed but not analyzed for content.

**Coverage caveat.** Of 326 documents in `data/vt_district_ordinance_text.json`, only 103 (32%) have extractable text — 220 are scans with no text layer, concentrated in Norwich's older minutes. This analysis covers the **17 substantive, non-minutes documents** that do have text, spanning **7 districts**: Castleton FD 1, Castleton FD 3, East Hardwick FD 1, North Branch FD 1, Brandon FD 1, Cold Brook FD 1, Wallingford FD 1, and Wilmington Water District. It is a close read of what's readable today, not a statistical sample of the full 81-district inventory. OCR would materially change which districts are represented, especially for governance content buried in Norwich's minutes.

## Documents reviewed

| District | Document | Type | Length |
| --- | --- | --- | --- |
| Castleton FD 1 | Water Ordinance (Apr. 2014) | ordinance | 41,626 chars, 24 pp |
| East Hardwick FD 1 | Governing Ordinance v1.1 (Jul. 2026) | ordinance | 31,113 chars, 10 pp |
| North Branch FD 1 | Ordinances (Jan. 2022) | ordinance | 48,188 chars, 22 pp |
| Brandon FD 1 | By-Laws (Jan. 2023, amended from 1887) | bylaws | 15,858 chars |
| East Hardwick FD 1 | By-Laws (amended May 2026) | bylaws | 11,127 chars |
| East Hardwick FD 1 | Procurement Policy (Feb. 2024) | policy | 19,842 chars |
| East Hardwick FD 1 | Conflicts of Interest & Ethical Conduct Policy (Feb. 2024) | policy | 14,017 chars |
| East Hardwick FD 1 | Privacy Policy (Jul. 2026) | policy | 2,491 chars |
| Castleton FD 3 | Water Rate Policy (2007, rev. 2010) | rates | 4,452 chars |
| North Branch FD 1 | Rate History (spreadsheet export) | rates | 1,357 chars |
| North Branch FD 1 | 2024/25 Budget | budget | 1,834 chars |
| Wallingford FD 1 | 2025-2026 Lodge Rates | rates | 992 chars |
| Wallingford FD 1 | 2027 Lodge Rates | rates | 987 chars |
| Cold Brook FD 1 | Conditional Use Permit, off Haystack Rd (2012-064) | permit | 15,194 chars |
| Cold Brook FD 1 | Conditional Use Permit, off East Village Rd (2012-065) | permit | 13,628 chars |
| Wilmington Water District | Consumer Confidence Report Certificate 2025 | ccr | 15,471 chars |
| East Hardwick FD 1 | (Hardwick Historical Society Journal — not a governance document, excluded from analysis) | other | 45,948 chars |

## What's common across districts

**A shared governance vocabulary and template.** Every governance document — regardless of district — names its governing board the **"Prudential Committee."** Brandon's and East Hardwick's bylaws are structurally near-identical and in places verbatim: both cite *"Title 20, V.S.A. Sec. 2601-2608"* word-for-word for their powers, and both organize as Purpose → Powers → Office → Meetings → Prudential Committee → Officers → Rates and Revenues → Operating Rules → Tax Exemption → Amendment, in that exact order. This is almost certainly a shared drafting template (VLCT or VRWA model bylaws) that districts adopt and localize rather than independent legal drafting.

**Enforcement is uniformly civil.** Every ordinance routes violations through Vermont's Judicial Bureau as civil (not criminal) matters under **24 V.S.A. §§ 1974a and 1977 et seq.** Penalty caps differ (Castleton: $250/offense; North Branch: $800/offense, citing the statutory maximum) but the mechanism — written notice, a cure period, a per-day-continuing violation, a waiver-fee option — is the same pattern in both.

**The same financial and legal scaffolding recurs everywhere:**
- All district property is **tax-exempt**.
- All districts hold **eminent domain** power.
- Rates are set to cover **operations, debt service (bond repayment), and reserve funds** — never described as pure cost-recovery.
- Delinquent charges become **liens on real estate** under 24 V.S.A. Ch. 129, enforced like a tax lien, not ordinary debt collection.
- Every document defers to state law when it conflicts: "the more strict shall apply" (Castleton) or "the statute shall govern" (North Branch).

## Where they differ sharply

### 1. How much is actually written down varies by an order of magnitude

Castleton's 2014 ordinance is comprehensive in structure — 15 articles, a professional table of contents — but roughly **40 of its ~90 sections say only "(SEE POLICY DOCUMENT)" or "(SEE CONSTRUCTION STANDARDS)."** Those referenced documents are not in this corpus and may not be public. The ordinance is a skeleton over rules we cannot see.

East Hardwick's 2026 ordinance is the opposite: fully self-contained. It spells out an 8% late fee, a 1%/month interest rate, a 30/60/90/180-day collection escalation ladder, a requirement that the second notice be "printed on pink paper," and a hard rule against shutoffs between November 1 and March 31. Nothing is deferred to a document we don't have.

**Practical implication:** any TMF (technical/managerial/financial) capacity assessment based on "does the district have a written ordinance" needs to also ask "does the ordinance actually contain the rule, or point somewhere else?" Castleton and East Hardwick would score identically on the first question and very differently on the second.

### 2. "Fire District" hides at least three different statutory creatures

- **North Branch FD 1's entire ordinance (48,000 characters) is a sewer/wastewater pretreatment ordinance** — industrial discharge limits (pH 5.0–8.5, BOD, temperature caps, grease trap requirements), manhole permitting, EPA-style pretreatment standards. There is no water-service content in it at all. It cites **24 V.S.A. Ch. 105 (Sewer Districts)** and **Ch. 91 (Water Districts)** as parallel authorities and describes itself as a "consolidated district" with town-like powers, formed 1972.
- **Castleton FD 1** cites **24 V.S.A. Ch. 89** specifically (the fire-district-as-water-utility chapter).
- **Brandon FD 1 and East Hardwick FD 1** both cite **20 V.S.A. Ch. 171** (the general fire-district incorporation statute) — even though East Hardwick runs no fire department at all.

Four districts, three distinct statutory bases, all filed identically as "Fire District" in the inventory. This confirms and sharpens the legal-form finding from the manual website reviews (Westford as a non-profit corporation, Stowe FD 2 as a homeowners' association): the "Fire District" label in Vermont covers meaningfully different legal instruments, and neither the name nor the VRWA list distinguishes them.

### 3. Governance scope is not standardized

Brandon's Prudential Committee runs **both a Water Department and a Fire Department**, appointing six fire officers (Chief, Assistant Chief, two Captains, two Lieutenants) plus a Water Superintendent. East Hardwick runs water only, with no fire department function anywhere in its bylaws. This mirrors what the project lead found manually at Royalton (water + fire department + rescue squad) — district remit varies from "just water" to "water and emergency services," and nothing in the roster currently records which.

### 4. Inter-district wholesale relationships exist and are invisible elsewhere in the data

Castleton FD 3's rate policy has a line item for **purchasing water wholesale from Castleton FD 1** — its quarterly rate calculation explicitly multiplies gallons used by "the CFD#1 rate in effect for each of the months." This is a real infrastructure dependency between two districts already in the 81-district inventory, and it does not appear in the crosswalk, the roster, or anywhere else. There may be other consecutive/wholesale relationships hiding the same way.

### 5. Financial trajectories are readable directly from rate history

North Branch's rate table shows price per thousand gallons climbing from ~$16 (2011) to a peak of **$43.17** (Spring 2020), then dropping and flattening at exactly **$25.06 with a 0% bond rate from 2022 onward** — a visible signature of the bond being paid off around 2022. This kind of document, if collected systematically, could support a project-wide affordability or capital-cycle analysis.

### 6. "Rates" documents aren't always water rates

Wallingford FD 1's two "rate" documents are not water rates — they are **rental rates for a community lodge** the district owns and rents out (386 Lodge Lane: $1,200–$2,600/weekend for the 2025-2027 seasons). Districts can hold non-water revenue-generating assets that the roster doesn't currently track. Any future document-type taxonomy should not assume "rates" means water rates.

### 7. Document genre varies by who actually authored the document

Not every document in the corpus is district self-governance:

- **Cold Brook FD 1's "permits"** are Town of Wilmington Development Review Board findings — third-party zoning/land-use adjudications, not documents the district wrote. They show the district as a land-use applicant, with named abutter objections (well-contamination concerns, construction noise) and formal DRB conditions of approval.
- **Wilmington Water District's CCR certificate** is a Vermont DEC compliance form, not district-authored content — a signed attestation that the district distributed its Consumer Confidence Report, not the report itself.

Treating all 326 corpus documents as one genre — "district ordinances" — understates how differently these were produced, who controls their content, and how much weight each should carry in a governance assessment.

## Open questions this raises

1. **Which other "Fire Districts" are actually sewer districts, water-only districts, or combined water+fire+other entities?** Only a full-text read surfaces this; the name alone does not. Combined with the SoS legal-form question (Westford as non-profit corp, Stowe FD 2 as HOA), district *type* looks like a genuinely unresolved dimension of the 81-district inventory.
2. **How many districts' ordinances defer to a "Policy Document" or "Construction Standards" we don't have?** Castleton FD 1 is a confirmed case; there may be others once more full-text ordinances come in.
3. **Are there other wholesale/consecutive-system relationships between districts in this inventory**, comparable to Castleton FD 3 buying from Castleton FD 1? This would need to be checked against SDWIS's own consecutive-system flags if available.
4. **Should the ordinance registry (`vt_district_ordinances.csv`) track a `related_district` or `wholesale_supplier` field?** Castleton FD 3's case suggests this relationship is worth modeling explicitly rather than leaving it buried in rate-policy prose.
