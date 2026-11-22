import datetime
import html
import json
import math
import os
import re
import time
import xml.etree.ElementTree as ET
import requests

from prefixes import get_call_continent

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROP_CACHE_FILE = os.path.join(BASE_DIR, "prop_cache.json")
PROP_CACHE_MINUTES = int(os.getenv("PROP_CACHE_MINUTES", "45"))
HAMQSL_SOLAR_URL = "https://www.hamqsl.com/solarxml.php"

VALID_CONTINENTS = {"EU", "NA", "SA", "AF", "AS", "OC"}

HIGH_BANDS = {"10M", "12M", "15M", "17M", "28MHZ", "24MHZ", "21MHZ", "18MHZ"}
MID_BANDS = {"20M", "30M", "14MHZ", "10MHZ"}
LOW_BANDS = {"40M", "60M", "80M", "160M", "7MHz", "5MHZ", "3.5MHZ", "1.8MHZ"}
LOW_BANDS_UPPER = {b.upper() for b in LOW_BANDS}
GRAYLINE_FAVORED_BANDS = LOW_BANDS_UPPER | {"20M", "30M", "14MHZ", "10MHZ"}

# Continenti le cui tratte intercontinentali attraversano spesso latitudini medio-alte / aurorali
HIGH_LAT_CONTINENTS = {"NA", "EU"}
# Continenti tipicamente coinvolti in tratte trans-equatoriali / nord-sud
EQUATORIAL_SOUTH_CONTINENTS = {"SA", "AF", "OC"}

# Coordinate indicative per continente (usate solo se MY_LAT / MY_LON non sono impostate)
CONTINENT_REFERENCE_COORDS: dict[str, tuple[float, float]] = {
    "EU": (48.0, 10.0),
    "NA": (40.0, -98.0),
    "SA": (-15.0, -60.0),
    "AF": (5.0, 20.0),
    "AS": (35.0, 105.0),
    "OC": (-25.0, 135.0),
}


def _load_cache(path: str = PROP_CACHE_FILE) -> dict | None:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _save_cache(payload: dict, path: str = PROP_CACHE_FILE) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    except OSError as err:
        print(f"Propagation warning: unable to save cache ({err})")


def _to_float(val: str | None) -> float | None:
    if not val:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", val.strip())
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def _resolve_reference_coords(home_continent: str | None) -> tuple[float, float] | None:
    """Restituisce (lat, lon) da MY_LAT/MY_LON se presenti, altrimenti da home_continent."""
    lat_env = _to_float(os.getenv("MY_LAT"))
    lon_env = _to_float(os.getenv("MY_LON"))
    if lat_env is not None and lon_env is not None:
        if -90.0 <= lat_env <= 90.0 and -180.0 <= lon_env <= 180.0:
            return lat_env, lon_env

    cont = (home_continent or "").strip().upper()
    return CONTINENT_REFERENCE_COORDS.get(cont)


def solar_elevation_deg(lat_deg: float, lon_deg: float, dt_utc: datetime.datetime) -> float:
    """Calcola l'elevazione approssimata del Sole in gradi per (lat, lon) all'istante UTC."""
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=datetime.timezone.utc)
    else:
        dt_utc = dt_utc.astimezone(datetime.timezone.utc)

    day_of_year = dt_utc.timetuple().tm_yday
    utc_hours = (
        dt_utc.hour
        + dt_utc.minute / 60.0
        + dt_utc.second / 3600.0
    )

    gamma = 2.0 * math.pi * (day_of_year - 1) / 365.0
    decl_deg = (
        0.006918
        - 0.399912 * math.cos(gamma)
        + 0.070257 * math.sin(gamma)
        - 0.006758 * math.cos(2.0 * gamma)
        + 0.000907 * math.sin(2.0 * gamma)
    ) * (180.0 / math.pi)

    eq_time_min = 229.18 * (
        0.000075
        + 0.001868 * math.cos(gamma)
        - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2.0 * gamma)
        - 0.040849 * math.sin(2.0 * gamma)
    )
    solar_time_min = (utc_hours * 60.0 + eq_time_min + 4.0 * lon_deg) % 1440.0
    hour_angle_deg = solar_time_min / 4.0 - 180.0

    lat_rad = math.radians(lat_deg)
    decl_rad = math.radians(decl_deg)
    ha_rad = math.radians(hour_angle_deg)

    sin_alt = (
        math.sin(lat_rad) * math.sin(decl_rad)
        + math.cos(lat_rad) * math.cos(decl_rad) * math.cos(ha_rad)
    )
    sin_alt = max(-1.0, min(1.0, sin_alt))
    return math.degrees(math.asin(sin_alt))


def is_grayline_window(
    home_continent: str | None,
    dt_utc: datetime.datetime | None = None,
    window_deg: float = 6.0,
) -> tuple[bool, float | None]:
    """Verifica se all'istante UTC indicato il Sole è vicino all'orizzonte (finestra grayline)."""
    coords = _resolve_reference_coords(home_continent)
    if not coords:
        return False, None

    ref_dt = dt_utc or datetime.datetime.now(datetime.timezone.utc)
    elev = solar_elevation_deg(coords[0], coords[1], ref_dt)
    return (-window_deg <= elev <= window_deg), elev


def _fetch_hamqsl_solar(timeout: int = 10) -> dict:
    resp = requests.get(
        HAMQSL_SOLAR_URL,
        headers={"User-Agent": "DXpedition-Notifier/0.5"},
        timeout=timeout,
    )
    resp.raise_for_status()
    root = ET.fromstring(resp.text)
    solardata = root.find("solardata")
    if solardata is None:
        raise ValueError("Missing solardata element in XML")

    def tag_text(name: str) -> str:
        el = solardata.find(name)
        return (el.text or "").strip() if el is not None and el.text else ""

    sfi = _to_float(tag_text("solarflux"))
    k_index = _to_float(tag_text("kindex"))
    a_index = _to_float(tag_text("aindex"))
    xray = tag_text("xray") or ""

    return {
        "sfi": int(sfi) if sfi is not None else None,
        "k_index": k_index,
        "a_index": int(a_index) if a_index is not None else None,
        "xray": xray,
        "source": "HamQSL/NOAA",
    }


def classify_conditions(data: dict) -> str:
    k = data.get("k_index")
    a = data.get("a_index")
    sfi = data.get("sfi")

    if k is not None and k >= 4:
        return "Disturbed (K>=4)"
    if a is not None and a >= 20:
        return "Disturbed (high A)"
    if k is not None and k >= 3:
        return "Unsettled"
    if sfi is not None and sfi >= 150:
        return "Good HF / High bands"
    if sfi is not None and sfi >= 100:
        return "Moderate HF"
    if k is not None or sfi is not None:
        return "Quiet / Low-Mid bands"
    return "Unknown"


def get_propagation_summary(
    cache_path: str = PROP_CACHE_FILE,
    cache_minutes: int = PROP_CACHE_MINUTES,
    force_refresh: bool = False,
) -> dict:
    now = time.time()
    cached = _load_cache(cache_path)

    if not force_refresh and cached and isinstance(cached.get("fetched_at"), (int, float)):
        age_sec = now - float(cached["fetched_at"])
        if age_sec < cache_minutes * 60 and isinstance(cached.get("data"), dict):
            out = dict(cached["data"])
            out["cached"] = True
            return out

    try:
        fresh = _fetch_hamqsl_solar()
        fresh["condition"] = classify_conditions(fresh)
        fresh["updated_utc"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        _save_cache({"fetched_at": now, "data": fresh}, cache_path)
        fresh["cached"] = False
        return fresh
    except Exception as err:
        if cached and isinstance(cached.get("data"), dict):
            fallback = dict(cached["data"])
            fallback["condition"] = fallback.get("condition") or classify_conditions(fallback)
            fallback["cached"] = True
            fallback["error"] = str(err)
            return fallback
        return {
            "sfi": None,
            "k_index": None,
            "a_index": None,
            "xray": "",
            "condition": "Unavailable",
            "source": "none",
            "cached": False,
            "error": str(err),
        }


def resolve_spot_zone(spot: dict) -> str:
    """Restituisce il continente della stazione DX dal feed o dal prefisso del nominativo."""
    feed_cont = (spot.get("dx_continent") or "").strip().upper()
    if feed_cont in VALID_CONTINENTS:
        return feed_cont
    detected = (get_call_continent(spot.get("dx_call", "")) or "").strip().upper()
    return detected if detected in VALID_CONTINENTS else "UNK"


def _normalize_band(band: str | None) -> str:
    return (band or "").strip().upper()


def _parse_spot_utc_datetime(utc_field: str | None) -> datetime.datetime | None:
    """Estrae un datetime UTC dallo spot se contiene HHMM o HH:MM (ed eventualmente YYYY-MM-DD)."""
    raw = (utc_field or "").strip()
    if not raw:
        return None

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    date_match = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", raw)
    time_match = re.search(r"\b(\d{2}):?(\d{2})\s*(?:UTC|Z)?\b", raw)
    if not time_match:
        return None

    hour = int(time_match.group(1))
    minute = int(time_match.group(2))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None

    if date_match:
        try:
            year, month, day = map(int, date_match.groups())
            return datetime.datetime(year, month, day, hour, minute, tzinfo=datetime.timezone.utc)
        except ValueError:
            return None

    return now_utc.replace(hour=hour, minute=minute, second=0, microsecond=0)


def assess_path_for_spot(spot: dict, prop: dict | None, home_continent: str | None) -> str:
    """
    Valuta in modo simmetrico e puramente informativo il percorso radio tra home_continent
    e la zona geografica del DX, includendo eventuale finestra grayline.
    Non scarta mai lo spot.
    """
    home_raw = (home_continent or "").strip().upper()
    home = home_raw if home_raw in VALID_CONTINENTS else "UNK"
    dx_zone = resolve_spot_zone(spot)
    band = _normalize_band(spot.get("band"))

    path_label = f"{home}->{dx_zone}" + (f" {band}" if band else "")
    spot_dt = _parse_spot_utc_datetime(spot.get("utc"))
    in_grayline, elev = is_grayline_window(home, dt_utc=spot_dt)
    gl_suffix = ""
    if in_grayline and elev is not None:
        gl_suffix = f" [grayline window, sun {elev:+.1f}°]" if band in GRAYLINE_FAVORED_BANDS else f" [grayline {elev:+.1f}°]"

    if not prop:
        return f"Path {path_label}{gl_suffix}"

    k = prop.get("k_index")
    sfi = prop.get("sfi")

    if home == "UNK" or dx_zone == "UNK":
        return f"Path {path_label}: DX spot{gl_suffix}"

    if dx_zone == home:
        if k is not None and k >= 4:
            return f"Path {path_label}: intra-continental with geomagnetic disturbance (K={k}){gl_suffix}"
        return f"Path {path_label}: intra-continental path{gl_suffix}"

    if k is not None and k >= 4:
        if home in HIGH_LAT_CONTINENTS and dx_zone in HIGH_LAT_CONTINENTS:
            return f"Path {path_label}: high-latitude path sensitive to disturbance (K={k}){gl_suffix}"
        if home in EQUATORIAL_SOUTH_CONTINENTS or dx_zone in EQUATORIAL_SOUTH_CONTINENTS:
            return f"Path {path_label}: trans-equatorial path during disturbed conditions (K={k}){gl_suffix}"
        return f"Path {path_label}: geomagnetic disturbance (K={k}){gl_suffix}"

    if band in HIGH_BANDS:
        if sfi is not None and sfi >= 150:
            return f"Path {path_label}: favorable high-band DX (SFI={sfi}){gl_suffix}"
        if sfi is not None and sfi < 100:
            return f"Path {path_label}: low SFI ({sfi}) on high band, selective openings{gl_suffix}"
        return f"Path {path_label}: high-band intercontinental DX{gl_suffix}"

    if band in LOW_BANDS_UPPER:
        if k is not None and k >= 3:
            return f"Path {path_label}: low-band DX with unsettled geomagnetic field (K={k}){gl_suffix}"
        return f"Path {path_label}: low-band DX (favored on darkness/grayline){gl_suffix}"

    if band in MID_BANDS:
        if (home in EQUATORIAL_SOUTH_CONTINENTS) ^ (dx_zone in EQUATORIAL_SOUTH_CONTINENTS):
            return f"Path {path_label}: trans-equatorial mid-band DX{gl_suffix}"
        return f"Path {path_label}: mid-band intercontinental DX{gl_suffix}"

    return f"Path {path_label}: intercontinental DX{gl_suffix}"


def format_prop_log(prop: dict, home_continent: str | None = None) -> str:
    sfi = prop.get("sfi") if prop.get("sfi") is not None else "-"
    k = prop.get("k_index") if prop.get("k_index") is not None else "-"
    a = prop.get("a_index") if prop.get("a_index") is not None else "-"
    cond = prop.get("condition") or "Unknown"
    mode = "cache" if prop.get("cached") else "live"
    in_gl, elev = is_grayline_window(home_continent)
    gl_part = f" | Grayline: YES ({elev:+.1f}°)" if (in_gl and elev is not None) else ""
    return f"PROPAGATION [{mode}]: SFI {sfi} | K {k} | A {a} | {cond}{gl_part}"


def format_prop_telegram_html(prop: dict, home_continent: str | None = None) -> str:
    sfi = prop.get("sfi") if prop.get("sfi") is not None else "-"
    k = prop.get("k_index") if prop.get("k_index") is not None else "-"
    a = prop.get("a_index") if prop.get("a_index") is not None else "-"
    cond = html.escape(str(prop.get("condition") or "Unknown"), quote=False)
    in_gl, elev = is_grayline_window(home_continent)
    gl_part = f" | 🌅 Grayline (<code>{elev:+.1f}°</code>)" if (in_gl and elev is not None) else ""
    return f"☀️ Conditions: <b>{cond}</b> (SFI <code>{sfi}</code>, K <code>{k}</code>, A <code>{a}</code>){gl_part}"