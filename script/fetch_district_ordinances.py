"""
Build the district ordinance & policy corpus.

Two products come out of one pipeline, for two different audiences:

  1. END USER -- docs/data/ordinances.json, metadata and links only. Feeds the
     "Ordinances & policy" section of the Details dialog on the site.
  2. RESEARCH -- data/vt_district_ordinance_text.json, the same documents with
     full extracted text, so the ordinances can be searched and compared as a
     corpus in their own right. Not shipped to docs/ -- it is large, and it is
     a research artifact rather than something the site renders.

The registry data/vt_district_ordinances.csv is the hand-maintained input:
one row per known document. `--discover` proposes new rows by crawling the
district websites we already know about; a human triages them before they
count. Nothing is published straight from discovery.

Usage:
  python script/fetch_district_ordinances.py              # fetch + extract
  python script/fetch_district_ordinances.py --discover   # propose new rows
  python script/fetch_district_ordinances.py --force      # ignore the cache
"""

import argparse
import csv
import hashlib
from html import unescape as html_unescape
import json
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "data" / "vt_district_ordinances.csv"
WEBSITES = ROOT / "data" / "vt_district_websites.csv"
CACHE_DIR = ROOT / "data" / "ordinances"
CORPUS = ROOT / "data" / "vt_district_ordinance_text.json"
SITE_OUT = ROOT / "docs" / "data" / "ordinances.json"

FIELDS = ["district_name", "doc_type", "title", "url", "adopted",
          "source_page", "notes"]

# Municipal sites routinely refuse a bare python-requests UA.
UA = ("Mozilla/5.0 (compatible; VT-district-boundaries/1.0; "
      "+https://github.com/VERSO-UVM/Drinking_Water_Service_Areas)")
HEADERS = {"User-Agent": UA}
TIMEOUT = 60
PAUSE = 1.0          # seconds between requests to the same host

# Above this many candidates, we are crawling a town's archive rather than a
# district's documents, so the whole site is skipped rather than half-filed.
PER_SITE_CAP = 40

# A PDF that yields fewer than this many characters is almost certainly a scan.
OCR_THRESHOLD = 200

# "24 V.S.A. Chapter 89, Section 3315", "24 V.S.A. § 3315"
VSA_RE = re.compile(
    r"\d{1,2}\s*V\.?\s*S\.?\s*A\.?[^.;)\n]{0,60}?(?:§+\s*[\d-]+|"
    r"Chapter\s+\d+(?:,?\s*Section\s+[\d-]+)?)",
    re.I)

# Words that mark a linked PDF as worth a human look during discovery.
INTERESTING = re.compile(
    r"ordinance|polic|rule|regulation|rate|fee|tariff|bylaw|by-law|charter|"
    r"annual\s*report|budget|warning|minutes|capital|asset\s*management|"
    r"water\s*quality|ccr|consumer\s*confidence|permit|plan",
    re.I)

# Same-host pages worth one extra hop when the landing page holds no PDFs.
RECORDS_PAGE = re.compile(
    r"document|minute|report|ordinance|polic|rule|regulation|rate|fee|"
    r"bylaw|by-law|archive|meeting|budget|financ|water|resource|about|form",
    re.I)

# Filenames that are plainly not district records, even on a district page.
NOT_A_RECORD = re.compile(
    r"logo|banner|header|footer|icon|thumb|sprite|favicon|"
    r"brochure|flyer|poster|map-?legend|privacy|accessibility|"
    r"newsletter-?signup|subscribe",
    re.I)

PDF_HREF = re.compile(r'href=["\']([^"\']+\.pdf[^"\']*)["\']', re.I)
ANCHOR = re.compile(r'<a\b[^>]*href=["\']([^"\']+\.pdf[^"\']*)["\'][^>]*>(.*?)</a>',
                    re.I | re.S)
TAG = re.compile(r"<[^>]+>")

# https://drive.google.com/file/d/<id>/view?usp=sharing
DRIVE_FILE = re.compile(r"drive\.google\.com/file/d/([A-Za-z0-9_-]+)", re.I)
DRIVE_OPEN = re.compile(r"drive\.google\.com/open\?id=([A-Za-z0-9_-]+)", re.I)


def resolve_url(url):
    """Share links -> something curl-able. Everything else passes through."""
    m = DRIVE_FILE.search(url) or DRIVE_OPEN.search(url)
    if m:
        return f"https://drive.google.com/uc?export=download&id={m.group(1)}"
    return url


def clean_text(s):
    """Normalise the mojibake that municipal PDF exports are full of."""
    return (s.replace("�", "'")      # smart quote lost in extraction
             .replace("’", "'")
             .replace("“", '"').replace("”", '"')
             .replace("–", "-").replace("—", "--")
             .replace("\xa0", " "))


def load_registry():
    if not REGISTRY.exists():
        return []
    with REGISTRY.open(encoding="utf-8-sig") as fh:
        return [r for r in csv.DictReader(fh) if r.get("url", "").strip()]


def write_registry(rows):
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    with REGISTRY.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for r in sorted(rows, key=lambda r: (r["district_name"], r["title"])):
            w.writerow({k: r.get(k, "") for k in FIELDS})


def doc_id(url):
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]


def fetch(url, session):
    r = session.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return r


def extract_pdf(path):
    """(text, pages, extractor). Tries PyMuPDF, falls back to pdfplumber."""
    try:
        import fitz
        with fitz.open(path) as doc:
            text = "\n".join(p.get_text() for p in doc)
            if len(text.strip()) >= OCR_THRESHOLD:
                return text, doc.page_count, "pymupdf"
            pages = doc.page_count
    except Exception as exc:                      # noqa: BLE001
        print(f"      pymupdf failed: {exc}")
        pages = 0

    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            text = "\n".join(p.extract_text() or "" for p in pdf.pages)
            return text, len(pdf.pages), "pdfplumber"
    except Exception as exc:                      # noqa: BLE001
        print(f"      pdfplumber failed: {exc}")
    return "", pages, "none"


def build(force=False):
    rows = load_registry()
    if not rows:
        sys.exit(f"No documents in {REGISTRY.relative_to(ROOT)}. "
                 f"Add rows, or run with --discover.")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    docs = []

    for i, row in enumerate(rows, 1):
        url = row["url"].strip()
        did = doc_id(url)
        cached = CACHE_DIR / f"{did}.pdf"
        print(f"  [{i}/{len(rows)}] {row['district_name']} -- {row['title'][:52]}")

        if cached.exists() and not force:
            blob = cached.read_bytes()
        else:
            try:
                resp = fetch(resolve_url(url), session)
            except Exception as exc:              # noqa: BLE001
                print(f"      FETCH FAILED: {exc}")
                docs.append({**meta(row, did, url), "status": f"fetch_failed: {exc}"})
                continue
            blob = resp.content
            ctype = resp.headers.get("content-type", "")
            if blob[:5] != b"%PDF-":
                # Drive answers a restricted file with its sign-in page, HTTP 200.
                if b"Sign-in" in blob[:4000] or b"accounts.google.com" in blob[:4000]:
                    print("      NOT PUBLIC: Drive returned a sign-in page")
                    docs.append({**meta(row, did, url),
                                 "status": "not_public: requires Google sign-in"})
                    continue
                if "pdf" not in ctype.lower():
                    print(f"      not a PDF (content-type {ctype})")
                    docs.append({**meta(row, did, url), "status": f"not_pdf: {ctype}"})
                    continue
            cached.write_bytes(blob)
            time.sleep(PAUSE)

        text, pages, extractor = extract_pdf(cached)
        text = clean_text(text)
        refs = sorted({re.sub(r"\s+", " ", m.group(0)).strip()
                       for m in VSA_RE.finditer(text)})
        needs_ocr = len(text.strip()) < OCR_THRESHOLD

        print(f"      {pages} pages, {len(text):,} chars, {extractor}"
              + (", NEEDS OCR" if needs_ocr else "")
              + (f", {len(refs)} statutory refs" if refs else ""))

        docs.append({
            **meta(row, did, url),
            "status": "ok" if not needs_ocr else "needs_ocr",
            "sha256": hashlib.sha256(blob).hexdigest(),
            "bytes": len(blob),
            "pages": pages,
            "chars": len(text),
            "extractor": extractor,
            "needs_ocr": needs_ocr,
            "statutory_refs": refs,
            "text": text,
        })

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    CORPUS.write_text(json.dumps(
        {"generated": stamp, "document_count": len(docs), "documents": docs},
        indent=1), encoding="utf-8")
    print(f"\n  wrote {CORPUS.relative_to(ROOT)} "
          f"({len(docs)} documents, {CORPUS.stat().st_size/1024:,.0f} KB)")

    # The site gets everything except the text.
    light = [{k: v for k, v in d.items() if k != "text"} for d in docs]
    SITE_OUT.parent.mkdir(parents=True, exist_ok=True)
    SITE_OUT.write_text(json.dumps({"generated": stamp, "documents": light},
                                   separators=(",", ":")), encoding="utf-8")
    print(f"  wrote {SITE_OUT.relative_to(ROOT)} "
          f"({SITE_OUT.stat().st_size/1024:,.0f} KB, no full text)")

    ok = sum(1 for d in docs if d.get("status") == "ok")
    ocr = sum(1 for d in docs if d.get("needs_ocr"))
    failed = len(docs) - ok - ocr
    words = sum(len(d.get("text", "").split()) for d in docs)
    print(f"\n  {ok} extracted, {ocr} need OCR, {failed} failed. "
          f"{words:,} words in the corpus.")


def meta(row, did, url):
    return {
        "doc_id": did,
        "district_name": row["district_name"].strip(),
        "doc_type": row.get("doc_type", "").strip() or "other",
        "title": row.get("title", "").strip() or Path(urlparse(url).path).name,
        "url": url,
        "adopted": row.get("adopted", "").strip(),
        "source_page": row.get("source_page", "").strip(),
        "notes": row.get("notes", "").strip(),
        "fetched": date.today().isoformat(),
        # Defaults so every record carries the same keys, whether or not the
        # fetch succeeded. Consumers should never have to guard for absence.
        "sha256": "",
        "bytes": 0,
        "pages": 0,
        "chars": 0,
        "extractor": "",
        "needs_ocr": False,
        "statutory_refs": [],
        "text": "",
    }


def discover(limit=None, depth=2):
    """Crawl known district websites for candidate PDFs.

    Depth 1 is the district's landing page. Depth 2 follows same-host links
    that look like a records page, because most districts keep documents one
    click in rather than on the front page.
    """
    if not WEBSITES.exists():
        sys.exit(f"Need {WEBSITES.relative_to(ROOT)} to know where to look.")

    with WEBSITES.open(encoding="utf-8-sig") as fh:
        sites = [r for r in csv.DictReader(fh) if r.get("district_website", "").strip()]
    if limit:
        sites = sites[:limit]

    existing = {r["url"] for r in load_registry() if r["url"].strip()}
    session = requests.Session()
    found = []

    for i, row in enumerate(sites, 1):
        landing = row["district_website"].strip()
        print(f"  [{i}/{len(sites)}] {row['district_name']}")

        # Own domain (landing page is the root) -> the whole site is theirs, so
        # a second hop is safe. A page inside a town site is all we may crawl.
        owns_domain = urlparse(landing).path.strip("/") == ""
        levels = depth if owns_domain else 1

        pages, visited, hits = [landing], set(), {}
        for level in range(levels):
            next_pages = []
            for page in pages:
                if page in visited:
                    continue
                visited.add(page)
                try:
                    resp = fetch(page, session)
                except Exception as exc:          # noqa: BLE001
                    if level == 0:
                        print(f"      unreachable: {str(exc)[:80]}")
                    continue
                html = resp.text

                for url, label in pdf_links(html, resp.url):
                    if url in existing or url in hits:
                        continue
                    name = Path(urlparse(url).path).name
                    if NOT_A_RECORD.search(name):
                        continue
                    hits[url] = (label or name, page)

                # Queue the next hop only if we have another level to spend.
                if level + 1 < levels:
                    next_pages.extend(records_pages(html, resp.url))
                time.sleep(PAUSE)
            pages = next_pages

        if len(hits) > PER_SITE_CAP:
            print(f"      {len(hits)} candidates exceeds the {PER_SITE_CAP} cap "
                  f"-- skipping this site, it is almost certainly a town archive")
            continue

        for url, (label, source) in hits.items():
            name = Path(urlparse(url).path).name
            found.append({
                "district_name": row["district_name"],
                "doc_type": guess_type(label + " " + name),
                "title": label,
                "url": url,
                "adopted": "",
                "source_page": source,
                "notes": "PROPOSED by --discover; confirm before trusting.",
            })
        if hits:
            print(f"      {len(hits)} candidate document(s)")

    if not found:
        print("\n  No new candidates found.")
        return

    write_registry(load_registry() + found)
    print(f"\n  Added {len(found)} PROPOSED rows to "
          f"{REGISTRY.relative_to(ROOT)}. Review them, clear the notes column "
          f"on the ones you keep, then run without --discover.")


def pdf_links(html, base):
    """(absolute_url, link_text) for every PDF on the page."""
    out, seen = [], set()
    for m in ANCHOR.finditer(html):
        url = urljoin(base, m.group(1))
        if url in seen:
            continue
        seen.add(url)
        label = re.sub(r"\s+", " ", TAG.sub(" ", m.group(2))).strip()
        out.append((url, html_unescape(label)))
    for href in PDF_HREF.findall(html):
        url = urljoin(base, href)
        if url not in seen:
            seen.add(url)
            out.append((url, ""))
    return out


def records_pages(html, base):
    """Same-host links that look like they lead to district records."""
    out, host = [], urlparse(base).netloc
    for m in re.finditer(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
                         html, re.I | re.S):
        href, text = m.group(1), TAG.sub(" ", m.group(2))
        if href.startswith(("mailto:", "tel:", "#", "javascript:")):
            continue
        url = urljoin(base, href)
        if urlparse(url).netloc != host or url.lower().endswith(".pdf"):
            continue
        if RECORDS_PAGE.search(text) or RECORDS_PAGE.search(url):
            out.append(url.split("#")[0])
    # Cap the fan-out so one navigation-heavy town site cannot dominate a run.
    return list(dict.fromkeys(out))[:12]


def guess_type(s):
    s = s.lower()
    for key, kind in (("ordinance", "ordinance"), ("charter", "charter"),
                      ("rate", "rates"), ("fee", "rates"), ("tariff", "rates"),
                      ("bylaw", "bylaws"), ("by-law", "bylaws"),
                      ("annual report", "annual_report"), ("budget", "budget"),
                      ("minute", "minutes"), ("warning", "warning"),
                      ("consumer confidence", "ccr"), ("ccr", "ccr"),
                      ("asset management", "plan"), ("capital", "plan"),
                      ("permit", "permit"), ("polic", "policy"),
                      ("rule", "policy"), ("regulation", "policy")):
        if key in s:
            return kind
    return "other"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--discover", action="store_true",
                    help="crawl district websites for candidate PDFs")
    ap.add_argument("--limit", type=int, help="with --discover, cap the sites crawled")
    ap.add_argument("--force", action="store_true", help="re-download cached PDFs")
    ap.add_argument("--depth", type=int, default=2,
                    help="with --discover, how many page hops to follow (default 2)")
    args = ap.parse_args()

    if args.discover:
        print("Discovering candidate documents:")
        discover(args.limit, args.depth)
    else:
        print("Fetching and extracting district documents:")
        build(args.force)


if __name__ == "__main__":
    main()
