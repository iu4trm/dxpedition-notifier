import os
from dataclasses import dataclass

from locators import normalize_locator

TRUE_VALUES = {"1", "true", "yes", "on"}


def parse_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in {"0", "false", "no", "off", ""}:
        return False
    raise ValueError(f"{name} must be boolean (1/true/yes/on or 0/false/no/off)")


def parse_positive_float(name: str, default: float) -> float:
    raw = os.getenv(name, str(default))
    try:
        value = float(raw)
    except (TypeError, ValueError) as err:
        raise ValueError(f"{name} must be a number") from err
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def parse_positive_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except (TypeError, ValueError) as err:
        raise ValueError(f"{name} must be an integer") from err
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


@dataclass(frozen=True)
class AppConfig:
    callsign: str
    require_home_spotter: bool
    max_dxped_age_hours: float
    dedup_window_minutes: int
    telegram_notify_mode: str
    telegram_bot_token: str
    telegram_chat_id: str
    telegram_silent: bool
    prop_cache_minutes: int
    qth_locator: str
    locator: str


def load_config() -> AppConfig:
    notify_mode = os.getenv("TELEGRAM_NOTIFY_MODE", "HIGH_AND_NORMAL").strip().upper()
    if notify_mode not in {"HIGH", "HIGH_AND_NORMAL"}:
        raise ValueError("TELEGRAM_NOTIFY_MODE must be HIGH or HIGH_AND_NORMAL")

    qth_locator = normalize_locator(os.getenv("MY_QTH_LOCATOR") or os.getenv("MY_LOCATOR", ""))
    configured_locator = os.getenv("MY_QTH_LOCATOR") or os.getenv("MY_LOCATOR")
    if configured_locator and not qth_locator:
        raise ValueError("MY_QTH_LOCATOR/MY_LOCATOR must be a valid 4-, 6-, or 8-character Maidenhead locator")

    latitude = os.getenv("MY_LAT")
    longitude = os.getenv("MY_LON")
    if (latitude is None) != (longitude is None):
        raise ValueError("MY_LAT and MY_LON must be configured together")
    if latitude is not None:
        try:
            lat_value = float(latitude.strip().replace(",", "."))
            lon_value = float(longitude.strip().replace(",", "."))
        except (AttributeError, TypeError, ValueError) as err:
            raise ValueError("MY_LAT and MY_LON must be decimal numbers") from err
        if not (-90 <= lat_value <= 90 and -180 <= lon_value <= 180):
            raise ValueError("MY_LAT/MY_LON are outside valid geographic ranges")

    return AppConfig(
        callsign=os.getenv("MY_CALLSIGN", "IU4TRM").strip().upper(),
        require_home_spotter=parse_bool("REQUIRE_HOME_CONTINENT_SPOTTER", True),
        max_dxped_age_hours=parse_positive_float("MAX_DXPED_AGE_HOURS", 12),
        dedup_window_minutes=parse_positive_int("DEDUP_WINDOW_MINUTES", 30),
        telegram_notify_mode=notify_mode,
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "").strip(),
        telegram_silent=parse_bool("TELEGRAM_SILENT", False),
        prop_cache_minutes=parse_positive_int("PROP_CACHE_MINUTES", 45),
        qth_locator=qth_locator,
        locator=configured_locator,
    )
