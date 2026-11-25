import json
import os
import re

LOCATOR_PATTERN = re.compile(
    r"(?<![A-Z0-9])([A-R]{2}[0-9]{2}(?:[A-X]{2}(?:[0-9]{2})?)?)(?![A-Z0-9])",
    re.IGNORECASE,
)


def normalize_locator(value: str | None) -> str | None:
    locator = (value or "").strip().upper()
    if not re.fullmatch(r"[A-R]{2}[0-9]{2}(?:[A-X]{2}(?:[0-9]{2})?)?", locator):
        return None
    if len(locator) not in {4, 6, 8}:
        return None
    return locator


def maidenhead_to_latlon(locator: str) -> tuple[float, float] | None:
    """Convert a 4-, 6-, or 8-character Maidenhead locator to its center point."""
    locator = normalize_locator(locator)
    if not locator:
        return None

    lon = (ord(locator[0]) - ord("A")) * 20 - 180
    lat = (ord(locator[1]) - ord("A")) * 10 - 90
    lon += (ord(locator[2]) - ord("0")) * 2
    lat += (ord(locator[3]) - ord("0")) * 1

    if len(locator) >= 6:
        lon += (ord(locator[4]) - ord("A") + 0.5) / 12
        lat += (ord(locator[5]) - ord("A") + 0.5) / 24

    if len(locator) == 8:
        lon += (ord(locator[6]) - ord("0") + 0.5) / 120
        lat += (ord(locator[7]) - ord("0") + 0.5) / 240

    if len(locator) == 4:
        lon += 1.0
        lat += 0.5

    return lat, lon


def extract_locator(text: str | None) -> str:
    """Extract a Maidenhead locator from text, preferring longer precision."""
    if not text:
        return ""
    matches = LOCATOR_PATTERN.findall(text.upper())
    normalized = sorted(
        (item for item in (normalize_locator(match) for match in matches) if item),
        key=len,
        reverse=True,
    )
    return normalized[0] if normalized else ""


def resolve_callsign_locator(callsign: str, mapping_path: str | None = None) -> str:
    """Resolve an exact callsign or slash segment through an optional JSON map."""
    if not callsign:
        return ""

    path = mapping_path or os.getenv("CALLSIGN_LOCATORS_FILE", "")
    if not path or not os.path.exists(path):
        return ""

    try:
        with open(path, "r", encoding="utf-8") as handle:
            mapping = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(mapping, dict):
        return ""

    call = callsign.strip().upper()
    candidates = [call]
    candidates.extend(part.strip().upper() for part in call.split("/") if part.strip())
    for candidate in candidates:
        value = normalize_locator(str(mapping.get(candidate, "")))
        if value:
            return value
    return ""


def resolve_spot_locator(spot: dict) -> str:
    """Resolve a locator already supplied by the feed, comment, or callsign map."""
    for key in ("dx_locator", "grid_locator", "maidenhead", "grid"):
        locator = normalize_locator(str(spot.get(key, "") or ""))
        if locator:
            return locator

    comment_locator = extract_locator(str(spot.get("comment", "") or ""))
    if comment_locator:
        return comment_locator

    return resolve_callsign_locator(
        str(spot.get("dx_call", "") or ""),
        os.getenv("CALLSIGN_LOCATORS_FILE"),
    )
