# DXpedition Notifier

An automated DX Cluster monitoring tool for amateur radio operators that fetches live DX spots from **HamQTH**, cross-references them against active DXpeditions from **NG3K ADXO**, applies continent and heuristic filtering with time-windowed deduplication, and sends push alerts via **Telegram**.

---

## Features

- **Live DX Cluster Ingestion:** Pulls and normalizes spot data from HamQTH (`dxc_csv.php`), automatically detecting delimiters (`^`, `;`, `,`) and normalizing frequencies into kHz.
- **Automatic DXpedition List Refresh:** Loads local DXpedition entries (`dxpeditions.json`) and refreshes them from NG3K ADXO (`adxo.html`) when missing or older than `MAX_DXPED_AGE_HOURS` (default: 12 hours).
- **Priority & Continent Filtering:**
  - Restricts spotters to your home continent by default (`REQUIRE_HOME_CONTINENT_SPOTTER=true`), derived from your callsign prefix.
  - **`HIGH` priority:** Direct match against active DXpeditions (full callsign, slash-separated segments, and aliases) within `start_date` / `end_date` windows.
  - **`NORMAL` priority:** Heuristic matches based on comment keywords (`dxped`, `dx-ped`, `dx expedition`, `expedition`, `qsx`, `split`, `iota`, `sota`, `pota`, `wwff`), standalone `\bup\b`, `/` in the DX callsign, or a DX continent different from the home continent.
- **Time-Windowed Deduplication:** Tracks notified spots in `seen_spots.json` keyed by `DX_CALL|BAND` (or a ~2 kHz frequency bucket when band is absent) over `DEDUP_WINDOW_MINUTES` (default: 30 minutes), automatically pruning expired entries.
- **Telegram Bot Alerts:** Sends formatted HTML notifications with automatic message splitting for long payloads, supporting `HIGH` or `HIGH_AND_NORMAL` notification modes, silent mode, and a CLI test command.
- **Cron-Friendly Automation:** Designed to run periodically (e.g., every 15 minutes via `crontab`) with log redirection and clean separation of local state/secrets via `.gitignore`.

---

## Project Structure

```text
dxpedition-notifier/
├── main.py                   # Main CLI pipeline, filtering, deduplication, and Telegram sender
├── fetch_ng3k_dxpeditions.py # NG3K ADXO HTML scraper and JSON normalizer
├── prefixes.py               # Callsign-to-continent lookup helper
├── .env                      # Local environment variables & secrets (gitignored)
├── dxpeditions.json          # Local/cached DXpedition database
├── seen_spots.json           # Local deduplication state (gitignored)
└── dx_monitor.log            # Optional cron execution log (gitignored)
```

---

## Installation

1. **Clone the repository and enter the project directory:**
   ```bash
   git clone <your-repo-url> dxpedition-notifier
   cd dxpedition-notifier
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv venv
   ./venv/bin/pip install --upgrade pip
   ./venv/bin/pip install requests beautifulsoup4
   ```

3. **Configure environment variables:**
   Create a `.env` file in the project root:
   ```env
   MY_CALLSIGN=IU4TRM
   REQUIRE_HOME_CONTINENT_SPOTTER=true
   MAX_DXPED_AGE_HOURS=12
   DEDUP_WINDOW_MINUTES=30

   TELEGRAM_BOT_TOKEN=your_bot_token_here
   TELEGRAM_CHAT_ID=your_chat_id_here
   TELEGRAM_NOTIFY_MODE=HIGH
   TELEGRAM_SILENT=false
   ```

---

## Configuration Reference

| Variable | Default | Description |
| :--- | :--- | :--- |
| `MY_CALLSIGN` | `IU4TRM` | Reference callsign used to determine home continent (fallback: `EU`). |
| `REQUIRE_HOME_CONTINENT_SPOTTER` | `true` | Only accepts spots reported by spotters in your home continent. |
| `MAX_DXPED_AGE_HOURS` | `12` | Maximum age (in hours) of `dxpeditions.json` before refreshing from NG3K. |
| `DEDUP_WINDOW_MINUTES` | `30` | Deduplication window (in minutes) stored in `seen_spots.json`. |
| `TELEGRAM_BOT_TOKEN` | `""` | Telegram Bot API token from `@BotFather`. |
| `TELEGRAM_CHAT_ID` | `""` | Target Telegram chat, group, or channel ID. |
| `TELEGRAM_NOTIFY_MODE` | `HIGH_AND_NORMAL` | Set to `HIGH` for DXpedition matches only, or `HIGH_AND_NORMAL` for all matches. |
| `TELEGRAM_SILENT` | `false` | Sends Telegram messages without sound (`disable_notification`). |

---

## Usage

### Run a Monitoring Cycle
```bash
./venv/bin/python main.py
```

### CLI Options
- **Override callsign for a single run:**
  ```bash
  ./venv/bin/python main.py --callsign K1ABC
  ```
- **Run without sending Telegram messages:**
  ```bash
  ./venv/bin/python main.py --no-telegram
  ```
- **Verify Telegram credentials:**
  ```bash
  ./venv/bin/python main.py --test-telegram
  ```

### Automate with `crontab` (Every 15 Minutes)
```cron
*/15 * * * * cd /path/to/dxpedition-notifier && /path/to/dxpedition-notifier/venv/bin/python /path/to/dxpedition-notifier/main.py >> /path/to/dxpedition-notifier/dx_monitor.log 2>&1
```

*(Note on macOS: If running from `cron` against folders under `~/Documents`, ensure `cron` has the necessary permissions under **System Settings → Privacy & Security**.)*

---

## Git & Security Notes

Keep local runtime files and credentials out of version control by including them in `.gitignore`:

```gitignore
venv/
.venv/
__pycache__/
*.pyc
.env
seen_spots.json
dx_monitor.log
dxmonitor.log
```