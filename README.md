# DXpedition Notifier

An automated DX Cluster monitoring tool for amateur radio operators. The project downloads live spots from **HamQTH**, cross-references them with active expeditions published by **NG3K ADXO**, optionally evaluates propagation and grayline conditions through HamQSL/NOAA data, and sends formatted alerts to **Telegram**.

It is designed for manual runs or scheduled jobs and uses local JSON files instead of an external database.

## Main Features

### HamQTH DX Cluster ingestion

- Downloads the CSV feed from `https://www.hamqth.com/dxc_csv.php`.
- Automatically recognizes `^`, `;`, or `,` delimiters.
- Converts frequencies expressed in MHz to kHz.
- Keeps the spotter, DX callsign, frequency, comment, UTC time, DX continent, band, DXCC entity, and original row.
- Uses a 15-second network timeout and reports network errors clearly.

### DXpedition database

- Loads `dxpeditions.json`, a local index containing update metadata.
- Refreshes the list from NG3K ADXO when the file is missing or older than `MAX_DXPED_AGE_HOURS`.
- The default maximum age is 12 hours.
- Beautiful Soup extracts the primary callsign, aliases, entity, dates, QSL route, and notes.
- If the refresh fails or returns no entries, the existing local list is preserved.

### Filtering and priorities

Each spot is checked against the configured spotter-continent filter and classified as `HIGH` or `NORMAL`.

#### Home-continent spotter filter

With `REQUIRE_HOME_CONTINENT_SPOTTER=true`, only spots reported from the same continent as the configured callsign are accepted. `prefixes.py` resolves the continent from the callsign prefix. If a callsign is not recognized, the application falls back to `EU`.

Set `REQUIRE_HOME_CONTINENT_SPOTTER=false` to disable this filter.

#### `HIGH` priority

A spot is `HIGH` when its DX callsign matches an active DXpedition. Matching includes:

- the complete callsign;
- each slash-separated callsign segment;
- aliases extracted from the NG3K notes;
- the start/end date window from `start_date` and `end_date`.

If the UTC field contains `YYYY-MM-DD`, the match is checked against that date. If no date is present, date-window parsing cannot restrict the match.

#### `NORMAL` priority

A spot can receive `NORMAL` priority through one or more heuristics, even if it is not a direct DXpedition match:

- Comment keywords: `dxped`, `dx-ped`, `dx expedition`, `expedition`, `qsx`, `split`, `iota`, `sota`, `pota`, `wwff`.
- The standalone word `UP` in the comment.
- A `/` in the DX callsign.
- A DX continent different from the configured home continent.

### Deduplication

Notified spot keys are stored in `seen_spots.json`:

- Default key: `DX_CALL|BAND`.
- When a band is missing: `DX_CALL|~FREQkHz`, with frequency rounded to approximately 2 kHz buckets.
- Entries older than `DEDUP_WINDOW_MINUTES` are automatically removed.
- The default window is 30 minutes.

The state file is updated after each run, including runs that produce no notification.

### Propagation information

If `propagation.py` is available, `main.py` optionally enriches alerts with HamQSL/NOAA data:

- Downloads solar XML data from HamQSL.
- Reads the Solar Flux Index (SFI), K index, A index, and X-ray activity.
- Caches data in `prop_cache.json` for `PROP_CACHE_MINUTES` minutes.
- Uses stale cache data as a fallback when live data cannot be retrieved.
- Adds a band-, geomagnetic-, intercontinental-, trans-equatorial-, and grayline-aware path note.
- Keeps propagation evaluation informational: it does not reject matching spots.

Custom `MY_LAT` and `MY_LON` values can be supplied. Otherwise, approximate continent coordinates are used.

### Telegram notifications

- `HIGH` mode sends direct DXpedition matches only.
- `HIGH_AND_NORMAL` sends both priority classes.
- Notifications use HTML formatting, local/UTC timestamps, solar conditions, spot details, and path notes.
- `TELEGRAM_SILENT=true` enables `disable_notification`.
- Long alerts are split into Telegram-compatible parts.
- `--test-telegram` sends a test message without processing the DX Cluster feed.

HIGH matches are displayed and sent before NORMAL matches.

## Project Structure

```text
dxpedition-notifier/
├── main.py                      # CLI pipeline, filtering, deduplication, and Telegram
├── fetch_ng3k_dxpeditions.py    # NG3K ADXO scraper and JSON normalizer
├── prefixes.py                  # Callsign-prefix-to-continent lookup
├── propagation.py               # Solar data, propagation assessment, and grayline
├── dxpeditions.json             # Local/generated DXpedition cache
├── seen_spots.json              # Local deduplication state (gitignored)
├── prop_cache.json              # Solar propagation cache (gitignored)
├── .env                         # Local parameters and secrets (gitignored)
├── README.md                    # Project documentation
├── dx_monitor.log               # Optional cron log (gitignored)
├── venv/                        # Local Python environment (gitignored)
└── .gitignore
```

If `propagation.py` or its dependencies are unavailable, `main.py` continues without propagation enrichment.

## Requirements

- macOS, Linux, or another compatible Python environment.
- Python 3.10 or newer; the source uses annotations such as `str | None`.
- Python packages:
  - `requests`
  - `beautifulsoup4`

## Installation

```bash
git clone <repository-url> dxpedition-notifier
cd dxpedition-notifier

python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install requests beautifulsoup4
```

Create `.env` in the project root:

```env
MY_CALLSIGN=IU4TRM
REQUIRE_HOME_CONTINENT_SPOTTER=true
MAX_DXPED_AGE_HOURS=12
DEDUP_WINDOW_MINUTES=30

TELEGRAM_BOT_TOKEN=123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
TELEGRAM_CHAT_ID=-1001234567890
TELEGRAM_NOTIFY_MODE=HIGH_AND_NORMAL
TELEGRAM_SILENT=false

MY_LAT=44.5000
MY_LON=11.3500
PROP_CACHE_MINUTES=45
```

Existing process environment variables are not overwritten by `_load_dotenv()`.

## Configuration Reference

| Variable | Default | Description |
| :--- | :--- | :--- |
| `MY_CALLSIGN` | `IU4TRM` | Callsign used to determine the home continent. |
| `REQUIRE_HOME_CONTINENT_SPOTTER` | `true` | Accept only spotters from the home continent. |
| `MAX_DXPED_AGE_HOURS` | `12` | Maximum age of `dxpeditions.json` in hours. |
| `DEDUP_WINDOW_MINUTES` | `30` | Time window for duplicate notifications. |
| `TELEGRAM_BOT_TOKEN` | `""` | Telegram Bot API token. |
| `TELEGRAM_CHAT_ID` | `""` | Telegram user, group, or channel destination. |
| `TELEGRAM_NOTIFY_MODE` | `HIGH_AND_NORMAL` | `HIGH` or `HIGH_AND_NORMAL`. |
| `TELEGRAM_SILENT` | `false` | Enables Telegram silent notifications. |
| `MY_LAT` | approximate continent center | Latitude for grayline calculations. |
| `MY_LON` | approximate continent center | Longitude for grayline calculations. |
| `PROP_CACHE_MINUTES` | `45` | Lifetime of the solar-data cache. |

Boolean values accepted as enabled: `1`, `true`, `yes`, `on`, case-insensitively.

## Usage

Run a complete monitoring cycle:

```bash
./venv/bin/python main.py
```

Send a Telegram test message:

```bash
./venv/bin/python main.py --test-telegram
```

Run without Telegram delivery:

```bash
./venv/bin/python main.py --no-telegram
```

Override the callsign for one run:

```bash
./venv/bin/python main.py --callsign K1ABC
```

Refresh the NG3K DXpedition cache manually:

```bash
./venv/bin/python fetch_ng3k_dxpeditions.py
```

## macOS Cron Example

Run every 15 minutes:

```cron
*/15 * * * * cd /Users/name/dxpedition-notifier && /Users/name/dxpedition-notifier/venv/bin/python /Users/name/dxpedition-notifier/main.py >> /Users/name/dxpedition-notifier/dx_monitor.log 2>&1
```

Use absolute paths. On macOS, `cron` may require folder permissions under **System Settings → Privacy & Security**, especially for folders under `~/Documents`.

## Local Data Formats

`dxpeditions.json` contains metadata and an array of DXpedition entries:

```json
{
  "updated_at": "2026-11-22 18:37 UTC",
  "source_url": "https://www.ng3k.com/Misc/adxo.html",
  "count": 57,
  "dxpeditions": []
}
```

`seen_spots.json` maps deduplicated keys to POSIX timestamps:

```json
{
  "KH7X|15M": 1795372644.181173,
  "CT2GRF/P|10M": 1795372756.978312
}
```

`prop_cache.json` stores a retrieval timestamp and the latest available solar payload.

## Git and Security

The current `.gitignore` excludes runtime state, credentials, Python environments, logs, editor settings, and macOS metadata, including:

```gitignore
dxpeditions.json
seen_spots.json
prop_cache.json
.env
*.pyc
__pycache__/
venv/
.DS_Store
**/.DS_Store
.vscode/settings.json
dx_monitor.log
```

Do not commit Telegram credentials or `.env`. If a file was previously committed, remove it from the index without deleting the local copy:

```bash
git rm --cached .DS_Store
git commit -m "Stop tracking macOS .DS_Store"
```

Verify tracked and untracked files with:

```bash
git status
git ls-files
```

## Troubleshooting

- **Telegram receives nothing:** verify `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, bot permissions, and `TELEGRAM_NOTIFY_MODE`; run `--test-telegram`.
- **The same spot is ignored:** check `seen_spots.json` and `DEDUP_WINDOW_MINUTES`.
- **No matches are found:** check `REQUIRE_HOME_CONTINENT_SPOTTER` and the callsign continent mapping.
- **DXpedition data is stale:** run `fetch_ng3k_dxpeditions.py` manually and verify network access to NG3K.
- **Solar data is unavailable:** the application continues using cache, or reports `Unavailable` if no data exists.
- **A callsign resolves to the wrong continent:** use `--callsign` for a one-off run or extend `PREFIX_TO_CONTINENT` in `prefixes.py`.

NG3K, HamQTH, HamQSL, or Telegram outages do not need to stop the remaining monitoring logic permanently: the application reports the failure and preserves available local state whenever possible.

---

# Dokumentazione in italiano

# DXpedition Notifier

Uno strumento automatico per monitorare lo DX Cluster tramite il feed CSV pubblico di **HamQTH**, incrociare gli spot con le spedizioni attive pubblicate da **NG3K ADXO**, valutare la propagazione tramite dati solari HamQSL/NOAA e inviare allarmi HTML tramite **Telegram**.

Il progetto è pensato per esecuzioni periodiche da terminale o `cron`, con filtri configurabili, stato locale persistente e nessuna dipendenza da database esterni.

---

## Funzionalità principali

### Monitoraggio dello DX Cluster

- Scarica gli spot da `https://www.hamqth.com/dxc_csv.php`.
- Rileva automaticamente il separatore `^`, `;` o `,`.
- Normalizza le frequenze espresse in MHz nel formato kHz.
- Conserva nominativo, frequenza, commento, ora UTC, continente DX, banda, entità DXCC e riga originale.
- Usa un timeout HTTP di 15 secondi e restituisce messaggi chiari in caso di problemi di rete.

### Lista delle DXpedition

- Legge `dxpeditions.json`, un indice locale con metadati di aggiornamento.
- Aggiorna automaticamente la lista da NG3K ADXO se il file manca oppure è più vecchio del limite configurato.
- Il limite predefinito è `MAX_DXPED_AGE_HOURS=12` ore.
- La pagina viene analizzata con Beautiful Soup; vengono estratti nominativo principale, alias, entità, date, QSL e note.
- Se il refresh di rete fallisce o restituisce zero risultati, il file locale esistente viene conservato.

### Filtri e priorità

Ogni spot viene prima valutato contro il continente dello spotter, quindi classificato come `HIGH` o `NORMAL`.

#### Filtro continente dello spotter

`REQUIRE_HOME_CONTINENT_SPOTTER=true` permette di accettare soltanto spot provenienti da spotter appartenenti al continente del proprio callsign. Il continente viene ricavato da `prefixes.py`; se il callsign non è riconosciuto, il progetto usa `EU` come fallback.

Il parametro può essere disattivato impostando `REQUIRE_HOME_CONTINENT_SPOTTER=false`.

#### Match `HIGH`

Uno spot è `HIGH` quando il nominativo DX corrisponde a una DXpedition attiva. Il confronto considera:

- chiamata completa;
- singoli segmenti separati da `/`;
- alias estratti dalle note NG3K;
- finestra temporale tra `start_date` ed `end_date`.

Se UTC dello spot contiene una data `YYYY-MM-DD`, la corrispondenza viene verificata all’interno della spedizione. Se la data non è presente, le regole temporali vengono applicate solo finché il formato può essere verificato.

#### Match `NORMAL`

Uno spot può ottenere priorità `NORMAL` anche senza corrispondenza diretta nella lista, se il commento contiene una delle parole chiave configurate:

`dxped`, `dx-ped`, `dx expedition`, `expedition`, `qsx`, `split`, `iota`, `sota`, `pota`, `wwff`

Sono inoltre applicate le euristiche:

- parola autonoma `UP` nel commento;
- slash `/` nel nominativo DX;
- continente DX diverso dal continente di riferimento.

### Deduplicazione

Lo stato dei nuovi spot viene salvato in `seen_spots.json`.

- Chiave predefinita: `DX_CALL|BAND`.
- Se manca la banda, usa una frequenza arrotondata a intervalli di circa 2 kHz: `DX_CALL|~FREQkHz`.
- Gli elementi scaduti oltre `DEDUP_WINDOW_MINUTES` vengono rimossi automaticamente.
- Valore predefinito della finestra: 30 minuti.

Il file viene aggiornato ad ogni ciclo, anche quando nessun nuovo messaggio viene inviato.

### Informazioni sulla propagazione

Se il modulo `propagation.py` è disponibile, il programma può integrare i dati solari e una valutazione informativa del percorso.

- Scarica dati XML da HamQSL/NOAA.
- Legge Solar Flux Index (SFI), indici K e A e tipo di flare solare.
- Conserva i dati in `prop_cache.json` per evitare richieste troppo frequenti.
- Usa dati da cache alla scadenza o dati precedenti come fallback in caso di errore di rete.
- Valuta bande alte/basse, disturbo geomagnetico, tratte intercontinentali, trans-equatoriali e finestre di grayline.
- Aggiunge una nota al log e ai messaggi Telegram, ma non elimina lo spot dal filtro.

La valutazione usa coordinate personalizzate se definite oppure coordinate indicative del continente. È puramente orientativa e non sostituisce previsioni professionali.

### Notifiche Telegram

- Modalità `HIGH`: invia soltanto corrispondenze dirette alle DXpedition.
- Modalità `HIGH_AND_NORMAL`: invia sia `HIGH` sia `NORMAL`.
- Messaggi in HTML con timestamp locale e UTC, richieste solari e dettagli dello spot.
- Flag opzionale `disable_notification` per le notifiche silenziose.
- Suddivisione automatica in parti quando il contenuto potrebbe superare il limite Telegram.
- Comando `--test-telegram` per verificare token e chat senza processare gli spot.

I match sono ordinati prima per priorità `HIGH` e poi `NORMAL` nella console e nei messaggi Telegram.

---

## Struttura del progetto

```text
dxpedition-notifier/
├── main.py                      # Pipeline principale, CLI, filtri, deduplica e Telegram
├── fetch_ng3k_dxpeditions.py    # Scraper NG3K ADXO e normalizzazione JSON
├── prefixes.py                  # Mappa prefissi callsign -> continente
├── propagation.py               # Dati solari, propagazione e grayline
├── dxpeditions.json             # Cache locale delle DXpedition (generata/aggiornata)
├── seen_spots.json              # Stato locale della deduplicazione (gitignored)
├── prop_cache.json              # Cache dati propagazione (gitignored)
├── .env                         # Parametri locali e segreti (gitignored)
├── README.md                    # Documentazione del progetto
├── dx_monitor.log               # Log opzionale usato da cron (gitignored)
├── venv/                        # Ambiente Python locale (gitignored)
└── .gitignore
```

Nota: `main.py` importa `propagation.py` facoltativamente. Se il modulo o le sue dipendenze non sono disponibili, il monitoraggio normale continua a funzionare senza analisi propagazione.

---

## Requisiti

- macOS, Linux o un altro ambiente Python compatibile.
- Python 3.10 o superiore, perché il codice usa annotazioni moderne come `str | None`.
- Pacchetti Python:
  - `requests`
  - `beautifulsoup4`

Esempio per macOS/Linux:

```bash
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install requests beautifulsoup4
```

---

## Installazione e configurazione

### 1. Clona il progetto

```bash
git clone <URL_DEL_REPOSITORY> dxpedition-notifier
cd dxpedition-notifier
```

### 2. Crea l'ambiente virtuale

```bash
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install requests beautifulsoup4
```

### 3. Crea il file `.env`

Creare `.env` nella directory principale:

```env
MY_CALLSIGN=IU4TRM
REQUIRE_HOME_CONTINENT_SPOTTER=true
MAX_DXPED_AGE_HOURS=12
DEDUP_WINDOW_MINUTES=30

TELEGRAM_BOT_TOKEN=123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
TELEGRAM_CHAT_ID=-1001234567890
TELEGRAM_NOTIFY_MODE=HIGH_AND_NORMAL
TELEGRAM_SILENT=false

MY_LAT=44.5000
MY_LON=11.3500
PROP_CACHE_MINUTES=45
```

Le variabili non impostate usano i valori predefiniti riportati sotto. Il file `.env` viene letto automaticamente da `main.py` senza sovrascrivere variabili già presenti nell'ambiente del sistema.

### 4. Configura Telegram

1. Apri una conversazione con `@BotFather`.
2. Crea o seleziona un bot e copia il token.
3. Inserisci il token in `TELEGRAM_BOT_TOKEN`.
4. Determina l'ID della chat, del gruppo o del canale Telegram.
5. Per un gruppo o canale, aggiungi il bot con permessi sufficienti a scrivere messaggi.

Il `chat_id` deve essere scritto esattamente come restituito da Telegram; i valori numerici negativi per gruppi e canali devono essere mantenuti con il meno iniziale.

---

## Riferimento configurazione

| Variabile | Valore predefinito | Descrizione |
| :--- | :--- | :--- |
| `MY_CALLSIGN` | `IU4TRM` | Callsign usato per ricavare il continente locale. |
| `REQUIRE_HOME_CONTINENT_SPOTTER` | `true` | Accetta solo spot inviati da spotter dello stesso continente. |
| `MAX_DXPED_AGE_HOURS` | `12` | Età massima, in ore, della cache `dxpeditions.json`. |
| `DEDUP_WINDOW_MINUTES` | `30` | Finestra temporale di deduplicazione degli spot notificati. |
| `TELEGRAM_BOT_TOKEN` | `""` | Token API del bot Telegram. |
| `TELEGRAM_CHAT_ID` | `""` | Destinatario Telegram: utente, gruppo o canale. |
| `TELEGRAM_NOTIFY_MODE` | `HIGH_AND_NORMAL` | `HIGH` soltanto; `HIGH_AND_NORMAL` per entrambe le priorità. |
| `TELEGRAM_SILENT` | `false` | Imposta `disable_notification` nelle chiamate Telegram. |
| `MY_LAT` | centro indicativo del continente | Latitudine geografica in decimali per il calcolo della grayline. |
| `MY_LON` | centro indicativo del continente | Longitudine geografica in decimali per il calcolo della grayline. |
| `PROP_CACHE_MINUTES` | `45` | Durata della cache dei dati solari in `prop_cache.json`. |

Valori booleani riconosciuti come attivi: `1`, `true`, `yes`, `on`, senza distinzione maiuscole/minuscole.

---

## Utilizzo

### Ciclo completo di monitoraggio

```bash
./venv/bin/python main.py
```

Esempio di operazioni svolte:

1. determina callsign e continente;
2. legge o aggiorna la lista DXpedition;
3. legge i dati solari/cache;
4. scarica gli spot HamQTH;
5. applica filtri e deduplicazione;
6. stampa i nuovi match;
7. salva lo stato;
8. invia gli avvisi Telegram consentiti dalla modalità configurata.

### Verifica Telegram

```bash
./venv/bin/python main.py --test-telegram
```

In questa modalità viene inviato un solo messaggio di prova e il monitoraggio degli spot non viene avviato.

### Escludere l'invio Telegram

```bash
./venv/bin/python main.py --no-telegram
```

Utile per diagnosticare i match, cron in ambienti di prova o esecuzioni manuali senza notifiche.

### Sovrascrivere il callsign

```bash
./venv/bin/python main.py --callsign K1ABC
```

La chiamata passata da CLI ha priorità su `MY_CALLSIGN` nel file `.env`.

### Aggiornare manualmente la lista NG3K

```bash
./venv/bin/python fetch_ng3k_dxpeditions.py
```

Questo comando riscrive `dxpeditions.json` con i dati estratti e mostra fino a otto voci estratte.

### Esempi combinati

```bash
./venv/bin/python main.py --callsign IU4ABC --no-telegram
./venv/bin/python main.py --test-telegram --callsign K1ABC
```

---

## Automazione con cron su macOS

Esempio ogni 15 minuti:

```cron
*/15 * * * * cd /Users/nome/dxpedition-notifier && /Users/nome/dxpedition-notifier/venv/bin/python /Users/nome/dxpedition-notifier/main.py >> /Users/nome/dxpedition-notifier/dx_monitor.log 2>&1
```

Usare sempre percorsi assoluti. Le righe `>> ... 2>&1` separano l'output e gli errori dal terminale e li salvano nel log.

Su macOS potrebbe essere necessario concedere a `cron` l'accesso alle cartelle in:

**Impostazioni di Sistema → Privacy e sicurezza → Accesso completo al disco**

oppure consentire l'accesso alla directory specifica interessata, soprattutto se il progetto si trova sotto `~/Documents`.

---

## Formati dei dati locali

### `dxpeditions.json`

```json
{
  "updated_at": "2026-11-22 18:37 UTC",
  "source_url": "https://www.ng3k.com/Misc/adxo.html",
  "count": 57,
  "dxpeditions": []
}
```

Ogni voce contiene tipicamente:

```json
{
  "callsign": "5X7W",
  "aliases": ["5X1Q"],
  "entity": "Uganda",
  "start_date": "2026-11-08",
  "end_date": "2026-12-29",
  "qsl_via": "LoTW",
  "notes": "Testo e modalità di operazione",
  "source": "ng3k-adxo"
}
```

### `seen_spots.json`

Contiene chiavi deduplicate associate a timestamp POSIX:

```json
{
  "KH7X|15M": 1795372644.181173,
  "CT2GRF/P|10M": 1795372756.978312
}
```

### `prop_cache.json`

Contiene il timestamp di recupero e l'ultimo payload solare disponibile:

```json
{
  "fetched_at": 1795372644.181173,
  "data": {
    "sfi": 150,
    "k_index": 2,
    "a_index": 5,
    "xray": "C1.2",
    "condition": "Good HF / High bands",
    "source": "HamQSL/NOAA"
  }
}
```

---

## Git e sicurezza

Il file `.gitignore` attuale include, tra gli altri:

```gitignore
dxpeditions.json
seen_spots.json
prop_cache.json
.env
*.pyc
__pycache__/
venv/
.DS_Store
**/.DS_Store
.vscode/settings.json
dx_monitor.log
```

Prima di pubblicare il repository:

- non inserire token Telegram o credenziali in sorgenti o screenshot;
- verificare con `git status` che `.env`, cache e log non siano tracciati;
- usare `git rm --cached <file>` per togliere dall'indice un file già tracciato senza eliminarlo dal disco;
- evitare di committare `.DS_Store` e configurazioni personali dell'editor.

Se `.DS_Store` era già stato committato:

```bash
git rm --cached .DS_Store
git commit -m "Stop tracking macOS .DS_Store"
```

Per verificare i file tracciati dal repository:

```bash
git ls-files
```

---

## Risoluzione problemi

### Telegram non riceve messaggi

- verificare token e chat ID nel `.env`;
- eseguire `./venv/bin/python main.py --test-telegram`;
- verificare che il bot sia membro del gruppo/canale e abbia permessi di scrittura;
- controllare che `TELEGRAM_NOTIFY_MODE` includa la priorità attesa.

### Nessun nuovo spot viene inviato

- verificare `seen_spots.json`: la chiave dello stesso DX sulla stessa banda può essere in finestra di deduplicazione;
- aumentare o diminuire `DEDUP_WINDOW_MINUTES`;
- controllare `REQUIRE_HOME_CONTINENT_SPOTTER`;
- usare `--no-telegram` per mostrare i match trovati senza invio.

### Lista DXpedition non viene aggiornata

- controllare la connettività verso `https://www.ng3k.com/Misc/adxo.html`;
- verificare `MAX_DXPED_AGE_HOURS`;
- eseguire manualmente `fetch_ng3k_dxpeditions.py`;
- in caso di errore viene mantenuta la lista locale valida disponibile.

### Dati solari indisponibili

- il programma può usare `prop_cache.json` se contiene dati ancora nel formato atteso;
- in assenza di dati nuovi o cache, mostra `Unavailable` e continua il monitoraggio;
- verificare l'accesso a `https://www.hamqsl.com/solarxml.php`.

### Callsign riconosciuto nel continente sbagliato

- usare `--callsign` per la singola esecuzione;
- verificare che `MY_CALLSIGN` abbia il prefisso corretto;
- controllare o estendere `PREFIX_TO_CONTINENT` in `prefixes.py`.

---

## Comportamento in caso di errore

Il progetto privilegia la resilienza durante i cicli automatizzati:

- un errore sul refresh NG3K non cancella la lista locale;
- uno spot live non viene scartato dalla valutazione propagazione se quel modulo fallisce;
- dati solari mancanti producono una condizione `Unavailable` anziché bloccare il programma;
- errori Telegram vengono registrati in console/log e non impediscono la deduplicazione degli altri dati;
- se non esistono credenziali Telegram, l'invio viene saltato con un messaggio informativo.

Questo rende il programma adatto a esecuzioni ripetute, ma non garantisce disponibilità durante outage di HamQTH, NG3K, HamQSL o Telegram.