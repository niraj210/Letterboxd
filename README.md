# 🎬 Letterboxd Top 250 Indian Films

A Python script that scrapes [Letterboxd](https://letterboxd.com)'s **India-by-rating** pages and generates a curated **Top 250 Indian Films** list as a CSV — ready to import into your Letterboxd account.

## ✨ Features

- **Automated scraping** — Uses Playwright to fetch the top-rated Indian films from Letterboxd's public pages (no login required)
- **Blocklist support** — Exclude non-Indian or irrelevant entries (documentaries, stand-up specials, web series, etc.) via `blocklist.txt`
- **Change tracking** — Detects new entries, removals, rank changes, and Top 25 movements between runs
- **Changelog** — Automatically logs notable changes to `changelog.txt` with formatted dates
- **Offline mode** — Re-parse previously saved HTML pages without hitting the network
- **CSV export** — Outputs a Letterboxd-compatible CSV for direct import

## 📋 Requirements

- Python 3.10+
- [Playwright](https://playwright.dev/python/) (for browser automation)

## 🚀 Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Install browser (one-time)
python -m playwright install chromium
```

## 📖 Usage

```bash
# Default: fetch pages (headless) + parse + update CSV & changelog
python LB_Final.py

# Show the browser window while fetching
python LB_Final.py --headed

# Skip fetching — parse already-saved p1.html … p4.html
python LB_Final.py --offline
```

### Import to Letterboxd

1. Run the script to generate `top250_indian_films.csv`
2. Go to [letterboxd.com/import](https://letterboxd.com/import/)
3. Upload the CSV file

## 📁 Project Structure

| File | Description |
|------|-------------|
| `LB_Final.py` | Main script — fetches, parses, and generates the list |
| `blocklist.txt` | Slugs to exclude (one per line, `#` for comments) |
| `top250_indian_films.csv` | Output CSV with 250 Letterboxd URIs |
| `changelog.txt` | Auto-generated log of list changes across runs |
| `requirements.txt` | Python dependencies |
| `p1.html` … `p4.html` | Cached HTML pages from Letterboxd (auto-generated) |

## 🔧 Configuration

Key settings in `LB_Final.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `TOTAL_FILMS` | `250` | Number of films to include |
| `N_PAGES` | `4` | Number of Letterboxd pages to fetch |
| `FETCH_TIMEOUT_MS` | `90000` | Browser timeout per page (ms) |
| `BIG_MOVER_THRESHOLD` | `4` | Minimum rank change to highlight |

## 📝 Blocklist

Edit `blocklist.txt` to exclude films that shouldn't appear in the list. Add one Letterboxd slug per line:

```
# Example: exclude a stand-up special
samay-raina-still-alive

# Example: exclude a non-Indian film
the-fabelmans
```

The slug is the last part of a Letterboxd film URL:
`https://letterboxd.com/film/the-fabelmans/` → `the-fabelmans`

## 📊 Changelog

Each run compares against the previous CSV and logs:
- 🆕 **New entries** — Films that entered the Top 250
- 👋 **Removals** — Films that dropped out
- 📈 **Big movers** — Films that climbed 4+ spots
- 🏆 **Top 25 changes** — Films entering or leaving the elite Top 25

## 📄 License

This project is for personal use. Letterboxd data belongs to [Letterboxd Ltd](https://letterboxd.com).
