import argparse
import csv
import datetime
import html
import io
import json
import os
import re
import time
import requests

from prefixes import get_call_continent

try:
    from propagation import (
        CONTINENT_REFERENCE_COORDS,
        assess_path_for_spot,
        format_prop_log,
        format_prop_telegram_html,
        get_propagation_summary,
    )
except ImportError:
    CONTINENT_REFERENCE_COORDS = {}
    assess_path_for_spot = None
    format_prop_log = None
    format_prop_telegram_html = None
    get_propagation_summary = None

try:
    from map_paths import DEFAULT_MAP_OUT, render_paths_map, send_photo_to_chats
except ImportError:
    DEFAULT_MAP_OUT = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "dx_paths_map.png"
    )
    render_paths_map = None
    send_photo_to_chats = None

HAMQTH_DXC_URL = "https://www.hamqth.com/dxc_csv.php"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOTENV_FILE = os.path.join(BASE_DIR, ".env")
LOCAL_DXPED_FILE = os.path.join(BASE_DIR, "dxpeditions.json")
SEEN_SPOTS_FILE = os.path.join(BASE_DIR, "seen_spots.json")


def _load_dotenv(dotenv_path: str = DOTENV_FILE) -> None:
    """Carica variabili chiave=valore da .env senza sovrascrivere quelle già nell'ambiente."""
    if not os.path.exists(dotenv_path):
        return
    try:
        with open(dotenv_path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith("#") or "=" not in s:
                    continue
                key, val = s.split("=", 1)
                key = key.strip()
                val = val.strip()
                if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
                    val = val[1:-1]
                if key and key not in os.environ:
                    os.environ[key] = val
    except OSError as err:
        print(f"Avviso: impossibile leggere .env ({err})")


# Carica .env prima di leggere le variabili di configurazione
_load_dotenv()

MAX_DXPED_AGE_HOURS = float(os.getenv("MAX_DXPED_AGE_HOURS", "12"))
DEDUP_WINDOW_MINUTES = int(os.getenv("DEDUP_WINDOW_MINUTES", "30"))

# Identità della stazione di default da .env / ambiente
DEFAULT_CALLSIGN = os.getenv("MY_CALLSIGN", "IU4TRM").strip().upper()

# Se True, considera validi solo gli spot inviati da spotter nello stesso continente di riferimento
REQUIRE_HOME_CONTINENT_SPOTTER = os.getenv("REQUIRE_HOME_CONTINENT_SPOTTER", "true").strip().lower() in (
    "1", "true", "yes", "on"
)

# Priorità da notificare su Telegram: "HIGH" oppure "HIGH_AND_NORMAL"
TELEGRAM_NOTIFY_MODE = os.getenv("TELEGRAM_NOTIFY_MODE", "HIGH_AND_NORMAL").strip().upper()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
TELEGRAM_SILENT = os.getenv("TELEGRAM_SILENT", "false").strip().lower() in (
    "1", "true", "yes", "on"
)

DX_PHRASE_KEYWORDS = (
    "dxped",
    "dx-ped",
    "dx expedition",
    "expedition",
    "qsx",
    "split",
    "iota",
    "sota",
    "pota",
    "wwff",
)

UP_WORD_PATTERN = re.compile(r"\bup\b", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Monitor DX Cluster locale con filtri per callsign/continente e notifiche Telegram."
    )
    parser.add_argument(
        "-c",
        "--callsign",
        default=None,
        help="Callsign da usare per questa esecuzione (sovrascrive MY_CALLSIGN nel .env).",
    )
    parser.add_argument(
        "--no-telegram",
        action="store_true",
        help="Esegue il controllo senza inviare messaggi su Telegram.",
    )
    parser.add_argument(
        "--test-telegram",
        action="store_true",
        help="Invia un messaggio di test su Telegram per verificare token e chat_id.",
    )
    parser.add_argument(
        "--send-map",
        action="store_true",
        help="Allega anche la mappa delle tratte su Telegram (disattivato per default).",
    )
    return parser.parse_args()


def normalize_freq_khz(freq_str: str) -> str:
    """Converte la frequenza in kHz se sembra espressa in MHz (es. 14.200 -> 14200.0)."""
    cleaned = freq_str.strip().replace(",", ".")
    try:
        val = float(cleaned)
        if 1.0 <= val <= 60.0 and "." in cleaned:
            return f"{val * 1000:.1f}"
        return f"{val:.1f}"
    except ValueError:
        return freq_str.strip()


def resolve_dx_continent(spot: dict) -> str:
    """Ricava il continente della stazione DX dal feed o, in alternativa, dal prefisso del callsign."""
    feed_cont = (spot.get("dx_continent") or "").strip().upper()
    if feed_cont in {"EU", "NA", "SA", "AF", "AS", "OC"}:
        return feed_cont
    return get_call_continent(spot.get("dx_call", "")) or ""


def is_home_continent_spotter(spotter: str, home_continent: str) -> bool:
    """Verifica se chi ha fatto lo spot appartiene al continente di riferimento."""
    return get_call_continent(spotter) == home_continent


def _save_local_dxpeditions(data: dict, path: str = LOCAL_DXPED_FILE) -> None:
    """Salva la lista DXpedition in locale."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except OSError as err:
        print(f"Avviso: impossibile salvare il file locale DXpedition ({err})")


def _parse_updated_at(updated_str: str | None, fallback_path: str) -> datetime.datetime | None:
    """Ricava un datetime UTC da updated_at o, in mancanza, da mtime del file locale."""
    if updated_str:
        cleaned = updated_str.replace("UTC", "").strip()
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                dt = datetime.datetime.strptime(cleaned, fmt)
                return dt.replace(tzinfo=datetime.timezone.utc)
            except ValueError:
                continue

    if os.path.exists(fallback_path):
        try:
            mtime = os.path.getmtime(fallback_path)
            return datetime.datetime.fromtimestamp(mtime, tz=datetime.timezone.utc)
        except OSError:
            return None

    return None


def _is_dxpeditions_stale(
    updated_at: str | None,
    local_path: str,
    max_age_hours: float = MAX_DXPED_AGE_HOURS,
) -> bool:
    """Restituisce True se il file è assente o più vecchio di max_age_hours."""
    last_dt = _parse_updated_at(updated_at, local_path)
    if last_dt is None:
        return True
    age = datetime.datetime.now(datetime.timezone.utc) - last_dt
    return age.total_seconds() >= max_age_hours * 3600


def _refresh_from_ng3k(local_path: str = LOCAL_DXPED_FILE) -> tuple[list[dict], str] | None:
    """Aggiorna la lista direttamente da NG3K e la salva in locale."""
    try:
        from fetch_ng3k_dxpeditions import ADXO_URL, fetch_ng3k_dxpeditions
    except ImportError as err:
        print(f"Avviso: impossibile importare fetch_ng3k_dxpeditions ({err}).")
        return None

    try:
        entries = fetch_ng3k_dxpeditions()
        if not entries:
            print("Avviso: NG3K ha restituito 0 voci, mantengo la lista esistente.")
            return None

        now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        payload = {
            "updated_at": now_str,
            "source_url": ADXO_URL,
            "count": len(entries),
            "dxpeditions": entries,
        }
        _save_local_dxpeditions(payload, local_path)
        return entries, f"ng3k-refresh ({now_str})"
    except Exception as err:
        print(f"Avviso: refresh da NG3K fallito ({err}), mantengo la lista esistente.")
        return None


def load_dxpeditions(
    local_path: str = LOCAL_DXPED_FILE,
    max_age_hours: float = MAX_DXPED_AGE_HOURS,
) -> tuple[list[dict], str]:
    """
    Carica la lista DXpedition dal file locale e la aggiorna da NG3K
    se il file manca o ha superato max_age_hours.
    """
    entries: list[dict] = []
    source = "none"
    updated_at: str | None = None

    if os.path.exists(local_path):
        try:
            with open(local_path, "r", encoding="utf-8") as f:
                parsed = json.load(f)
            if isinstance(parsed, dict) and isinstance(parsed.get("dxpeditions"), list):
                entries = parsed["dxpeditions"]
                updated_at = parsed.get("updated_at")
                source = "local-file"
        except (OSError, ValueError) as err:
            print(f"Avviso: errore lettura file locale DXpedition ({err}).")

    if _is_dxpeditions_stale(updated_at, local_path, max_age_hours=max_age_hours):
        print(f"Lista DXpedition assente o più vecchia di {max_age_hours}h: aggiorno da NG3K...")
        refreshed = _refresh_from_ng3k(local_path)
        if refreshed is not None:
            entries, source = refreshed

    return entries, source


def _extract_spot_date(utc_field: str) -> datetime.date | None:
    """Estrae la data YYYY-MM-DD dal campo UTC (es. '1141 2026-11-22') se presente."""
    match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", utc_field or "")
    if not match:
        return None
    try:
        return datetime.date.fromisoformat(match.group(1))
    except ValueError:
        return None


def _is_within_date_window(entry: dict, spot_date: datetime.date | None) -> bool:
    """Verifica se spot_date rientra in start_date/end_date (se definiti)."""
    start_str = entry.get("start_date")
    end_str = entry.get("end_date")
    if not start_str and not end_str:
        return True
    if spot_date is None:
        return True

    try:
        if start_str and spot_date < datetime.date.fromisoformat(start_str):
            return False
        if end_str and spot_date > datetime.date.fromisoformat(end_str):
            return False
    except ValueError:
        return True

    return True


def match_dxpedition(dx_call: str, utc_field: str, dxpeditions: list[dict]) -> dict | None:
    """
    Controlla se dx_call corrisponde a una DXpedition attiva nella lista.
    Confronta il callsign intero, i singoli segmenti separati da '/' e gli eventuali alias.
    """
    call_upper = dx_call.strip().upper()
    if not call_upper or not dxpeditions:
        return None

    spot_date = _extract_spot_date(utc_field)
    call_parts = {p.strip() for p in call_upper.split("/") if p.strip()}
    candidates = {call_upper} | call_parts

    for entry in dxpeditions:
        targets = [str(entry.get("callsign", "")).strip().upper()]
        for alias in entry.get("aliases") or []:
            if isinstance(alias, str) and alias.strip():
                targets.append(alias.strip().upper())

        for target in targets:
            if not target:
                continue
            target_parts = {p.strip() for p in target.split("/") if p.strip()}
            if (target in candidates) or (target_parts & candidates):
                if _is_within_date_window(entry, spot_date):
                    return entry

    return None


def fetch_dxc_spots(callsign: str, url: str = HAMQTH_DXC_URL) -> list[dict]:
    """Scarica e normalizza gli spot dal feed CSV del DX Cluster di HamQTH."""
    headers = {
        "User-Agent": f"DXpedition-Notifier/0.5 ({callsign})"
    }
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"

    lines = [line.strip() for line in response.text.splitlines() if line.strip()]
    if not lines:
        return []

    delimiter = "^" if "^" in lines[0] else (";" if ";" in lines[0] else ",")
    reader = csv.reader(io.StringIO("\n".join(lines)), delimiter=delimiter)

    spots = []
    for row in reader:
        if len(row) < 4:
            continue

        spot = {
            "spotter": row[0].strip().upper(),
            "freq": normalize_freq_khz(row[1]),
            "dx_call": row[2].strip().upper(),
            "comment": row[3].strip(),
            "utc": row[4].strip() if len(row) > 4 else "",
            "dx_continent": row[7].strip().upper() if len(row) > 7 else "",
            "band": row[8].strip().upper() if len(row) > 8 else "",
            "dxcc_entity": row[9].strip() if len(row) > 9 else "",
            "dxcc_id": row[10].strip() if len(row) > 10 else "",
            "raw": row,
        }
        spots.append(spot)

    return spots


def evaluate_spot(
    spot: dict,
    dxpeditions: list[dict],
    home_continent: str,
    require_home_spotter: bool = REQUIRE_HOME_CONTINENT_SPOTTER,
) -> tuple[bool, str, str]:
    """
    Valuta uno spot e ritorna (matched, priority, reason).
    priority può essere 'HIGH' (match lista DXpedition) o 'NORMAL' (euristiche).
    """
    spotter_cont = get_call_continent(spot["spotter"]) or "UNK"
    if require_home_spotter and spotter_cont != home_continent:
        return False, "", ""

    spotter_tag = f"{spotter_cont}-spotter"

    dx_match = match_dxpedition(spot["dx_call"], spot["utc"], dxpeditions)
    if dx_match:
        entity = dx_match.get("entity") or spot["dxcc_entity"]
        label = f"DXpedition ({dx_match.get('callsign')}" + (f" - {entity})" if entity else ")")
        return True, "HIGH", f"{spotter_tag}, {label}"

    comment = spot["comment"]
    comment_lower = comment.lower()
    reasons = []

    for kw in DX_PHRASE_KEYWORDS:
        if kw in comment_lower:
            reasons.append(f"kw:{kw}")
            break

    if UP_WORD_PATTERN.search(comment):
        reasons.append("up")

    if "/" in spot["dx_call"]:
        reasons.append("slash")

    dx_cont = resolve_dx_continent(spot)
    if dx_cont and dx_cont != home_continent:
        reasons.append(f"cont:{dx_cont}")

    if reasons:
        return True, "NORMAL", f"{spotter_tag} ({', '.join(reasons)})"

    return False, "", ""


def _build_spot_dedup_key(spot: dict) -> str:
    """Crea una chiave stabile per deduplicare spot ripetuti dello stesso DX sulla stessa banda/QRG."""
    call = spot["dx_call"].strip().upper()
    band = spot["band"].strip().upper()
    if band:
        return f"{call}|{band}"

    try:
        khz = float(spot["freq"])
        bucket = int(round(khz / 2.0) * 2)
        return f"{call}|~{bucket}kHz"
    except ValueError:
        return f"{call}|{spot['freq']}"


def load_seen_spots(path: str = SEEN_SPOTS_FILE, window_minutes: int = DEDUP_WINDOW_MINUTES) -> dict[str, float]:
    """Carica le chiavi già notificate e ripulisce quelle scadute oltre la finestra temporale."""
    if not os.path.exists(path):
        return {}

    now = time.time()
    max_age_sec = window_minutes * 60
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, dict):
            return {}
        return {
            str(k): float(v)
            for k, v in raw.items()
            if isinstance(v, (int, float)) and (now - float(v)) < max_age_sec
        }
    except (OSError, ValueError) as err:
        print(f"Avviso: errore lettura stato deduplica ({err}), riparto pulito.")
        return {}


def save_seen_spots(seen: dict[str, float], path: str = SEEN_SPOTS_FILE) -> None:
    """Salva su disco lo stato delle chiavi già notificate."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(seen, f, indent=2)
    except OSError as err:
        print(f"Avviso: impossibile salvare lo stato deduplica ({err})")


def _should_send_telegram(priority: str) -> bool:
    if TELEGRAM_NOTIFY_MODE == "HIGH":
        return priority == "HIGH"
    return priority in ("HIGH", "NORMAL")


def _esc(val: str | None) -> str:
    return html.escape((val or "").strip(), quote=False)


def _format_notification_timestamp(dt: datetime.datetime | None = None) -> str:
    """Restituisce giorno e ora in formato leggibile (locale + UTC)."""
    base_dt = dt or datetime.datetime.now().astimezone()
    if base_dt.tzinfo is None:
        base_dt = base_dt.astimezone()
    local_str = base_dt.strftime("%d/%m/%Y %H:%M %Z").strip()
    utc_str = base_dt.astimezone(datetime.timezone.utc).strftime("%H:%M UTC")
    return f"{local_str} ({utc_str})"


def _get_path_note(spot: dict, prop: dict | None, home_continent: str) -> str:
    if assess_path_for_spot is None:
        return ""
    try:
        return assess_path_for_spot(spot, prop, home_continent)
    except Exception:
        return ""


def _render_prop_log(prop: dict | None, home_continent: str) -> str:
    if not prop or format_prop_log is None:
        return ""
    try:
        return format_prop_log(prop, home_continent=home_continent)
    except TypeError:
        return format_prop_log(prop)


def _render_prop_telegram(prop: dict | None, home_continent: str) -> str:
    if not prop or format_prop_telegram_html is None:
        return ""
    try:
        return format_prop_telegram_html(prop, home_continent=home_continent)
    except TypeError:
        return format_prop_telegram_html(prop)


def _resolve_home_coords(home_continent: str) -> tuple[float, float] | None:
    """Ricava (lat, lon) da MY_LAT/MY_LON oppure dal centro indicativo del continente."""
    lat_raw = os.getenv("MY_LAT", "").strip().replace(",", ".")
    lon_raw = os.getenv("MY_LON", "").strip().replace(",", ".")
    if lat_raw and lon_raw:
        try:
            lat_val = float(lat_raw)
            lon_val = float(lon_raw)
            if -90.0 <= lat_val <= 90.0 and -180.0 <= lon_val <= 180.0:
                return lat_val, lon_val
        except ValueError:
            pass

    return CONTINENT_REFERENCE_COORDS.get(home_continent)


def _update_local_map(
    matches: list[tuple[dict, str, str]],
    home_continent: str,
    out_path: str = DEFAULT_MAP_OUT,
) -> str | None:
    """Genera la mappa PNG in locale se ci sono nuovi match; restituisce il percorso o None."""
    if not matches or render_paths_map is None:
        return None
    home_coords = _resolve_home_coords(home_continent)
    if not home_coords:
        return None
    try:
        return render_paths_map(matches, home_coords=home_coords, out_path=out_path)
    except Exception as err:
        print(f"Avviso mappa: impossibile generare {out_path} ({err}).")
        return None


def _format_telegram_message(
    matches: list[tuple[dict, str, str]],
    callsign: str,
    home_continent: str,
    sent_at_label: str | None = None,
    prop: dict | None = None,
) -> str:
    """Formatta i nuovi spot in uno o più messaggi leggibili su Telegram."""
    ts_label = sent_at_label or _format_notification_timestamp()
    lines = [
        f"📡 <b>DX Cluster Alert</b> ({_esc(callsign)} / {_esc(home_continent)})",
        f"🗓️ Inviato: <code>{_esc(ts_label)}</code>",
    ]
    prop_line = _render_prop_telegram(prop, home_continent)
    if prop_line:
        lines.append(prop_line)
    lines.append("")

    for spot, priority, reason in matches:
        badge = "🚨 <b>HIGH</b>" if priority == "HIGH" else "🔹 <b>NORMAL</b>"
        entity = spot.get("dxcc_entity") or (get_call_continent(spot["dx_call"]) or "")
        comment = spot.get("comment") or "-"
        path_note = _get_path_note(spot, prop, home_continent)
        spot_block = (
            f"{badge} <b>{_esc(spot['dx_call'])}</b> ({_esc(entity)}) — "
            f"<b>{_esc(spot['freq'])} kHz</b> [{_esc(spot['band'])}]\n"
            f"🕒 {_esc(spot['utc'])} | spotter: <code>{_esc(spot['spotter'])}</code>\n"
            f"💬 {_esc(comment)}\n"
            f"<i>{_esc(reason)}</i>"
        )
        if path_note:
            spot_block += f"\n🧭 <code>{_esc(path_note)}</code>"
        lines.append(spot_block + "\n")
    return "\n".join(lines).strip()


def _send_telegram_text(
    text: str,
    bot_token: str = TELEGRAM_BOT_TOKEN,
    chat_id: str = TELEGRAM_CHAT_ID,
    silent: bool = TELEGRAM_SILENT,
) -> bool:
    """Invia un singolo messaggio HTML su Telegram e restituisce True se andato a buon fine."""
    if not bot_token or not chat_id:
        print("Info Telegram: TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID non impostati, invio saltato.")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
                "disable_notification": silent,
            },
            timeout=15,
        )
        resp.raise_for_status()
        return True
    except requests.RequestException as err:
        print(f"Avviso Telegram: errore durante l'invio: {err}")
        return False


def send_telegram_test(
    callsign: str,
    home_continent: str,
    bot_token: str = TELEGRAM_BOT_TOKEN,
    chat_id: str = TELEGRAM_CHAT_ID,
    silent: bool = TELEGRAM_SILENT,
    prop: dict | None = None,
) -> bool:
    """Invia un messaggio di prova per verificare configurazione Telegram."""
    ts_label = _format_notification_timestamp()
    lines = [
        "✅ <b>Test Telegram DX Cluster Monitor</b>",
        f"Callsign: <code>{_esc(callsign)}</code> ({_esc(home_continent)})",
        f"Modalità: <code>{_esc(TELEGRAM_NOTIFY_MODE)}</code> | Silenzioso: <code>{silent}</code>",
        f"🗓️ Inviato: <code>{_esc(ts_label)}</code>",
    ]
    prop_line = _render_prop_telegram(prop, home_continent)
    if prop_line:
        lines.append(prop_line)

    ok = _send_telegram_text("\n".join(lines), bot_token=bot_token, chat_id=chat_id, silent=silent)
    if ok:
        print("Messaggio di test inviato su Telegram con successo.")
    return ok


def send_telegram_alerts(
    matches: list[tuple[dict, str, str]],
    callsign: str,
    home_continent: str,
    bot_token: str = TELEGRAM_BOT_TOKEN,
    chat_id: str = TELEGRAM_CHAT_ID,
    silent: bool = TELEGRAM_SILENT,
    prop: dict | None = None,
) -> None:
    """Invia i nuovi match filtrati su Telegram, suddividendo se superano il limite di 4096 caratteri."""
    to_send = [(s, p, r) for (s, p, r) in matches if _should_send_telegram(p)]
    if not to_send:
        return

    if not bot_token or not chat_id:
        print("Info Telegram: TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID non impostati, invio saltato.")
        return

    sent_at_label = _format_notification_timestamp()
    max_len = 3900

    chunks: list[list[tuple[dict, str, str]]] = []
    current_chunk: list[tuple[dict, str, str]] = []
    current_len = 0

    for item in to_send:
        approx_len = len(_format_telegram_message([item], callsign, home_continent, sent_at_label, prop=prop))
        if current_chunk and (current_len + approx_len) > max_len:
            chunks.append(current_chunk)
            current_chunk = [item]
            current_len = approx_len
        else:
            current_chunk.append(item)
            current_len += approx_len

    if current_chunk:
        chunks.append(current_chunk)

    for idx, chunk in enumerate(chunks, start=1):
        text = _format_telegram_message(chunk, callsign, home_continent, sent_at_label, prop=prop)
        if len(chunks) > 1:
            text = f"<i>Parte {idx}/{len(chunks)}</i>\n\n{text}"
        _send_telegram_text(text, bot_token=bot_token, chat_id=chat_id, silent=silent)


def main():
    args = parse_args()
    run_timestamp = _format_notification_timestamp()
    cli_callsign = (args.callsign or "").strip().upper()
    if cli_callsign:
        my_callsign = cli_callsign
        callsign_source = "CLI"
    else:
        my_callsign = DEFAULT_CALLSIGN
        callsign_source = ".env/default"

    detected_continent = get_call_continent(my_callsign)
    if detected_continent:
        home_continent = detected_continent
    else:
        home_continent = "EU"
        print(f"Avviso: prefisso di '{my_callsign}' non riconosciuto, uso 'EU' come fallback.")

    prop = None
    if get_propagation_summary is not None:
        try:
            prop = get_propagation_summary()
        except Exception as err:
            print(f"Avviso propagazione: impossibile leggere i dati solari ({err}).")

    print("=" * 56)
    print(f"ESECUZIONE: {run_timestamp}")
    print(f"CALLSIGN IN USO: {my_callsign}  |  CONTINENTE: {home_continent}  |  ORIGINE: {callsign_source}")
    prop_log = _render_prop_log(prop, home_continent)
    if prop_log:
        print(prop_log)
    print("=" * 56)

    if args.test_telegram:
        send_telegram_test(my_callsign, home_continent, prop=prop)
        return

    dxpeditions, source = load_dxpeditions()
    print(f"Lista DXpedition caricata ({len(dxpeditions)} voci, sorgente: {source}).")

    seen_spots = load_seen_spots(SEEN_SPOTS_FILE, DEDUP_WINDOW_MINUTES)
    now_ts = time.time()

    print(f"Scaricamento spot da {HAMQTH_DXC_URL}...")
    try:
        spots = fetch_dxc_spots(my_callsign)
    except requests.RequestException as err:
        print(f"Errore di rete: {err}")
        return

    print(f"Totale spot ricevuti: {len(spots)}")

    new_matches = []
    skipped_duplicates = 0

    for spot in spots:
        matched, priority, reason = evaluate_spot(
            spot,
            dxpeditions,
            home_continent=home_continent,
            require_home_spotter=REQUIRE_HOME_CONTINENT_SPOTTER,
        )
        if not matched:
            continue

        dedup_key = _build_spot_dedup_key(spot)
        if dedup_key in seen_spots:
            skipped_duplicates += 1
            continue

        seen_spots[dedup_key] = now_ts
        new_matches.append((spot, priority, reason))

    save_seen_spots(seen_spots, SEEN_SPOTS_FILE)

    new_matches.sort(key=lambda item: 0 if item[1] == "HIGH" else 1)

    print(
        f"Spot filtrati nuovi: {len(new_matches)} "
        f"(duplicati saltati negli ultimi {DEDUP_WINDOW_MINUTES} min: {skipped_duplicates})\n"
    )
    for spot, priority, reason in new_matches[:20]:
        path_note = _get_path_note(spot, prop, home_continent)
        path_suffix = f" | {path_note}" if path_note else ""
        print(
            f"[{priority}] [{spot['utc']} | {spot['band']}] {spot['dx_call']} ({spot['dxcc_entity']}) "
            f"su {spot['freq']} kHz | '{spot['comment']}' "
            f"| spotter: {spot['spotter']} | {reason}{path_suffix}"
        )

    map_path = _update_local_map(new_matches, home_continent)
    if map_path:
        print(f"Mappa locale aggiornata: {map_path}")

    if args.no_telegram:
        print("Info Telegram: --no-telegram attivo, invio saltato.")
    else:
        send_telegram_alerts(new_matches, my_callsign, home_continent, prop=prop)
        if args.send_map and map_path and send_photo_to_chats is not None:
            caption = (
                f"🗺️ <b>DX Paths Map</b> ({_esc(my_callsign)} / {_esc(home_continent)}) — "
                f"{len(new_matches)} nuovi match"
            )
            send_photo_to_chats(
                image_path=map_path,
                caption=caption,
                bot_token=TELEGRAM_BOT_TOKEN,
                chat_ids=[TELEGRAM_CHAT_ID] if TELEGRAM_CHAT_ID else [],
                silent=TELEGRAM_SILENT,
            )


if __name__ == "__main__":
    main()