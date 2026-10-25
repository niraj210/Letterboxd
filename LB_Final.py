"""
Letterboxd Top 250 Indian Films
===============================
Default: open the 4 public India-by-rating pages (no login), save HTML only,
then update top250_indian_films.csv and changelog.txt.

  python LB_Final.py              # fetch (headless) + parse
  python LB_Final.py --headed     # show the browser window
  python LB_Final.py --offline    # parse already-saved p1.html … p4.html

Uses a guest Playwright browser. Does not open your Chrome profile or
log into Letterboxd.

This does not import the list on Letterboxd. Upload the CSV yourself.
"""

import argparse
import csv
import os
import re
import quopri
import datetime
import sys

# Ensure UTF-8 output on Windows consoles
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ─── CONFIG ──────────────────────────────────────────────────────────────────
BASE_URL    = "https://letterboxd.com"
TOTAL_FILMS = 250
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
OUTPUT_CSV  = os.path.join(SCRIPT_DIR, "top250_indian_films.csv")
CHANGELOG   = os.path.join(SCRIPT_DIR, "changelog.txt")

N_PAGES        = 4
PAGE_URLS      = [
    f"{BASE_URL}/films/country/india/by/rating/page/{n}/"
    for n in range(1, N_PAGES + 1)
]
FETCH_TIMEOUT_MS = 90_000

BLOCKLIST_FILE      = os.path.join(SCRIPT_DIR, "blocklist.txt")
BIG_MOVER_THRESHOLD = 4   # films that climbed this many spots or more are highlighted


def load_blocklist() -> set:
    """Load blocklist from file. Falls back to empty set if file is missing."""
    if not os.path.exists(BLOCKLIST_FILE):
        print(f"[!] blocklist.txt not found at {BLOCKLIST_FILE} — no slugs will be blocked.")
        return set()
    slugs = set()
    with open(BLOCKLIST_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                slugs.add(line)
    print(f"[*] Blocklist loaded: {len(slugs)} slugs from blocklist.txt")
    return slugs


BLOCKLIST = load_blocklist()
# ─────────────────────────────────────────────────────────────────────────────


def _print_browser_install_help() -> None:
    print("\n[X] No browser found for Playwright.")
    print("    Install Chromium once, then run the script again:")
    print("        py -3 -m playwright install chromium")


def _launch_browser(playwright):
    """Guest window only — never your Chrome/Edge profile or Letterboxd login."""
    from playwright.sync_api import Error as PlaywrightError

    attempts = [
        ("Chromium", {}),
        ("Chrome (guest)", {"channel": "chrome"}),
        ("Edge (guest)", {"channel": "msedge"}),
    ]
    last_error = None
    for name, extra in attempts:
        try:
            browser = playwright.chromium.launch(headless=False, **extra)
            print(f"    using {name}")
            return browser
        except PlaywrightError as e:
            last_error = e
    print(last_error)
    _print_browser_install_help()
    sys.exit(1)


def fetch_pages() -> None:
    """Load public listing pages in a guest browser (no login, not your Chrome)."""
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeout
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("\n[X] Playwright is not installed.")
        print("    py -3 -m pip install playwright")
        print("    py -3 -m playwright install chromium")
        sys.exit(1)

    print(f"\n[*] Fetching {N_PAGES} public pages (guest browser, no account)")
    print("    If a security check appears, complete it in the window — do not log in.")

    with sync_playwright() as p:
        browser = _launch_browser(p)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        try:
            for i, url in enumerate(PAGE_URLS, 1):
                print(f"    [{i}/{N_PAGES}] {url}")
                page.goto(url, wait_until="domcontentloaded", timeout=FETCH_TIMEOUT_MS)
                try:
                    page.wait_for_selector(
                        '[data-item-link^="/film/"]',
                        timeout=FETCH_TIMEOUT_MS,
                    )
                except PlaywrightTimeout:
                    print("\n[X] Film grid never appeared (security check or page change).")
                    print("    Complete the check as a guest — do not sign in.")
                    print("    Or save pages by hand and run: python LB_Final.py --offline")
                    sys.exit(1)

                dest = os.path.join(SCRIPT_DIR, f"p{i}.html")
                with open(dest, "w", encoding="utf-8") as f:
                    f.write(page.content())
                print(f"        saved {os.path.basename(dest)}")
        finally:
            context.close()
            browser.close()

    print("[+] Fetch complete.")


def ordinal(n: int) -> str:
    if 11 <= (n % 100) <= 13:
        return f"{n}th"
    return f"{n}{['th','st','nd','rd','th'][min(n % 10, 4)]}"


def read_file(path: str) -> str:
    """Read HTML or MHTML file and return decoded text."""
    with open(path, "rb") as f:
        raw = f.read()

    # MHTML uses quoted-printable encoding
    if path.lower().endswith(".mhtml"):
        try:
            raw = quopri.decodestring(raw)
        except Exception:
            pass

    return raw.decode("utf-8", errors="ignore")


def extract_slugs(content: str) -> list[str]:
    """Extract unique film slugs from saved page HTML."""
    seen: set[str]  = set()
    slugs: list[str] = []

    def add(slug: str):
        if slug and slug not in seen:
            seen.add(slug)
            slugs.append(slug)

    # Pattern 1: data-item-link="/film/slug/" (most reliable in saved pages)
    for slug in re.findall(r'data-item-link=3D"/film/([^/\"]+)/', content):  # mhtml encoded
        add(slug)
    for slug in re.findall(r'data-item-link="/film/([^/\"]+)/', content):    # plain html
        add(slug)

    # Pattern 2: data-target-link="/film/slug/"
    for slug in re.findall(r'data-target-link=3D"/film/([^/\"]+)/', content):
        add(slug)
    for slug in re.findall(r'data-target-link="/film/([^/\"]+)/', content):
        add(slug)

    # Pattern 3: href="/film/slug/"
    for slug in re.findall(r'href=3D"/film/([^/\"]+)/', content):
        add(slug)
    for slug in re.findall(r'href="/film/([^/\"]+)/', content):
        add(slug)

    return slugs


def find_page_files() -> list[str]:
    """Auto-detect saved page files in the script directory."""
    found = []
    # Match files like page1.html, page2.mhtml, page_1.html, etc.
    pattern = re.compile(r'p(?:age)?[_\-]?(\d+)\.(html|mhtml)$', re.IGNORECASE)
    all_files = sorted(os.listdir(SCRIPT_DIR))
    matched = {}
    for fname in all_files:
        m = pattern.match(fname)
        if m:
            num = int(m.group(1))
            matched[num] = os.path.join(SCRIPT_DIR, fname)
    for num in sorted(matched):
        found.append(matched[num])
    return found


def parse_films() -> list[str]:
    page_files = find_page_files()

    if not page_files:
        print("\n[!] No page files found in script directory.")
        print("    Save your pages as page1.html, page2.html etc. and re-run.")
        return []

    print(f"\n[*] Found {len(page_files)} page file(s):")
    for f in page_files:
        print(f"    {os.path.basename(f)}")

    uris = []
    seen = set()

    for path in page_files:
        content = read_file(path)
        slugs   = extract_slugs(content)
        found   = 0
        for slug in slugs:
            if slug not in seen and slug not in BLOCKLIST:
                seen.add(slug)
                uris.append(f"{BASE_URL}/film/{slug}/")
                found += 1
            if len(uris) >= TOTAL_FILMS:
                break
        print(f"    {os.path.basename(path):20s} → {found} new films  (total: {len(uris)})")
        if len(uris) >= TOTAL_FILMS:
            break

    if len(uris) < TOTAL_FILMS:
        print(f"\n[!] Warning: Only {len(uris)}/{TOTAL_FILMS} films found — check your page files.")
    return uris[:TOTAL_FILMS]


# ─── CHANGE TRACKING ─────────────────────────────────────────────────────────

def load_previous_csv(path: str) -> list[str]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        uris = [row[0].strip() for row in reader if row and row[0].startswith("http")]
    return uris


def slug_from_uri(uri: str) -> str:
    return uri.strip("/").split("/")[-1]


def slug_to_title(slug: str) -> str:
    return " ".join(w.capitalize() for w in slug.replace("-", " ").split())


def compute_diff(old_uris, new_uris):
    old_slugs = {slug_from_uri(u): i + 1 for i, u in enumerate(old_uris)}
    new_slugs = {slug_from_uri(u): i + 1 for i, u in enumerate(new_uris)}
    added   = [(new_slugs[s], s) for s in new_slugs if s not in old_slugs]
    removed = [(old_slugs[s], s) for s in old_slugs if s not in new_slugs]
    rank_changes = []
    for slug, new_rank in new_slugs.items():
        if slug in old_slugs:
            old_rank = old_slugs[slug]
            if old_rank != new_rank:
                rank_changes.append({
                    "slug": slug, "old_rank": old_rank,
                    "new_rank": new_rank, "change": old_rank - new_rank,
                })
    rank_changes.sort(key=lambda x: abs(x["change"]), reverse=True)
    return added, removed, rank_changes


def get_top25_changes(old_uris: list[str], new_uris: list[str]):
    """
    Return films that entered or left the top 25.
    'entered': in new top 25 but not old top 25
    'dropped': in old top 25 but not new top 25
    Each entry is (rank, slug) — rank is the relevant list's position.
    """
    old_slug_to_rank = {slug_from_uri(u): i + 1 for i, u in enumerate(old_uris)}
    new_slug_to_rank = {slug_from_uri(u): i + 1 for i, u in enumerate(new_uris)}

    old_top25 = {s for s, r in old_slug_to_rank.items() if r <= 25}
    new_top25 = {s for s, r in new_slug_to_rank.items() if r <= 25}

    entered = sorted(
        [(new_slug_to_rank[s], s) for s in new_top25 - old_top25]
    )
    dropped = sorted(
        [(old_slug_to_rank[s], s) for s in old_top25 - new_top25]
    )
    return entered, dropped


def print_diff(added, removed, rank_changes, old_uris, new_uris):
    big_risers = [r for r in (rank_changes or []) if r["change"] >= BIG_MOVER_THRESHOLD]
    top25_entered, top25_dropped = get_top25_changes(old_uris, new_uris)

    has_notable = any([added, removed, big_risers, top25_entered, top25_dropped])
    has_any     = has_notable or bool(rank_changes)
    if not has_any:
        print("\n  No changes since last run.")
        return
    if not has_notable:
        print("\n  Minor rank changes only (no film moved 4+ spots).")
        return

    now = datetime.datetime.now()
    today = now.strftime("%B") + " " + ordinal(now.day) + ", " + str(now.year)
    print(f"\nUpdate {today}")

    if added:
        print("\nNew or back in the list:")
        for _, slug in sorted(added):
            print(f"  {slug_to_title(slug)}")

    if removed:
        print("\nGone, not forgotten:")
        print("  " + ", ".join(slug_to_title(s) for _, s in sorted(removed)))

    if big_risers:
        print("\nBig movers ↑ (climbed 4+ spots):")
        for r in sorted(big_risers, key=lambda x: x["change"], reverse=True):
            print(f"  {slug_to_title(r['slug'])}: #{r['old_rank']} → #{r['new_rank']}  (+{r['change']})")

    if top25_entered or top25_dropped:
        print("\nTop 25 changes:")
        for rank, slug in top25_entered:
            print(f"  ↑ Entered  #{rank:>2}  {slug_to_title(slug)}")
        for rank, slug in top25_dropped:
            print(f"  ↓ Dropped  (was #{rank:>2})  {slug_to_title(slug)}")


def save_changelog(added, removed, rank_changes, old_uris, new_uris):
    big_risers = [r for r in (rank_changes or []) if r["change"] >= BIG_MOVER_THRESHOLD]
    top25_entered, top25_dropped = get_top25_changes(old_uris, new_uris)

    has_changes = any([added, removed, big_risers, top25_entered, top25_dropped])
    if not has_changes:
        return

    now = datetime.datetime.now()
    today = now.strftime("%B") + " " + ordinal(now.day) + ", " + str(now.year)

    with open(CHANGELOG, "a", encoding="utf-8") as f:
        f.write(f"\nUpdate {today}\n")

        if added:
            f.write("\nNew or back in the list:\n")
            for _, slug in sorted(added):
                f.write(f"  {slug_to_title(slug)}\n")

        if removed:
            f.write("\nGone, not forgotten:\n")
            f.write("  " + ", ".join(slug_to_title(s) for _, s in sorted(removed)) + "\n")

        if big_risers:
            f.write("\nBig movers ↑ (climbed 4+ spots):\n")
            for r in sorted(big_risers, key=lambda x: x["change"], reverse=True):
                f.write(f"  {slug_to_title(r['slug'])}: #{r['old_rank']} → #{r['new_rank']}  (+{r['change']})\n")

        if top25_entered or top25_dropped:
            f.write("\nTop 25 changes:\n")
            for rank, slug in top25_entered:
                f.write(f"  ↑ Entered  #{rank:>2}  {slug_to_title(slug)}\n")
            for rank, slug in top25_dropped:
                f.write(f"  ↓ Dropped  (was #{rank:>2})  {slug_to_title(slug)}\n")

    print(f"[+] Changelog saved -> {CHANGELOG}")


def save_csv(uris, output_path, added=None, removed=None):
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["LetterboxdURI"])
        for uri in uris:
            writer.writerow([uri])
    print(f"[+] CSV saved -> {output_path}  ({len(uris)} rows)")


# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Fetch Letterboxd India-by-rating pages and update the Top 250 CSV/changelog."
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Skip Chrome fetch; parse existing p1.html … p4.html",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  Letterboxd Top 250 Indian Films")
    print("=" * 60)

    if not args.offline:
        fetch_pages()
    else:
        print("\n[*] Offline mode — using saved page files.")

    old_uris     = load_previous_csv(OUTPUT_CSV)
    is_first_run = len(old_uris) == 0
    if is_first_run:
        print("\n[*] No previous CSV — first run.")
    else:
        print(f"\n[*] Previous CSV loaded: {len(old_uris)} films.")

    new_uris = parse_films()

    if not new_uris:
        print("\n[X] No films parsed. Check that your page files are in the right folder.")
        return

    added, removed, rank_changes = None, None, None
    if not is_first_run:
        added, removed, rank_changes = compute_diff(old_uris, new_uris)
        print_diff(added, removed, rank_changes, old_uris, new_uris)
        save_changelog(added, removed, rank_changes, old_uris, new_uris)
    else:
        print(f"\n[*] First run complete — {len(new_uris)} films parsed.")

    save_csv(new_uris, OUTPUT_CSV, added=added, removed=removed)
    print(f"\n  Done! Import at: https://letterboxd.com/import/")


if __name__ == "__main__":
    main()