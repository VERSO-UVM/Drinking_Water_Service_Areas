#!/usr/bin/env python3
"""
Fill the town-clerk contact sheet with authoritative names/emails/phones from
the Vermont Secretary of State's maintained Town Clerk contact spreadsheet.

WHY this source: Vermont town clerks are not reliably listed on 234 individual
town websites, and scraping/guessing emails at that scale produces a sheet
that's ~40% wrong. The SoS Elections Division publishes ONE maintained Excel
file of clerk contacts (updated as clerks report changes; the companion guide
was updated Jan 2026). That is the correct, authoritative source -- pull it,
don't scrape.

  SoS Town Clerk contact xlsx:
  https://outside.vermont.gov/dept/sos/Elections_Division/voters/vermont_town_clerk_contact_information.xlsx

WHAT it does:
  1. Downloads the SoS clerk xlsx (or reads a local copy via --sos).
  2. Normalizes town names and joins onto vt_town_clerk_contacts.csv.
  3. Fills clerk_name / clerk_email / clerk_phone / clerk_mailing_address,
     tags source = "VT SoS (Jan 2026)", flags any town that didn't match.

INPUTS:
  vt_town_clerk_contacts.csv   (the skeleton, from your existing URL data)
OUTPUT:
  vt_town_clerk_contacts_filled.csv

Run:
  pip install pip-system-certs requests pandas openpyxl
  python merge_clerk_contacts.py
  # or if you already downloaded the xlsx by hand:
  python merge_clerk_contacts.py --sos vermont_town_clerk_contact_information.xlsx
"""

import argparse, io, re, sys
import requests
import pandas as pd

SOS_URL = ("https://outside.vermont.gov/dept/sos/Elections_Division/voters/"
           "vermont_town_clerk_contact_information.xlsx")
SKELETON = "vt_town_clerk_contacts.csv"
OUT = "vt_town_clerk_contacts_filled.csv"


def split_name(s):
    """Return (base, kind) for a municipality name.

    Two traps this avoids:
      * The SoS spells them "Saint Johnsbury" while the skeleton uses
        "St. Johnsbury" -- fold both to "st".
      * Stripping the trailing City/Town word outright collapses the four
        City/Town pairs (Barre, Newport, Rutland, Saint Albans) onto one key,
        which silently hands the Town the City clerk's contact. Rutland Town is
        the 5-district town at the centre of this project, so that matters.
        Keep the distinction as `kind` instead of discarding it.
    """
    s = str(s).lower().strip()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\bsaint\b", "st", s)
    s = re.sub(r"\b(of|the)\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip()

    m = re.search(r"\b(city|town|village|gore)$", s)
    if m:
        return s[:m.start()].strip(), m.group(1)
    return s, ""


def norm_town(s):
    """Base key only, ignoring the City/Town suffix."""
    return split_name(s)[0]


KINDS = ("city", "town", "village", "gore")


def muni_key(name, muni_type=""):
    """Canonical (base, kind); kind is "" when nothing states it.

    An empty kind is a wildcard, not a default. The SoS writes most towns bare
    ("Addison", "Burlington") and only disambiguates where it must
    ("Rutland City" vs "Rutland Town"). Defaulting the bare ones to "town"
    would wrongly split Burlington -- a city -- from its own clerk, so an
    absent suffix has to match anything.
    """
    base, kind = split_name(name)
    if not kind:
        kind = str(muni_type).strip().lower()
    return base, (kind if kind in KINDS else "")


def load_sos(path_or_none):
    """Read the SoS workbook, locating the real header row.

    The published file carries four banner rows (title, agency, "Last Updated",
    accessibility note) before the actual column headers, so a plain read_excel
    picks up the title as the only named column and everything else as
    "Unnamed: N". Scan for the row containing the town column instead.
    """
    if path_or_none:
        blob = path_or_none
    else:
        r = requests.get(SOS_URL, timeout=120)
        r.raise_for_status()
        blob = io.BytesIO(r.content)

    raw = pd.read_excel(blob, header=None, dtype=str)

    header_row = None
    for i in range(min(20, len(raw))):
        cells = [str(v).strip().lower() for v in raw.iloc[i].tolist()]
        if "town name" in cells or "town" in cells:
            header_row = i
            break
    if header_row is None:
        print("Could not locate the header row in the SoS workbook.",
              file=sys.stderr)
        sys.exit(1)

    # "Last Updated: June 12, 2026" sits in the banner; keep it for provenance.
    stamp = ""
    for i in range(header_row):
        m = re.search(r"last updated:\s*(.+)", str(raw.iloc[i, 0]), re.I)
        if m:
            stamp = m.group(1).strip()
            break

    sos = raw.iloc[header_row + 1:].copy()
    sos.columns = [str(c).strip() for c in raw.iloc[header_row].tolist()]
    sos = sos.reset_index(drop=True)
    sos.attrs["stamp"] = stamp
    print(f"Header row {header_row}; file stamp: {stamp or 'unknown'}")
    return sos


def pick(cols, *cands):
    """Find the first column whose name contains any candidate substring."""
    low = {c.lower(): c for c in cols}
    for cand in cands:
        for lc, orig in low.items():
            if cand in lc:
                return orig
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sos", default=None, help="local path to the SoS clerk xlsx")
    args = ap.parse_args()

    skel = pd.read_csv(SKELETON, dtype=str).fillna("")
    sos = load_sos(args.sos).fillna("")
    print("SoS columns:", list(sos.columns))

    # Auto-detect the relevant SoS columns (header names vary year to year).
    c_town  = pick(sos.columns, "town name", "town", "municipal", "jurisdiction")
    c_first = pick(sos.columns, "first name")
    c_last  = pick(sos.columns, "last name")
    c_name  = pick(sos.columns, "clerk name", "official", "contact name")
    c_email = pick(sos.columns, "email", "e-mail")
    c_phone = pick(sos.columns, "phone number", "phone", "telephone")
    c_addr  = pick(sos.columns, "mailing address", "office address", "address")
    c_city  = pick(sos.columns, "mailing city", "office city")
    c_state = pick(sos.columns, "mailing state", "office state")
    c_zip   = pick(sos.columns, "mailing zip", "office zip")
    if not c_town:
        print("Could not find a town column in the SoS file. Inspect headers "
              "above and set c_town by hand.", file=sys.stderr)
        sys.exit(1)
    print(f"Using -> town:{c_town}  name:{c_name or f'{c_first}+{c_last}'}  "
          f"email:{c_email}  phone:{c_phone}  addr:{c_addr}")

    # Index the SoS rows by (base, kind) so Barre City and Barre Town stay apart.
    sos_by_key = {}
    sos_by_base = {}
    for _, r in sos.iterrows():
        base, kind = muni_key(r[c_town])
        if not base:
            continue
        sos_by_key.setdefault((base, kind), r)
        sos_by_base.setdefault(base, []).append((kind, r))

    def resolve(town, muni_type):
        """Exact kind match, then a bare SoS entry, then an unambiguous base."""
        base, kind = muni_key(town, muni_type)
        for probe in ((base, kind), (base, "")):
            if probe in sos_by_key:
                return sos_by_key[probe]
        bucket = sos_by_base.get(base, [])
        # Never let a lone City row stand in for a Town (or vice versa) --
        # Rutland Town and Rutland City have different clerks.
        if len(bucket) == 1 and bucket[0][0] in ("", kind):
            return bucket[0][1]
        return None

    def grab(row, col):
        if row is None or not col:
            return ""
        v = str(row.get(col, "")).strip()
        return "" if v.lower() == "nan" else v

    def clerk_name(k):
        """SoS splits the clerk across First/Last; fall back to a single col."""
        if c_name:
            return grab(k, c_name)
        return " ".join(p for p in (grab(k, c_first), grab(k, c_last)) if p)

    def mailing(k):
        street = grab(k, c_addr)
        city = grab(k, c_city)
        state = grab(k, c_state)
        zipc = grab(k, c_zip)
        tail = " ".join(p for p in (state, zipc) if p)
        locality = ", ".join(p for p in (city, tail) if p)
        return ", ".join(p for p in (street, locality) if p)

    stamp = sos.attrs.get("stamp", "")
    source_label = f"VT SoS clerk file ({stamp})" if stamp else "VT SoS clerk file"

    matched = 0
    for i, row in skel.iterrows():
        hit = resolve(row["town"], row.get("municipality_type", ""))
        if hit is not None:
            matched += 1
            skel.at[i, "clerk_name"]  = clerk_name(hit)
            skel.at[i, "clerk_email"] = grab(hit, c_email)
            skel.at[i, "clerk_phone"] = grab(hit, c_phone)
            skel.at[i, "clerk_mailing_address"] = mailing(hit)
            skel.at[i, "source"] = source_label
        else:
            # Villages, gores and unincorporated places have no town clerk in
            # the SoS town list -- expected, not an error.
            skel.at[i, "notes"] = "no SoS match - village/gore/unincorporated or name variant"

    # The skeleton is missing some municipalities the SoS does carry -- notably
    # Rutland Town, the five-district town this project cares most about, which
    # otherwise falls through to Rutland City's clerk. Append what it lacks.
    used = {muni_key(r["town"], r.get("municipality_type", ""))
            for _, r in skel.iterrows()}
    skeleton_bases = {b for b, _ in used}
    added = []
    for _, r in sos.iterrows():
        base, kind = muni_key(r[c_town])
        if not base or (base, kind) in used:
            continue
        # Only add a same-base row when the SoS explicitly names a different
        # kind ("Rutland Town" alongside the skeleton's Rutland City). A bare
        # SoS name for a base we already have is the same municipality.
        if base in skeleton_bases and not kind:
            continue
        used.add((base, kind))
        added.append({
            "town": str(r[c_town]).strip(),
            "municipality_type": kind.title(),
            "county": grab(r, pick(sos.columns, "county")) or "",
            "town_website": "",
            "clerk_name": clerk_name(r),
            "clerk_email": grab(r, c_email),
            "clerk_phone": grab(r, c_phone),
            "clerk_mailing_address": mailing(r),
            "source": source_label,
            "notes": "added from SoS list; not in original skeleton",
        })

    if added:
        skel = pd.concat([skel, pd.DataFrame(added)], ignore_index=True)
        print(f"Added from SoS (absent from skeleton): {len(added)} "
              f"-> {', '.join(a['town'] for a in added)}")

    skel = skel.sort_values("town").reset_index(drop=True)
    skel.to_csv(OUT, index=False)
    print(f"\nWrote {OUT}")
    print(f"Matched to SoS: {matched} of {len(skel)}")
    print(f"Emails filled:  {(skel['clerk_email']!='').sum()}")
    print(f"Unmatched (need review): {(skel['source']=='').sum()}")


if __name__ == "__main__":
    main()
