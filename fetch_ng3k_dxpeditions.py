import datetime
import json
import os
import re
import requests
from bs4 import BeautifulSoup

ADXO_URL = "https://www.ng3k.com/Misc/adxo.html"
OUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dxpeditions.json")

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

EXTRA_CALL_PATTERN = re.compile(
    r"\b(?:as|using|call(?:sign)?s?:?)\s+([A-Z0-9]{1,4}/[A-Z0-9]{2,8}|[A-Z0-9]*\d[A-Z0-9]{1,6})\b",
    re.IGNORECASE,
)


def parse_ng3k_date(raw_date: str) -> str | None:
    """Converte date tipo '2026 Oct20' o '2026 Oct 20' in '2026-10-20'."""
    if not raw_date:
        return None
    m = re.search(r"\b(\d{4})\s+([A-Za-z]{3})\s*(\d{1,2})\b", raw_date.strip())
    if not m:
        return None
    year = int(m.group(1))
    month = MONTHS.get(m.group(2).lower())
    day = int(m.group(3))
    if not month:
        return None
    try:
        return datetime.date(year, month, day).isoformat()
    except ValueError:
        return None


def clean_callsign(raw_call: str) -> str:
    """Rimuove '[spots]' e spazi superflui dal campo Call di NG3K."""
    cleaned = re.sub(r"\[spots\]", "", raw_call, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip().upper()


def extract_aliases(main_call: str, notes: str) -> list[str]:
    """Estrae eventuali nominativi completi o speciali dalle note (es. 3B9/M0CFW, 8P/PZ5TW)."""
    if not notes:
        return []
    found = []
    for match in EXTRA_CALL_PATTERN.finditer(notes):
        alias = match.group(1).strip().upper()
        if alias and alias != main_call and alias not in found:
            found.append(alias)
    return found


def fetch_ng3k_dxpeditions(url: str = ADXO_URL) -> list[dict]:
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) DXpedition-Notifier/0.2"
    }
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "latin-1"

    soup = BeautifulSoup(resp.text, "html.parser")
    entries: list[dict] = []

    for tr in soup.find_all("tr"):
        cells = [
            re.sub(r"\s+", " ", td.get_text(" ", strip=True)).strip()
            for td in tr.find_all("td")
        ]
        # Le righe reali delle spedizioni hanno almeno 7 colonne
        if len(cells) < 7:
            continue

        start_raw = cells[0]
        end_raw = cells[1]
        entity = cells[2]
        callsign = clean_callsign(cells[3])

        if not callsign or callsign == "CALL":
            continue

        start_date = parse_ng3k_date(start_raw)
        end_date = parse_ng3k_date(end_raw)

        if not start_date and not end_date:
            continue

        qsl = cells[4]
        info = cells[6]
        aliases = extract_aliases(callsign, info)

        entries.append({
            "callsign": callsign,
            "aliases": aliases,
            "entity": entity,
            "start_date": start_date,
            "end_date": end_date,
            "qsl_via": qsl,
            "notes": info,
            "source": "ng3k-adxo",
        })

    return entries


def main():
    entries = fetch_ng3k_dxpeditions()
    payload = {
        "updated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "source_url": ADXO_URL,
        "count": len(entries),
        "dxpeditions": entries,
    }

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"Estratte {len(entries)} spedizioni da NG3K e salvate in {OUT_FILE}")
    for item in entries[:8]:
        alias_str = f" (alias: {', '.join(item['aliases'])})" if item["aliases"] else ""
        print(
            f"  {item['callsign']:10s} | {item['entity']:15s} | "
            f"{item['start_date']} -> {item['end_date']}{alias_str}"
        )


if __name__ == "__main__":
    main()