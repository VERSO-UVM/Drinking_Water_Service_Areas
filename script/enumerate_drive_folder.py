"""
Enumerate a public Google Drive folder tree into ordinance-registry rows.

Several districts publish their records through Drive rather than as links on a
web page. `fetch_district_ordinances.py --discover` cannot see those at all --
the files never appear in the page HTML, and the folder listing itself is drawn
by JavaScript, so plain HTTP returns an empty shell.

This walks the tree with headless Chrome, which renders the listing, and writes
one PROPOSED registry row per file found. As everywhere else in this pipeline,
discovery proposes and a human accepts.

Usage:
  python script/enumerate_drive_folder.py <folder-url-or-id> \
      --district "Norwich Fire District 1" [--depth 3] [--dry-run]
"""

import argparse
import csv
import re
import shutil
import subprocess
import sys
import tempfile
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "data" / "vt_district_ordinances.csv"
FIELDS = ["district_name", "doc_type", "title", "url", "adopted",
          "source_page", "notes"]

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
]

ID_RE = re.compile(r"[A-Za-z0-9_-]{25,}")
DATA_ID = re.compile(r'data-id="([A-Za-z0-9_-]{20,})"')
# Drive labels every row; folders carry a "Shared folder"/"Folder" suffix.
LABEL = re.compile(r'aria-label="([^"]{2,160})"')
FOLDER_LABEL = re.compile(r"\bfolder\b", re.I)


def find_chrome():
    for c in CHROME_CANDIDATES:
        if Path(c).exists() or shutil.which(c):
            return c
    sys.exit("No Chrome/Edge binary found; edit CHROME_CANDIDATES.")


def folder_id(s):
    """Accept a bare id, a /folders/<id> url, or an open?id=<id> url."""
    m = re.search(r"/folders/([A-Za-z0-9_-]+)", s) or \
        re.search(r"[?&]id=([A-Za-z0-9_-]+)", s)
    if m:
        return m.group(1)
    if ID_RE.fullmatch(s.strip()):
        return s.strip()
    sys.exit(f"Could not read a Drive folder id from: {s}")


def render(url, chrome, budget_ms=25000):
    with tempfile.TemporaryDirectory() as profile:
        try:
            out = subprocess.run(
                [chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
                 f"--virtual-time-budget={budget_ms}", "--dump-dom",
                 f"--user-data-dir={profile}", url],
                capture_output=True, timeout=budget_ms / 1000 + 45)
            return out.stdout.decode("utf-8", errors="replace")
        except subprocess.TimeoutExpired:
            print(f"      timed out rendering {url}")
            return ""


TABLE_ROW = re.compile(
    r'<tr[^>]*data-id="([A-Za-z0-9_-]{20,})"[^>]*>(.*?)</tr>', re.S)
GRID_ITEM = re.compile(
    r'data-id="([A-Za-z0-9_-]{20,})"(?!.{0,80}?data-selection-key)', re.S)


def parse_listing(html):
    """[(id, name, is_folder)] for the entries Drive rendered.

    Drive uses two layouts in the same page: folders render as a grid of tiles
    whose aria-label carries the name, while files render as table rows whose
    cells read [kind, filename, sharing, owner, modified, size]. Reading only
    the aria-label near each id gets "Shared" for every file, so table rows are
    parsed from their cells and the grid is used only for what the table misses.
    """
    out, seen = [], set()

    for fid, body in TABLE_ROW.findall(html):
        cells = [unescape(t).strip() for t in re.split(r"<[^>]+>", body) if t.strip()]
        if not cells:
            continue
        kind = cells[0]
        name = cells[1] if len(cells) > 1 else fid
        # The first cell is the type chip: "PDF", "Folder", "Google Docs"...
        is_folder = kind.lower().startswith("folder")
        seen.add(fid)
        out.append((fid, name, is_folder))

    for m in DATA_ID.finditer(html):
        fid = m.group(1)
        if fid in seen:
            continue
        label = LABEL.search(html[m.end():m.end() + 1500])
        if not label:
            continue
        seen.add(fid)
        name = unescape(label.group(1)).strip()
        is_folder = bool(re.search(r"\b(Shared folder|Folder)\s*$", name, re.I))
        name = re.sub(r"\s*(Shared folder|Folder)\s*$", "", name, flags=re.I).strip()
        out.append((fid, name, is_folder))

    return out


def walk(root_id, chrome, depth):
    """Breadth-first over the folder tree. Returns [(file_id, name, path)]."""
    files, seen = [], set()
    queue = [(root_id, "")]
    for level in range(depth):
        nxt = []
        for fid, path in queue:
            if fid in seen:
                continue
            seen.add(fid)
            url = f"https://drive.google.com/drive/folders/{fid}"
            print(f"  [depth {level}] {path or '/'}")
            entries = parse_listing(render(url, chrome))
            if not entries:
                print("      (nothing rendered -- folder may be empty or private)")
            for eid, name, is_folder in entries:
                where = f"{path}/{name}" if path else name
                if is_folder:
                    nxt.append((eid, where))
                else:
                    files.append((eid, name, path))
            print(f"      {sum(1 for e in entries if e[2])} folders, "
                  f"{sum(1 for e in entries if not e[2])} files")
        queue = nxt
        if not queue:
            break
    return files


def guess_type(name):
    n = name.lower()
    for key, kind in (("minute", "minutes"), ("agenda", "agenda"),
                      ("packet", "packet"), ("warning", "warning"),
                      ("ordinance", "ordinance"), ("polic", "policy"),
                      ("rate", "rates"), ("budget", "budget"),
                      ("annual report", "annual_report"), ("audit", "audit"),
                      ("bylaw", "bylaws"), ("ccr", "ccr")):
        if key in n:
            return kind
    return "other"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("folder", help="Drive folder URL or id")
    ap.add_argument("--district", required=True, help="exact district_name")
    ap.add_argument("--depth", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    chrome = find_chrome()
    root = folder_id(args.folder)
    print(f"Walking Drive folder {root} for {args.district}:")
    files = walk(root, chrome, args.depth)
    print(f"\n  {len(files)} files found")
    if not files:
        return

    rows = []
    if REGISTRY.exists():
        with REGISTRY.open(encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
    existing = {r["url"] for r in rows}

    added = 0
    for fid, name, path in files:
        url = f"https://drive.google.com/file/d/{fid}/view"
        if url in existing:
            continue
        rows.append({
            "district_name": args.district,
            "doc_type": guess_type(name + " " + path),
            "title": name,
            "url": url,
            "adopted": "",
            "source_page": f"https://drive.google.com/drive/folders/{root}",
            "notes": f"PROPOSED by enumerate_drive_folder ({path or 'root'}); "
                     f"confirm before trusting.",
        })
        added += 1

    if args.dry_run:
        print(f"  (dry run) would add {added} rows")
        for r in rows[-added:][:10]:
            print(f"     {r['doc_type']:<14} {r['title'][:60]}")
        return

    with REGISTRY.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for r in sorted(rows, key=lambda r: (r["district_name"], r["title"])):
            w.writerow({k: r.get(k, "") for k in FIELDS})
    print(f"  added {added} PROPOSED rows to {REGISTRY.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
