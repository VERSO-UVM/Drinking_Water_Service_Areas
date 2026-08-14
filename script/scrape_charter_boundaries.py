#!/usr/bin/env python3
"""
Scrape every chapter of Vermont Statutes Title 24 Appendix (Municipal Charters)
and pull out the sections that describe a district's boundaries -- verbatim.

WHY THE WHOLE APPENDIX, NOT JUST THE DISTRICT CHAPTERS:
  The dedicated fire/water district chapters (the 500s and 700s) are only part of
  the story. District provisions also live inside TOWN charters. Chapter 127
  (Town of Middlebury) carries "§ 1505. Fire District No. 1 East Middlebury",
  which no scan of the 500s would ever reach. So every chapter is fetched.

WHAT COUNTS AS A HIT:
  Three independent rules, recorded per row in `match_reason`, because a boundary
  description is not reliably filed under a heading called "Boundaries":
    boundary_heading  -- heading says Boundaries / Limits / Territory / Description
    district_heading  -- heading names a fire/water/sewer/lighting district
    boundary_language -- body contains "bounded", "beginning at", "metes and
                         bounds", "land records", "corporate limits", etc.

THE TEXT IS UNEDITED:
  `section_text` is the statute's own words, verbatim. Tags are stripped and HTML
  entities decoded (unavoidable), and the source's line-wrapping indentation --
  layout, not content -- is normalized so each paragraph is one line. No
  summarizing, no truncation, no rewording. Paragraphs are separated by a blank
  line. `char_count` lets you spot anything suspiciously short.

OUTPUTS:
  data/vt_charter_boundary_sections.csv  one row per matching section
  data/vt_charter_chapters.csv           all 114 chapters, hit or not

Run:
  python script/scrape_charter_boundaries.py
  python script/scrape_charter_boundaries.py --chapter 507   # single chapter
"""

import argparse
import csv
import html as htmllib
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT_SECTIONS = ROOT / "data" / "vt_charter_boundary_sections.csv"
OUT_CHAPTERS = ROOT / "data" / "vt_charter_chapters.csv"

INDEX_URL = "https://legislature.vermont.gov/statutes/title/24APPENDIX"
CHAPTER_URL = "https://legislature.vermont.gov/statutes/fullchapter/24APPENDIX/{chap}"
SECTION_URL = "https://legislature.vermont.gov/statutes/section/24APPENDIX/{chap}/{sec}"

TIMEOUT = 90
PAUSE = 0.4  # be polite to the legislature's server

# The index nests <span> tags between "Chapter" and the number, which is why a
# plain `Chapter NNN: Name` regex matches nothing on this page.
INDEX_RE = re.compile(
    r'href="/statutes/chapter/24APPENDIX/([0-9A-Za-z]+)">\s*Chapter\s*'
    r'<span[^>]*>([^<]+)</span>\s*:\s*<span[^>]*>([^<]*)</span>',
    re.S,
)

# Anchor on the bolded section headings themselves rather than on the enclosing
# <ul>. Chapters that have subchapters close `statutes-detail` immediately and
# reopen a `statutes-list`, so keying off that container finds nothing for them.
HEADING_RE = re.compile(r"<b>\s*(§[^<]*)</b>", re.S)

# "limits" and "description of" have to be qualified: bare forms pull in "Debt
# limits", "Limits on terms of office", and "Description of officers".
BOUNDARY_HEADING = re.compile(
    r"(\bboundar|\bbounds\b|\bterritor|\bmetes\b|"
    r"\b(?:corporate|village|town|city|district|municipal|territorial)\s+limits\b|"
    r"\blimits\s+of\s+the\s+(?:village|town|city|district)\b|"
    r"\bdescription\s+of\s+(?:the\s+)?boundar)", re.I)
DISTRICT_HEADING = re.compile(
    r"\b(fire district|water district|sewer district|lighting district|"
    r"water system|waterworks|water works|incorporated district|"
    r"consolidated district)\b", re.I)
BOUNDARY_LANGUAGE = re.compile(
    r"(beginning at a|beginning at the|metes and bounds|thence (?:north|south|"
    r"east|west|along|running)|bounded (?:on|by|and)|corporate limits|"
    r"land records of|as recorded in book|shall be as recorded|"
    r"boundaries of the (?:district|fire district)|"
    r"territorial limits|shall comprise|shall include all)", re.I)


CACHE_DIR = None  # set from --cache-dir; keeps re-runs off the state's server


def get(url, cache_key=None):
    cached = None
    if CACHE_DIR and cache_key:
        cached = CACHE_DIR / f"{cache_key}.html"
        if cached.exists():
            return cached.read_text(encoding="utf-8")

    for attempt in range(4):
        try:
            r = requests.get(url, timeout=TIMEOUT)
            r.raise_for_status()
            # Bytes are UTF-8 (the section sign arrives as C2 A7); decode
            # explicitly rather than trusting requests' guess.
            text = r.content.decode("utf-8", errors="replace")
            if cached is not None:
                cached.parent.mkdir(parents=True, exist_ok=True)
                cached.write_text(text, encoding="utf-8")
            return text
        except requests.RequestException:
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))


def clean(fragment):
    """HTML fragment -> the statute's own words, paragraphs preserved."""
    # Paragraph and break tags become blank lines; everything else just goes.
    s = re.sub(r"(?i)</p\s*>|<br\s*/?>", "\n\n", fragment)
    s = re.sub(r"<[^>]+>", "", s)
    s = htmllib.unescape(s)
    s = s.replace("\xa0", " ")

    paragraphs = []
    for block in s.split("\n\n"):
        # The source hard-wraps and indents for layout; rejoin into one line
        # per paragraph without altering a single word.
        joined = " ".join(block.split())
        if joined:
            paragraphs.append(joined)
    return "\n\n".join(paragraphs)


def parse_index():
    page = get(INDEX_URL, "index")
    chapters = []
    for _href, num, title in INDEX_RE.findall(page):
        chapters.append({
            "chapter": num.strip(),
            "chapter_title": htmllib.unescape(title).strip(),
        })
    if not chapters:
        sys.exit("Parsed 0 chapters from the index -- the markup changed.")
    return chapters


def municipality(title):
    """'City of Barre' -> 'Barre'; district names keep their own name."""
    m = re.match(r"\s*(?:City|Town|Village)\s+of\s+(.+)", title, re.I)
    return m.group(1).strip() if m else title.strip()


def muni_type(title):
    m = re.match(r"\s*(City|Town|Village)\s+of\s+", title, re.I)
    if m:
        return m.group(1).title()
    for kind in ("Fire District", "Water District", "Utility District",
                 "Sewer District", "Recreational District", "Authority",
                 "Water Corporation", "District"):
        if kind.lower() in title.lower():
            return kind
    return "Other"


def parse_sections(page):
    """Yield (section_number, heading, body_text) for each § in the chapter."""
    heads = list(HEADING_RE.finditer(page))
    for idx, head in enumerate(heads):
        heading_raw = clean(head.group(1))
        if not heading_raw:
            continue

        # The body runs to the next section heading, or to the end of this
        # list item -- whichever comes first. The `</li>` cut keeps the page's
        # trailing navigation out of the final section on the page.
        stop = heads[idx + 1].start() if idx + 1 < len(heads) else len(page)
        chunk = page[head.end():stop]
        end_li = chunk.find("</li>")
        if end_li != -1:
            chunk = chunk[:end_li]

        body = clean(chunk)
        num_m = re.match(r"\s*§?\s*([0-9A-Za-z.\-]+)\s*\.\s*(.*)", heading_raw)
        if num_m:
            number, title = num_m.group(1), num_m.group(2).strip()
        else:
            number, title = "", heading_raw.lstrip("§ ").strip()
        yield number, title, body


def section_link(chap, number):
    if not number:
        return ""
    # Section pages use a zero-padded id: § 1505 -> 01505.
    core = number.replace(".", "")
    return SECTION_URL.format(chap=chap, sec=core.zfill(5)) if core.isdigit() \
        else SECTION_URL.format(chap=chap, sec=core)


def classify(title, body):
    reasons = []
    if BOUNDARY_HEADING.search(title):
        reasons.append("boundary_heading")
    if DISTRICT_HEADING.search(title):
        reasons.append("district_heading")
    if BOUNDARY_LANGUAGE.search(body):
        reasons.append("boundary_language")
    return reasons


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chapter", help="scrape a single chapter number")
    ap.add_argument("--cache-dir", help="cache chapter HTML here; re-runs "
                                        "reclassify without refetching")
    args = ap.parse_args()

    global CACHE_DIR
    if args.cache_dir:
        CACHE_DIR = Path(args.cache_dir)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    chapters = parse_index()
    if args.chapter:
        chapters = [c for c in chapters if c["chapter"] == args.chapter]
        if not chapters:
            sys.exit(f"Chapter {args.chapter} is not in the index.")
    print(f"Chapters to scrape: {len(chapters)}")

    rows, chapter_rows = [], []
    for i, ch in enumerate(chapters, start=1):
        chap = ch["chapter"]
        title = ch["chapter_title"]
        try:
            page = get(CHAPTER_URL.format(chap=chap), f"ch{chap}")
        except Exception as exc:
            print(f"  [{i:3}/{len(chapters)}] {chap} {title[:38]:38} FETCH ERROR {exc}")
            chapter_rows.append({**ch, "municipality": municipality(title),
                                 "municipality_type": muni_type(title),
                                 "sections": 0, "boundary_sections": 0,
                                 "status": f"fetch_error: {exc}"})
            continue

        n_sections = n_hits = 0
        for number, sec_title, body in parse_sections(page):
            n_sections += 1
            reasons = classify(sec_title, body)
            if not reasons:
                continue
            n_hits += 1
            rows.append({
                "municipality": municipality(title),
                "municipality_type": muni_type(title),
                "chapter": chap,
                "chapter_title": title,
                "section_number": number,
                "section_heading": sec_title,
                "match_reason": "|".join(reasons),
                "char_count": len(body),
                "section_url": section_link(chap, number),
                "section_text": body,
            })

        chapter_rows.append({**ch, "municipality": municipality(title),
                             "municipality_type": muni_type(title),
                             "sections": n_sections,
                             "boundary_sections": n_hits,
                             "status": "ok"})
        flag = f"{n_hits:>2} hit" if n_hits else "     -"
        print(f"  [{i:3}/{len(chapters)}] {chap} {title[:40]:40} "
              f"{n_sections:>3} sections  {flag}")
        if not (CACHE_DIR and (CACHE_DIR / f"ch{chap}.html").exists()):
            time.sleep(PAUSE)

    OUT_SECTIONS.parent.mkdir(parents=True, exist_ok=True)
    fields = ["municipality", "municipality_type", "chapter", "chapter_title",
              "section_number", "section_heading", "match_reason", "char_count",
              "section_url", "section_text"]
    with OUT_SECTIONS.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    cfields = ["chapter", "chapter_title", "municipality", "municipality_type",
               "sections", "boundary_sections", "status"]
    with OUT_CHAPTERS.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=cfields)
        w.writeheader()
        w.writerows(chapter_rows)

    hit_chapters = sum(1 for c in chapter_rows if c["boundary_sections"])
    print(f"\nWrote {OUT_SECTIONS.relative_to(ROOT)} ({len(rows)} sections)")
    print(f"Wrote {OUT_CHAPTERS.relative_to(ROOT)} ({len(chapter_rows)} chapters)")
    print(f"{hit_chapters} of {len(chapter_rows)} chapters had a matching section.")


if __name__ == "__main__":
    main()
