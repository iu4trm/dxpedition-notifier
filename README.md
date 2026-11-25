# DXpedition Notifier

An automated DX Cluster monitoring tool for amateur radio operators. It downloads live spots from **HamQTH**, matches them against active expeditions listed by **NG3K ADXO**, applies continent and heuristic filters, limits repeated notifications, evaluates propagation and grayline conditions, draws a DX paths map, and optionally sends text alerts and PNG images through **Telegram**.

The project is cron-friendly and uses local JSON/cache files instead of a database. Python 3.10+ is required.

## English Documentation

### Features

- Downloads HamQTH CSV spots and detects `^`, `;`, or `,` delimiters.
- Converts MHz-like frequencies to kHz while preserving already-normalized kHz values.
- Loads and periodically refreshes an NG3K DXpedition cache.
- Resolves callsign prefixes to continents, with an optional home-continent spotter filter.
- Matches complete callsigns, slash-separated callsign segments, aliases, and active date ranges.
- Supports heuristic `NORMAL` matches for expedition keywords, `UP`, slash callsigns, and foreign-continent DX.
- Deduplicates notifications by callsign and band or by an approximate 2 kHz frequency bucket.
- Retrieves HamQSL/NOAA solar data and caches it locally.
- Calculates approximate grayline windows and classifies an informational path assessment.
- Generates a 1000×500 PNG great-circle paths map with grid, countries, day/night shading, and grayline shading.
- Sends formatted Telegram text messages, optional silent notifications, and an optional map photo.
- Provides CLI overrides and test modes.

### Execution Flow

On every normal run, `main.py`:

1. Loads `.env` without replacing variables already present in the process environment.
2. Determines the callsign from `--callsign` or `MY_CALLSIGN`, and derives the home continent.
3. Loads cached solar data or fetches fresh HamQSL/NOAA XML data.
4. Loads `dxpeditions.json`, refreshing it from NG3K if missing or older than `MAX_DXPED_AGE_HOURS`.
5. Downloads and parses HamQTH spots.
6. Filters spotters, matches DXpeditions, and applies heuristic rules.
7. Removes entries outside the deduplication window and rejects recently notified keys.
8. Prints up to 20 new matches, sorted with `HIGH` before `NORMAL`.
9. Generates `dx_paths_map.png` when a map module and new matches are available.
10. Sends Telegram text alerts according to `TELEGRAM_NOTIFY_MODE`.
11. Optionally sends the map PNG when `--send-map` is used.

`--test-telegram` performs a Telegram credential test and stops before spot processing. `--no-telegram` suppresses both text and map delivery.

### Project Files

```text
dxpedition-notifier/
├── main.py                      # Main CLI, filtering, state, propagation, Telegram, map coordination
├── fetch_ng3k_dxpeditions.py    # NG3K HTML scraper and JSON cache generator
├── prefixes.py                  # Callsign-prefix-to-continent lookup
├── propagation.py               # Solar XML, cache, grayline, and path assessment
├── map_paths.py                 # PIL map, great-circle paths, GeoJSON countries, Telegram photo
├── dxpeditions.json             # Generated DXpedition cache
├── seen_spots.json              # Deduplication timestamps (gitignored)
├── prop_cache.json              # Solar data cache (gitignored)
├── dx_paths_map.png             # Generated DX paths map (gitignored)
├── world_countries.geojson      # Optional local country outlines (gitignored)
├── .env                         # Local configuration and secrets (gitignored)
├── dx_monitor.log               # Optional cron output (gitignored)
├── venv/                        # Local virtual environment (gitignored)
├── .gitignore
└── README.md
```

All optional modules are loaded gracefully: propagation or map failures do not prevent basic DX monitoring where the required modules remain available.

### Requirements

- Python 3.10 or newer.
- `requests`.
- `beautifulsoup4` for NG3K scraping.
- `Pillow` for PNG map generation.
- Internet access to HamQTH, NG3K, HamQSL/NOAA, and/or Telegram when those features are used.

Install an environment:

```bash
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install requests beautifulsoup4 Pillow
```

Dependencies can also be installed from the provided manifest:

```bash
./venv/bin/pip install -r requirements.txt
```

Run the automated test suite:

```bash
./venv/bin/python -m pytest -q
```

### Configuration

Create `.env` in the project directory:

```env
MY_CALLSIGN=IU4TRM
REQUIRE_HOME_CONTINENT_SPOTTER=true
MAX_DXPED_AGE_HOURS=12
DEDUP_WINDOW_MINUTES=30

TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
TELEGRAM_NOTIFY_MODE=HIGH_AND_NORMAL
TELEGRAM_SILENT=false

MY_LAT=44.5000
MY_LON=11.3500
MY_QTH_LOCATOR=JN45AB
PROP_CACHE_MINUTES=45
```

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `MY_CALLSIGN` | `IU4TRM` | Default callsign used to determine the home continent. |
| `REQUIRE_HOME_CONTINENT_SPOTTER` | `true` | Accept only spotters in the home continent. |
| `MAX_DXPED_AGE_HOURS` | `12` | Maximum `dxpeditions.json` age before refreshing NG3K. |
| `DEDUP_WINDOW_MINUTES` | `30` | Time window for repeated notification suppression. |
| `TELEGRAM_BOT_TOKEN` | empty | Telegram bot token. |
| `TELEGRAM_CHAT_ID` | empty | Telegram user, group, or channel ID. |
| `TELEGRAM_NOTIFY_MODE` | `HIGH_AND_NORMAL` | `HIGH` for direct DXpedition matches only, or `HIGH_AND_NORMAL` for both priorities. |
| `TELEGRAM_SILENT` | `false` | Sets Telegram `disable_notification`. |
| `MY_LAT` | continent reference | Optional station latitude in decimal degrees. |
| `MY_LON` | continent reference | Optional station longitude in decimal degrees. |
| `MY_QTH_LOCATOR` | `JN45AB` | Optional Maidenhead locator. |
| `PROP_CACHE_MINUTES` | `45` | Minimum lifetime of cached solar data. |

Boolean values `1`, `true`, `yes`, and `on` enable filtering and silent mode. Text is matched case-insensitively.

### HamQTH Parsing

`fetch_dxc_spots()` downloads the feed with a 15-second timeout and a DXpedition-Notifier User-Agent. It tries the first line to detect `^`, `;`, or `,` separators.

The CSV columns used are:

| Index | Field | Normalization |
| ---: | :--- | :--- |
| 0 | Spotter | Uppercase |
| 1 | Frequency | MHz to kHz when represented as a decimal in the 1–60 range |
| 2 | DX callsign | Uppercase |
| 3 | Comment | Preserved text |
| 4 | UTC/date | Preserved text |
| 7 | DX continent | Uppercase and validated against six common continent codes |
| 8 | Band | Uppercase |
| 9 | DXCC entity | Preserved text |
| 10 | DXCC ID | Preserved text |

Malformed rows with fewer than four columns are skipped.

### DXpedition Matching

The NG3K scraper inspects table rows containing at least seven cells. It requires parseable start/end dates, removes `[spots]` from callsigns, uppercases callsigns, and extracts aliases matching an ampersand-style `as/using/callsign` pattern or full-looking slash/digit callsigns.

The main matcher:

- Builds a set from the complete DX callsign and every `/`-separated segment.
- Compares that set with the primary callsign and each alias.
- Extracts `YYYY-MM-DD` from the spot UTC field when available.
- Accepts the entry only inside `start_date` and `end_date`, if present.
- Returns the first matching entry.

For `NORMAL` priority, the comment is searched for configured words, a standalone `UP` word, or a slash in the DX callsign. A DX continent obtained from the feed or callsign prefix is also considered when it differs from the home continent.

### Callsign Prefixes

`prefixes.py` provides a substantial amateur-radio prefix table and sorts prefixes from longest to shortest to improve special-prefix matching. When `/` is present, the callsign segments are sorted and checked before the full call.

The result is one of `EU`, `NA`, `SA`, `AF`, `AS`, or `OC`. Unknown prefixes return `None`; the monitoring entry point falls back to `EU`.

### Deduplication

The state file `seen_spots.json` stores keys and notification timestamps:

- With a band: `DX_CALL|BAND`.
- Without a band: `DX_CALL|~NNNNkHz`, with frequency rounded to the nearest 2 kHz.
- If frequency parsing fails: `DX_CALL|raw-frequency`.

Each run reads and prunes entries whose age exceeds `DEDUP_WINDOW_MINUTES`. New keys are added before Telegram delivery, so repeated spot cycles are suppressed even if delivery fails or Telegram credentials are missing.

### Propagation

The optional `propagation.py` module:

- Fetches HamQSL solar XML with a 10-second timeout.
- Parses SFI, K index, A index, and X-ray value.
- Classifies conditions as disturbed, unsettled, good/high-band, moderate, quiet/low-mid, unknown, or unavailable.
- Caches successful responses for `PROP_CACHE_MINUTES`.
- Reuses stale cache data when a refresh fails, while preserving an error field.
- Approximates solar elevation using the station coordinates or continent reference coordinates.
- Defines grayline as approximately ±6 degrees of solar elevation.

Path assessment is informational and never removes a spot. It distinguishes high bands, mid bands, low bands, intra-continental paths, high-latitude paths, trans-equatorial paths, geomagnetic disturbance, and grayline conditions.

### DX Paths Map

The optional `map_paths.py` module uses Pillow and can use `world_countries.geojson` for country outlines. Without GeoJSON, it still renders the grid, grayline/night fields, great-circle arcs, markers, labels, and title.

The map:

- Uses a 1000×500 equirectangular projection.
- Draws great-circle paths from the station QTH to resolved DX coordinates.
- Uses red paths for `HIGH` matches and cyan paths for `NORMAL` matches.
- Highlights countries at or near destination coordinates when GeoJSON is available.
- Shows a green station marker, call labels, UTC timestamp, and path count.
- Saves `dx_paths_map.png` whenever at least one destination can be resolved.

Map generation does not depend on Telegram delivery. The PNG is always generated before the optional `--send-map` photo is considered.

### Telegram

Text messages use Telegram HTML mode. The maximum chunk size is intentionally 3900 characters to leave margin below Telegram's 4096-character limit.

- `send_telegram_test()` sends station and propagation details without spot processing.
- `send_telegram_alerts()` filters `HIGH`/`NORMAL` according to the notify mode and splits long output.
- `_send_telegram_text()` escapes user/feed fields and posts to `sendMessage`.
- `--send-map` calls `sendPhoto` for `TELEGRAM_CHAT_ID` only; it does not support multiple chat IDs in the current implementation.
- Silent mode applies to text and photo delivery.

Telegram API response or network errors are printed and do not stop the rest of the local run.

### CLI Usage

Run a complete monitoring cycle:

```bash
./venv/bin/python main.py
```

Override the callsign:

```bash
./venv/bin/python main.py --callsign W6PQR
```

Skip Telegram delivery:

```bash
./venv/bin/python main.py --no-telegram
```

Test Telegram credentials:

```bash
./venv/bin/python main.py --test-telegram
```

Generate and send the paths map:

```bash
./venv/bin/python main.py --send-map
```

Combine independent options:

```bash
./venv/bin/python main.py --callsign W6PQR --no-telegram
./venv/bin/python main.py --test-telegram --callsign W6PQR
```

Refresh the DXpedition cache manually:

```bash
./venv/bin/python fetch_ng3k_dxpeditions.py
```

### macOS Cron Example

```cron
*/15 * * * * cd /Users/name/dxpedition-notifier && /Users/name/dxpedition-notifier/venv/bin/python /Users/name/dxpedition-notifier/main.py >> /Users/name/dxpedition-notifier/dx_monitor.log 2>&1
```

Use absolute paths. macOS cron may require folder access in **System Settings → Privacy & Security** when the project is located under `~/Documents`.

### Local JSON Examples

`dxpeditions.json`:

```json
{
  "updated_at": "2026-11-22 18:37 UTC",
  "source_url": "https://www.ng3k.com/Misc/adxo.html",
  "count": 57,
  "dxpeditions": []
}
```

A typical entry:

```json
{
  "callsign": "5X7W",
  "aliases": ["5X1Q"],
  "entity": "Uganda",
  "start_date": "2026-11-08",
  "end_date": "2026-12-29",
  "qsl_via": "LoTW",
  "notes": "Operations and planned modes",
  "source": "ng3k-adxo"
}
```

`seen_spots.json`:

```json
{
  "KH7X|15M": 1795372644.181173,
  "CT2GRF/P|10M": 1795372756.978312
}
```

`prop_cache.json`:

```json
{
  "fetched_at": 1795372644.181173,
  "data": {
    "sfi": 150,
    "k_index": 2,
    "a_index": 5,
    "xray": "C1.2",
    "condition": "Good HF / High bands",
    "source": "HamQSL/NOAA",
    "updated_utc": "2026-11-22 18:37 UTC"
  }
}
```

### Git and Security

The `.gitignore` should exclude runtime data, credentials, environments, caches, logs, editor settings, and macOS metadata:

```gitignore
dxpeditions.json
seen_spots.json
prop_cache.json
dx_paths_map.png
world_countries.geojson
.env
dx_monitor.log
.DS_Store
**/.DS_Store
.vscode/settings.json
__pycache__/
*.py[cod]
.venv/
venv/
```

Do not commit `.env` or Telegram credentials. If a runtime file was previously tracked, remove it from the index without deleting the local copy:

```bash
git rm --cached filename
git commit -m "Stop tracking local runtime file"
```

Check repository state with:

```bash
git status
git ls-files
```

### Troubleshooting

- **Telegram receives nothing:** verify token, chat ID, bot permissions, and notify mode; run `--test-telegram`.
- **A spot is still suppressed:** inspect `seen_spots.json` and `DEDUP_WINDOW_MINUTES`.
- **No DXpedition matches:** check NG3K freshness and active date windows.
- **Many spots are filtered:** set `REQUIRE_HOME_CONTINENT_SPOTTER=false` or verify the callsign prefix.
- **Unknown callsign continent:** extend `PREFIX_TO_CONTINENT` or override the callsign for one run.
- **Solar data unavailable:** a valid cache is reused; otherwise propagation reports `Unavailable` and monitoring continues.
- **Map not generated:** verify Pillow is installed and at least one DX match has resolvable coordinates.
- **Map photo not sent:** add `--send-map`, set bot credentials, and verify that no `--no-telegram` flag is present.
- **No HamQTH spots:** verify network access and the CSV feed response format.

### Failure Behavior

The project is designed for periodic automation:

- NG3K refresh failure preserves the existing local DXpedition list.
- HamQTH network errors stop the current cycle with an informative message.
- Propagation failures produce an unavailable or cached summary.
- Telegram failures do not revert the deduplication state.
- Missing Telegram credentials skip delivery rather than failing the run.
- Missing Pillow or map dependencies disable map generation and photo delivery gracefully.

---

# Dokumentazione in italiano

## Panoramica

DXpedition Notifier è uno strumento automatico per operatori radioamatoriali che scarica spot dal DX Cluster pubblico **HamQTH**, li confronta con spedizioni attive pubblicate da **NG3K ADXO**, applica filtri geografici ed euristiche, evita notifiche ripetute, valuta la propagazione, genera una mappa delle tratte e può inviare messaggi e immagini tramite **Telegram**.

Il progetto è adatto a cron e usa file JSON/cache locali senza database esterni. Richiede Python 3.10 o superiore.

## Funzionalità

- Scarica il feed CSV HamQTH rilevando separatori `^`, `;` o `,`.
- Normalizza frequenze MHz in kHz.
- Aggiorna una cache locale delle DXpedition da NG3K ADXO.
- Ricava il continente dai prefissi dei nominativi.
- Confronta chiamate complete, segmenti slash, alias e date di attività.
- Produce match `HIGH` e match euristici `NORMAL`.
- Deduplica per nominativo/banda o frequenza approssimativa.
- Legge dati solari HamQSL/NOAA e li salva in cache.
- Valuta grayline e propagazione in modo informativo.
- Genera una mappa PNG 1000×500 con tratte great-circle, paesi, luce/notte e grayline.
- Invia testo Telegram, messaggi silenziosi e facoltativamente la mappa PNG.
- Supporta override da CLI e test Telegram.

## Flusso di esecuzione

A ogni esecuzione normale `main.py`:

1. legge `.env` senza sovrascrivere variabili già presenti nell'ambiente;
2. determina callsign da `--callsign` o `MY_CALLSIGN`;
3. determina il continente locale tramite `prefixes.py`;
4. legge o aggiorna i dati solari;
5. carica o aggiorna `dxpeditions.json` da NG3K;
6. scarica gli spot HamQTH;
7. valuta continente dello spotter, match DXpedition ed euristiche;
8. elimina duplicati nelle finestre temporali;
9. ordina i nuovi match, `HIGH` prima di `NORMAL`;
10. stampa fino a 20 risultati;
11. genera la mappa se ci sono match e `Pillow` è disponibile;
12. invia testo Telegram secondo la modalità configurata;
13. invia facoltativamente la mappa con `--send-map`.

`--test-telegram` verifica Telegram e interrompe il flusso prima degli spot. `--no-telegram` impedisce testo e foto.

## Struttura del progetto

```text
dxpedition-notifier/
├── main.py                      # Pipeline, filtri, stato, Telegram e coordinamento mappa
├── fetch_ng3k_dxpeditions.py    # Scraper NG3K e generatore JSON
├── prefixes.py                  # Callsign -> continente
├── propagation.py               # Dati solari, cache, grayline e percorso
├── map_paths.py                 # Mappa PIL, great-circle, GeoJSON e foto Telegram
├── dxpeditions.json             # Cache DXpedition generata
├── seen_spots.json              # Timestamp deduplicazione (gitignored)
├── prop_cache.json              # Cache dati solari (gitignored)
├── dx_paths_map.png             # Mappa generata (gitignored)
├── world_countries.geojson      # Contorni paese opzionali (gitignored)
├── .env                         # Parametri e segreti locali (gitignored)
├── dx_monitor.log               # Output cron opzionale (gitignored)
├── venv/                        # Ambiente virtuale (gitignored)
├── .gitignore
└── README.md
```

L'importazione di propagazione e mappa è gestita come opzionale. Un'eventuale indisponibilità non impedisce il monitoraggio HamQTH di base.

## Requisiti

- Python 3.10 o superiore.
- `requests`.
- `beautifulsoup4`.
- `Pillow`.
- Accesso internet ai servizi HamQTH, NG3K, HamQSL/NOAA e Telegram, in base alle funzioni utilizzate.

Installazione:

```bash
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install requests beautifulsoup4 Pillow
```

Le dipendenze possono essere installate anche dal manifesto fornito:

```bash
./venv/bin/pip install -r requirements.txt
```

Eseguire la suite automatica:

```bash
./venv/bin/python -m pytest -q
```

## Configurazione

Creare `.env` nella directory principale:

```env
MY_CALLSIGN=IU4TRM
REQUIRE_HOME_CONTINENT_SPOTTER=true
MAX_DXPED_AGE_HOURS=12
DEDUP_WINDOW_MINUTES=30

TELEGRAM_BOT_TOKEN=token_del_bot
TELEGRAM_CHAT_ID=id_chat
TELEGRAM_NOTIFY_MODE=HIGH_AND_NORMAL
TELEGRAM_SILENT=false

MY_LAT=44.5000
MY_LON=11.3500
MY_QTH_LOCATOR=JN45AB
PROP_CACHE_MINUTES=45
```

| Variabile | Predefinito | Descrizione |
| :--- | :--- | :--- |
| `MY_CALLSIGN` | `IU4TRM` | Callsign predefinito e continente locale. |
| `REQUIRE_HOME_CONTINENT_SPOTTER` | `true` | Accetta solo spotter dello stesso continente. |
| `MAX_DXPED_AGE_HOURS` | `12` | Età massima della cache DXpedition prima del refresh. |
| `DEDUP_WINDOW_MINUTES` | `30` | Finestra di soppressione delle notifiche ripetute. |
| `TELEGRAM_BOT_TOKEN` | vuoto | Token del bot Telegram. |
| `TELEGRAM_CHAT_ID` | vuoto | ID utente, gruppo o canale Telegram. |
| `TELEGRAM_NOTIFY_MODE` | `HIGH_AND_NORMAL` | `HIGH` oppure `HIGH_AND_NORMAL`. |
| `TELEGRAM_SILENT` | `false` | Imposta le notifiche senza suono. |
| `MY_LAT` | centro continente | Latitudine facoltativa in gradi decimali. |
| `MY_LON` | centro continente | Longitudine facoltativa in gradi decimali. |
| `MY_QTH_LOCATOR` | `JN45AB` | Locator Maidenhead facoltativo. |
| `PROP_CACHE_MINUTES` | `45` | Durata dei dati solari in cache. |

I valori booleani attivi sono `1`, `true`, `yes`, `on`, ignorando maiuscole/minuscole. Le variabili già definite nell'ambiente non vengono sovrascritte dal `.env`.

## Parsing HamQTH

`fetch_dxc_spots()` usa timeout HTTP di 15 secondi e rileva il separatore dalla prima riga non vuota. Le righe con meno di quattro colonne vengono ignorate.

- Colonna 0: spotter, convertito in maiuscolo.
- Colonna 1: frequenza, convertita da MHz a kHz quando valida come numero decimale tra 1 e 60.
- Colonna 2: nominativo DX in maiuscolo.
- Colonna 3: commento.
- Colonna 4: campo UTC/data.
- Colonna 7: continente DX.
- Colonna 8: banda.
- Colonne 9 e 10: entità e ID DXCC.

## DXpedition e match

Lo scraper NG3K richiede righe HTML con almeno sette celle e date parseabili. Estrae:

- callsign principale;
- eventuali alias nelle note;
- entità;
- date di partenza e arrivo;
- via QSL;
- note operative;
- sorgente `ng3k-adxo`.

La corrispondenza `HIGH` considera il nominativo completo, i segmenti separati da `/`, gli alias e la data estratta da un campo UTC nel formato `YYYY-MM-DD`. Entrambi i limiti `start_date`/`end_date` vengono applicati se presenti.

La priorità `NORMAL` viene assegnata se il commento contiene una parola chiave configurata, il termine autonomo `UP`, una barra nel nominativo DX oppure un continente DX diverso dal continente locale.

### Filtri continente

`REQUIRE_HOME_CONTINENT_SPOTTER=true` accetta solo spot da spotter risolti nello stesso continente. La mappa dei prefissi è mantenuta in `prefixes.py`, ordinando i prefissi più lunghi prima dei più brevi.

I continenti riconosciuti sono `EU`, `NA`, `SA`, `AF`, `AS` e `OC`. Un callsign sconosciuto produce un fallback `EU` nell'esecuzione principale.

## Deduplicazione

`seen_spots.json` contiene chiavi e timestamp POSIX:

- con banda: `DX_CALL|BAND`;
- senza banda: `DX_CALL|~FREQkHz`, arrotondata a 2 kHz;
- se la frequenza non è numerica: `DX_CALL|frequenza-riga`.

All'avvio vengono rimossi gli elementi più vecchi della finestra `DEDUP_WINDOW_MINUTES`. Le chiavi sono registrate prima dell'invio Telegram, quindi rimangono deduplicate anche in caso di errore di rete o credenziali mancanti.

## Propagazione

Il modulo opzionale `propagation.py`:

- scarica XML da HamQSL/NOAA con timeout di 10 secondi;
- legge SFI, indici K/A e flare X-ray;
- conserva i dati in `prop_cache.json` per `PROP_CACHE_MINUTES`;
- usa una cache precedente come fallback in caso di refresh fallito;
- calcola un'elevazione approssimata del Sole alle coordinate locali;
- considera la grayline quando l'elevazione è vicina a ±6°.

La valutazione distingue bande alte, medie e basse, tratte intracontinentali, geomagnetiche disturbate, trans-equatoriali e ad alta latitudine. È informativa e non esclude gli spot.

## Mappa delle tratte

Il modulo `map_paths.py` usa Pillow e può leggere `world_countries.geojson`:

- genera un'immagine 1000×500;
- usa una proiezione equirettangolare;
- disegna griglia, campi giorno/notte e fascia grayline;
- evidenzia paesi coinvolti se il GeoJSON è disponibile;
- traccia archi great-circle fino alle coordinate DX;
- usa rosso per `HIGH`, ciano per `NORMAL`;
- mostra la posizione QTH, i callout, la data UTC e il numero delle tratte.

Se manca il GeoJSON, la mappa viene comunque generata senza contorni paesistici dettagliati. L'immagine predefinita è `dx_paths_map.png`.

## Telegram

I messaggi sono inviati con HTML Telegram. Il codice suddivide i blocchi limitandoli a circa 3900 caratteri.

- `HIGH`: soltanto match diretti alle DXpedition.
- `HIGH_AND_NORMAL`: entrambi i livelli.
- `TELEGRAM_SILENT=true`: aggiunge `disable_notification`.
- `--test-telegram`: verifica il bot senza leggere gli spot.
- `--send-map`: invia `dx_paths_map.png` con `sendPhoto`.

L'implementazione attuale invia la mappa al solo `TELEGRAM_CHAT_ID` configurato. Gli errori HTTP o di rete vengono registrati senza annullare il ciclo locale.

## Utilizzo CLI

Ciclo completo:

```bash
./venv/bin/python main.py
```

Sovrascrivere il callsign:

```bash
./venv/bin/python main.py --callsign W6PQR
```

Eseguire senza Telegram:

```bash
./venv/bin/python main.py --no-telegram
```

Verificare Telegram:

```bash
./venv/bin/python main.py --test-telegram
```

Inviare anche la mappa:

```bash
./venv/bin/python main.py --send-map
```

Aggiornamento manuale NG3K:

```bash
./venv/bin/python fetch_ng3k_dxpeditions.py
```

Combinazioni consentite:

```bash
./venv/bin/python main.py --callsign W6PQR --no-telegram
./venv/bin/python main.py --test-telegram --callsign W6PQR
```

## Automazione cron su macOS

```cron
*/15 * * * * cd /Users/nome/dxpedition-notifier && /Users/nome/dxpedition-notifier/venv/bin/python /Users/nome/dxpedition-notifier/main.py >> /Users/nome/dxpedition-notifier/dx_monitor.log 2>&1
```

Usare sempre percorsi assoluti. Se il progetto è dentro `~/Documents`, potrebbe essere necessario concedere a `cron` l'accesso alla directory o completo al disco nelle impostazioni macOS.

## Formati locali

### `dxpeditions.json`

```json
{
  "updated_at": "2026-11-22 18:37 UTC",
  "source_url": "https://www.ng3k.com/Misc/adxo.html",
  "count": 57,
  "dxpeditions": []
}
```

Ogni voce può contenere:

```json
{
  "callsign": "5X7W",
  "aliases": ["5X1Q"],
  "entity": "Uganda",
  "start_date": "2026-11-08",
  "end_date": "2026-12-29",
  "qsl_via": "LoTW",
  "notes": "Informazioni operative",
  "source": "ng3k-adxo"
}
```

### `seen_spots.json`

```json
{
  "KH7X|15M": 1795372644.181173,
  "CT2GRF/P|10M": 1795372756.978312
}
```

### `prop_cache.json`

```json
{
  "fetched_at": 1795372644.181173,
  "data": {
    "sfi": 150,
    "k_index": 2,
    "a_index": 5,
    "xray": "C1.2",
    "condition": "Good HF / High bands",
    "source": "HamQSL/NOAA",
    "updated_utc": "2026-11-22 18:37 UTC"
  }
}
```

## Git e sicurezza

`.gitignore` deve escludere almeno:

```gitignore
dxpeditions.json
seen_spots.json
prop_cache.json
dx_paths_map.png
world_countries.geojson
.env
dx_monitor.log
.DS_Store
**/.DS_Store
.vscode/settings.json
__pycache__/
*.py[cod]
.venv/
venv/
```

Non inserire token o chat ID nei sorgenti o negli screenshot. Per togliere dall'indice un file già tracciato:

```bash
git rm --cached nome-file
git commit -m "Stop tracking local runtime file"
```

Verifica lo stato Git con:

```bash
git status
git ls-files
```

## Risoluzione problemi

- **Telegram non riceve:** verificare token, chat ID, permessi del bot e modalità priorità; usare `--test-telegram`.
- **Uno spot viene saltato:** controllare `seen_spots.json` e `DEDUP_WINDOW_MINUTES`.
- **Nessun match DXpedition:** controllare la lista NG3K e le date attività.
- **Troppi spot esclusi:** disattivare il filtro continente o verificare il prefisso callsign.
- **Continente errato:** estendere `PREFIX_TO_CONTINENT` oppure usare `--callsign` per un'unica esecuzione.
- **Dati solari assenti:** usare la cache valida oppure accettare il valore `Unavailable`.
- **Mappa assente:** installare Pillow e verificare che gli spot abbiano coordinate risolvibili.
- **Foto non inviata:** aggiungere `--send-map`, impostare le credenziali e non usare `--no-telegram`.
- **Nessun spot HamQTH:** verificare rete e formato di risposta del feed.

## Comportamento in caso di errore

- Il fallimento NG3K conserva la lista locale precedente.
- Il fallimento HamQTH interrompe soltanto il ciclo corrente.
- Il fallimento propagazione produce dati cache o `Unavailable`.
- Il fallimento Telegram non annulla le chiavi di deduplicazione già salvate.
- Le credenziali mancanti saltano gli invii con messaggi informativi.
- La mancanza di Pillow o del modulo mappa disattiva solo la mappa e la foto.