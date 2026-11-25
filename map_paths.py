import datetime
import json
import math
import os
import re
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont
import requests

from project_utils import request_with_retry
from locators import maidenhead_to_latlon, resolve_spot_locator

from propagation import (
    CONTINENT_REFERENCE_COORDS,
    resolve_spot_zone,
    solar_elevation_deg,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MAP_OUT = os.path.join(BASE_DIR, "dx_paths_map.png")
DEFAULT_COUNTRIES_GEOJSON = os.path.join(BASE_DIR, "world_countries.geojson")

# Coordinate indicative per entità, prefissi o continenti (estendibili senza toccare la logica)
ZONE_COORDS: dict[str, tuple[float, float]] = {
    **CONTINENT_REFERENCE_COORDS,
    # Nord America e dintorni
    "W": (39.8, -98.6),
    "K": (39.8, -98.6),
    "N": (39.8, -98.6),
    "VE": (56.1, -106.3),
    "VA": (53.5, -113.5),
    "KL7": (64.2, -152.5),
    "ALASKA": (64.2, -152.5),
    "XE": (23.6, -102.5),
    "VP9": (32.3, -64.8),
    "V2": (17.1, -61.8),
    "TI": (9.9, -84.1),
    "HP": (8.5, -80.8),
    "OX": (71.7, -42.6),
    "GREENLAND": (71.7, -42.6),
    # Sud America
    "PY": (-14.2, -51.9),
    "LU": (-34.6, -58.4),
    "CE": (-35.7, -71.5),
    "CX": (-32.5, -55.8),
    "HK": (4.6, -74.1),
    "YV": (6.4, -66.6),
    # Europa e Mediterraneo
    "I": (42.8, 12.6),
    "DL": (51.2, 10.5),
    "F": (46.2, 2.2),
    "G": (52.4, -1.5),
    "GM": (56.5, -4.2),
    "GW": (52.3, -3.8),
    "GI": (54.6, -6.5),
    "EI": (53.1, -8.2),
    "EA": (40.4, -3.7),
    "CT": (39.4, -8.2),
    "HB9": (46.8, 8.2),
    "OE": (47.5, 14.6),
    "PA": (52.1, 5.3),
    "ON": (50.5, 4.5),
    "OZ": (56.0, 9.5),
    "SM": (62.0, 15.0),
    "LA": (60.5, 8.5),
    "OH": (62.5, 26.0),
    "OH0": (60.2, 20.0),
    "JW": (78.2, 15.6),
    "TF": (64.9, -18.5),
    "ICELAND": (64.9, -18.5),
    "SP": (52.1, 19.4),
    "OK": (49.8, 15.5),
    "OM": (48.7, 19.7),
    "HA": (47.2, 19.5),
    "YO": (45.9, 24.9),
    "9A": (45.1, 15.2),
    "SV": (39.1, 21.8),
    "SV9": (35.2, 24.9),
    "TA": (39.0, 35.2),
    "5B": (35.1, 33.4),
    "4X": (31.5, 34.8),
    "UA": (55.8, 37.6),
    # Africa
    "ZS": (-30.6, 22.9),
    "3X": (10.0, -10.7),
    "GUINEA": (10.0, -10.7),
    "V5": (-22.6, 17.1),
    "NAMIBIA": (-22.6, 17.1),
    "3B8": (-20.2, 57.6),
    "MAURITIUS": (-20.2, 57.6),
    "3B9": (-19.7, 63.4),
    "RODRIGUES": (-19.7, 63.4),
    "ZD8": (-7.9, -14.4),
    "ASCENSION": (-7.9, -14.4),
    "ZD9": (-37.1, -12.3),
    "TRISTAN": (-37.1, -12.3),
    # Asia
    "JA": (36.2, 138.2),
    "HL": (36.5, 127.8),
    "BY": (35.8, 104.2),
    "BV": (23.7, 121.0),
    "DU": (12.9, 121.8),
    "YB": (-2.5, 118.0),
    "9M6": (5.5, 116.5),
    # Oceania e Pacifico (incluse Hawaii)
    "KH6": (21.3, -157.8),
    "KH7": (21.3, -157.8),
    "HAWAII": (21.3, -157.8),
    "VK": (-25.3, 133.8),
    "ZL": (-41.3, 174.8),
    "FK": (-21.3, 165.3),
    "FO": (-17.6, -149.5),
    "KH2": (13.4, 144.8),
    "T8": (7.5, 134.5),
    "V7": (7.1, 171.2),
}


def _great_circle_points(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    steps: int = 80,
) -> list[tuple[float, float]]:
    """Interpola punti lungo l'arco ortodromico (great circle) tra due coordinate in gradi."""
    phi1, lam1 = math.radians(lat1), math.radians(lon1)
    phi2, lam2 = math.radians(lat2), math.radians(lon2)

    d_phi = phi2 - phi1
    d_lam = lam2 - lam1
    a = (
        math.sin(d_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2.0) ** 2
    )
    delta = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))

    if delta < 1e-9:
        return [(lat1, lon1), (lat2, lon2)]

    pts: list[tuple[float, float]] = []
    sin_delta = math.sin(delta)
    for i in range(steps + 1):
        t = i / steps
        a_coef = math.sin((1.0 - t) * delta) / sin_delta
        b_coef = math.sin(t * delta) / sin_delta

        x = (
            a_coef * math.cos(phi1) * math.cos(lam1)
            + b_coef * math.cos(phi2) * math.cos(lam2)
        )
        y = (
            a_coef * math.cos(phi1) * math.sin(lam1)
            + b_coef * math.cos(phi2) * math.sin(lam2)
        )
        z = a_coef * math.sin(phi1) + b_coef * math.sin(phi2)

        lat_i = math.degrees(math.atan2(z, math.sqrt(x * x + y * y)))
        lon_i = math.degrees(math.atan2(y, x))
        lon_i = ((lon_i + 180.0) % 360.0) - 180.0
        pts.append((lat_i, lon_i))

    return pts


def _latlon_to_xy(
    lat: float, lon: float, width: int, height: int
) -> tuple[int, int]:
    """Proiezione equirettangolare semplice: lon [-180..180], lat [90..-90]."""
    x = int(round(((lon + 180.0) / 360.0) * (width - 1)))
    y = int(round(((90.0 - lat) / 180.0) * (height - 1)))
    return x, y


def _draw_segmented_polyline(
    draw: ImageDraw.ImageDraw,
    coords: list[tuple[float, float]],
    width: int,
    height: int,
    fill: tuple[int, int, int, int],
    line_width: int = 3,
) -> None:
    """Disegna una polilinea spezzando i salti oltre metà mappa (antimeridiano +/-180°)."""
    if len(coords) < 2:
        return

    segment: list[tuple[int, int]] = []
    prev_lon: float | None = None

    for lat, lon in coords:
        if prev_lon is not None and abs(lon - prev_lon) > 180.0:
            if len(segment) >= 2:
                draw.line(segment, fill=fill, width=line_width)
            segment = []
        segment.append(_latlon_to_xy(lat, lon, width, height))
        prev_lon = lon

    if len(segment) >= 2:
        draw.line(segment, fill=fill, width=line_width)


def _point_in_ring(lon: float, lat: float, ring: list) -> bool:
    """Ray-casting leggero per verificare se (lon, lat) cade dentro un anello poligonale."""
    inside = False
    n = len(ring)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = float(ring[i][0]), float(ring[i][1])
        xj, yj = float(ring[j][0]), float(ring[j][1])
        intersects = ((yi > lat) != (yj > lat)) and (
            lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def _point_in_geometry(lat: float, lon: float, geom: dict) -> bool:
    """Controlla se (lat, lon) ricade in una geometria GeoJSON Polygon o MultiPolygon."""
    gtype = geom.get("type")
    coords = geom.get("coordinates") or []
    if gtype == "Polygon" and coords:
        if not _point_in_ring(lon, lat, coords[0]):
            return False
        for hole in coords[1:]:
            if _point_in_ring(lon, lat, hole):
                return False
        return True
    if gtype == "MultiPolygon":
        for poly in coords:
            if poly and _point_in_ring(lon, lat, poly[0]):
                in_hole = any(_point_in_ring(lon, lat, h) for h in poly[1:])
                if not in_hole:
                    return True
    return False


def _draw_geojson_rings(
    draw: ImageDraw.ImageDraw,
    rings: list,
    width: int,
    height: int,
    fill: tuple[int, int, int, int] | None,
    outline: tuple[int, int, int, int] | None,
    line_width: int = 1,
) -> None:
    """Disegna anelli poligonali spezzando eventuali salti sull'antimeridiano."""
    for ring in rings:
        if not ring or len(ring) < 3:
            continue
        segments: list[list[tuple[int, int]]] = []
        current: list[tuple[int, int]] = []
        prev_lon: float | None = None
        for pt in ring:
            lon, lat = float(pt[0]), float(pt[1])
            if prev_lon is not None and abs(lon - prev_lon) > 180.0:
                if len(current) >= 2:
                    segments.append(current)
                current = []
            current.append(_latlon_to_xy(lat, lon, width, height))
            prev_lon = lon
        if len(current) >= 2:
            segments.append(current)

        for seg in segments:
            if fill and len(seg) >= 3:
                draw.polygon(seg, fill=fill, outline=outline)
            elif outline and len(seg) >= 2:
                draw.line(seg, fill=outline, width=line_width)


def _draw_geometry(
    draw: ImageDraw.ImageDraw,
    geom: dict,
    width: int,
    height: int,
    fill: tuple[int, int, int, int] | None,
    outline: tuple[int, int, int, int] | None,
    line_width: int = 1,
) -> None:
    """Disegna il contorno esterno di Polygon o MultiPolygon da GeoJSON."""
    gtype = geom.get("type")
    coords = geom.get("coordinates") or []
    if gtype == "Polygon":
        _draw_geojson_rings(draw, coords[:1], width, height, fill, outline, line_width)
    elif gtype == "MultiPolygon":
        for poly in coords:
            if poly:
                _draw_geojson_rings(draw, poly[:1], width, height, fill, outline, line_width)


def _load_geojson_features(geojson_path: str = DEFAULT_COUNTRIES_GEOJSON) -> list[dict]:
    """Carica le feature geografiche da un file GeoJSON locale, se presente."""
    if not geojson_path or not os.path.exists(geojson_path):
        return []
    try:
        with open(geojson_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        features = data.get("features") if isinstance(data, dict) else []
        return features if isinstance(features, list) else []
    except (OSError, ValueError):
        return []


def draw_countries_layer(
    draw: ImageDraw.ImageDraw,
    width: int,
    height: int,
    home_coords: tuple[float, float],
    destinations: list[tuple[float, float, str, str]],
    geojson_path: str = DEFAULT_COUNTRIES_GEOJSON,
) -> None:
    """
    Disegna i contorni dei continenti/paesi da GeoJSON ed evidenzia i paesi
    coinvolti (QTH di partenza e destinazioni degli spot).
    destinations: lista di (lat, lon, priority, label)
    """
    features = _load_geojson_features(geojson_path)
    if not features:
        return

    land_fill = (24, 36, 54, 165)
    border_line = (90, 118, 156, 220)
    home_fill = (60, 190, 105, 115)

    for feat in features:
        geom = (feat or {}).get("geometry")
        if geom:
            _draw_geometry(
                draw,
                geom,
                width,
                height,
                fill=land_fill,
                outline=border_line,
                line_width=1,
            )

    for feat in features:
        geom = (feat or {}).get("geometry")
        if not geom:
            continue

        if _point_in_geometry(home_coords[0], home_coords[1], geom):
            _draw_geometry(
                draw,
                geom,
                width,
                height,
                fill=home_fill,
                outline=(135, 255, 170, 240),
                line_width=2,
            )

        for dst_lat, dst_lon, priority, _label in destinations:
            if _point_in_geometry(dst_lat, dst_lon, geom):
                dst_fill = (
                    (225, 65, 65, 120) if priority == "HIGH" else (55, 165, 235, 100)
                )
                dst_out = (
                    (255, 115, 115, 245)
                    if priority == "HIGH"
                    else (125, 225, 255, 230)
                )
                _draw_geometry(
                    draw,
                    geom,
                    width,
                    height,
                    fill=dst_fill,
                    outline=dst_out,
                    line_width=2,
                )


def _resolve_dx_coords(spot: dict) -> tuple[float, float] | None:
    """Ricava coordinate esatte o indicative per lo spot."""
    locator = resolve_spot_locator(spot)
    locator_coords = maidenhead_to_latlon(locator) if locator else None
    if locator_coords:
        return locator_coords

    entity = (spot.get("dxcc_entity") or "").strip().upper()
    call = (spot.get("dx_call") or "").strip().upper()

    if entity in ZONE_COORDS:
        return ZONE_COORDS[entity]
    for key, coords in ZONE_COORDS.items():
        if len(key) > 2 and key in entity:
            return coords

    # Controlla prefissi di callsign (es. KH6/..., KH7X, KL7/..., OH0/...)
    tokens = [t for t in re.split(r"[^A-Z0-9]+", call) if t]
    for token in tokens:
        for length in (4, 3, 2, 1):
            if len(token) >= length:
                prefix = token[:length]
                if prefix in ZONE_COORDS and prefix not in {"EU", "NA", "SA", "AF", "AS", "OC"}:
                    return ZONE_COORDS[prefix]

    for prefix, coords in ZONE_COORDS.items():
        if len(prefix) <= 2 and prefix not in {"EU", "NA", "SA", "AF", "AS", "OC"}:
            if entity.startswith(prefix + " ") or entity == prefix:
                return coords

    zone = resolve_spot_zone(spot)
    return CONTINENT_REFERENCE_COORDS.get(zone)


def _draw_labels_non_overlapping(
    draw: ImageDraw.ImageDraw,
    labels: list[tuple[int, int, str, str]],
    width: int,
    height: int,
    font: ImageFont.ImageFont,
) -> None:
    """
    Raggruppa etichette sullo stesso punto o molto vicine e sfalsa quelle che
    colliderebbero con riquadri già disegnati.
    labels: lista di (x, y, callsign, priority)
    """
    grouped: list[dict] = []
    for x, y, call, priority in labels:
        call_clean = (call or "").strip()
        if not call_clean:
            continue
        placed_in_group = False
        for grp in grouped:
            if abs(grp["x"] - x) <= 10 and abs(grp["y"] - y) <= 10:
                if call_clean not in grp["calls"]:
                    grp["calls"].append(call_clean)
                if priority == "HIGH":
                    grp["priority"] = "HIGH"
                placed_in_group = True
                break
        if not placed_in_group:
            grouped.append(
                {
                    "x": x,
                    "y": y,
                    "calls": [call_clean],
                    "priority": priority,
                }
            )

    occupied_boxes: list[tuple[int, int, int, int]] = [(8, 8, 430, 28)]

    for grp in grouped:
        text = ", ".join(grp["calls"][:4])
        if len(grp["calls"]) > 4:
            text += f" (+{len(grp['calls']) - 4})"

        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        base_x = min(max(4, grp["x"] + 8), max(4, width - tw - 8))
        candidates_y = [
            grp["y"] - th - 4,
            grp["y"] + 6,
            grp["y"] - (th * 2) - 8,
            grp["y"] + th + 10,
        ]

        chosen_x, chosen_y = base_x, max(32, min(height - th - 6, grp["y"] - th - 4))
        for cy in candidates_y:
            cy_clamped = max(32, min(height - th - 6, cy))
            box = (base_x - 2, cy_clamped - 1, base_x + tw + 3, cy_clamped + th + 2)
            overlaps = any(
                not (
                    box[2] < ox0
                    or box[0] > ox2
                    or box[3] < oy1
                    or box[1] > oy3
                )
                for (ox0, oy1, ox2, oy3) in occupied_boxes
            )
            if not overlaps:
                chosen_x, chosen_y = base_x, cy_clamped
                break

        final_box = (
            chosen_x - 2,
            chosen_y - 1,
            chosen_x + tw + 3,
            chosen_y + th + 2,
        )
        occupied_boxes.append(final_box)
        bg = (45, 16, 18, 215) if grp["priority"] == "HIGH" else (14, 24, 38, 210)
        draw.rectangle(final_box, fill=bg)
        draw.text((chosen_x, chosen_y), text, fill=(245, 248, 252, 245), font=font)


def _find_solar_elevation_latitude(
    lon_deg: float,
    target_elev_deg: float,
    dt_utc: datetime.datetime,
) -> float | None:
    previous_lat = -90.0
    previous_elev = solar_elevation_deg(previous_lat, lon_deg, dt_utc) - target_elev_deg

    for lat in range(-89, 91):
        elev = solar_elevation_deg(float(lat), lon_deg, dt_utc) - target_elev_deg
        if previous_elev == 0.0:
            return previous_lat
        if previous_elev * elev < 0:
            fraction = previous_elev / (previous_elev - elev)
            return previous_lat + fraction * (lat - previous_lat)
        previous_lat = float(lat)
        previous_elev = elev
    return None


def _draw_smooth_grayline(
    draw: ImageDraw.ImageDraw,
    width: int,
    height: int,
    dt_utc: datetime.datetime,
) -> None:
    outer_points: list[tuple[int, int]] = []
    inner_points: list[tuple[int, int]] = []
    center_points: list[tuple[int, int]] = []

    for lon in range(-180, 181, 2):
        outer_lat = _find_solar_elevation_latitude(float(lon), 6.0, dt_utc)
        inner_lat = _find_solar_elevation_latitude(float(lon), -6.0, dt_utc)
        center_lat = _find_solar_elevation_latitude(float(lon), 0.0, dt_utc)

        x, _ = _latlon_to_xy(0.0, float(lon), width, height)
        if outer_lat is not None:
            _, outer_y = _latlon_to_xy(outer_lat, float(lon), width, height)
            outer_points.append((x, outer_y))
        if inner_lat is not None:
            _, inner_y = _latlon_to_xy(inner_lat, float(lon), width, height)
            inner_points.append((x, inner_y))
        if center_lat is not None:
            _, center_y = _latlon_to_xy(center_lat, float(lon), width, height)
            center_points.append((x, center_y))

    if len(outer_points) > 2 and len(inner_points) > 2:
        polygon = outer_points + list(reversed(inner_points))
        draw.polygon(polygon, fill=(194, 134, 70, 75))

    if len(center_points) > 2:
        draw.line(center_points, fill=(194, 134, 70, 55), width=6, joint="curve")
        draw.line(center_points, fill=(157, 102, 58, 235), width=2, joint="curve")


def render_paths_map(
    matches: Iterable[tuple[dict, str, str]],
    home_coords: tuple[float, float],
    dt_utc: datetime.datetime | None = None,
    out_path: str = DEFAULT_MAP_OUT,
    size: tuple[int, int] = (1000, 500),
    geojson_path: str = DEFAULT_COUNTRIES_GEOJSON,
    home_locator: str = "",
) -> str | None:
    """
    Genera una mappa PNG con contorni geografici, griglia, fascia grayline approssimata,
    evidenziazione dei paesi coinvolti, QTH di riferimento e tratte great-circle.
    Restituisce out_path se generata, altrimenti None.
    """
    match_list = list(matches)
    if not match_list:
        return None

    ref_dt = dt_utc or datetime.datetime.now(datetime.timezone.utc)
    if ref_dt.tzinfo is None:
        ref_dt = ref_dt.replace(tzinfo=datetime.timezone.utc)

    w, h = size
    base = Image.new("RGBA", (w, h), (12, 18, 28, 255))
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw_base = ImageDraw.Draw(base, "RGBA")
    draw_ov = ImageDraw.Draw(overlay, "RGBA")

    resolved_spots: list[tuple[dict, str, tuple[float, float]]] = []
    destinations: list[tuple[float, float, str, str]] = []
    for spot, priority, _reason in match_list:
        dst = _resolve_dx_coords(spot)
        if not dst:
            continue
        resolved_spots.append((spot, priority, dst))
        destinations.append((dst[0], dst[1], priority, spot.get("dx_call", "")))

    if not resolved_spots:
        return None

    # Griglia meridiani/paralleli ogni 30°
    grid_color = (34, 48, 68, 255)
    for lon in range(-180, 181, 30):
        x, _ = _latlon_to_xy(0.0, float(lon), w, h)
        draw_base.line([(x, 0), (x, h)], fill=grid_color, width=1)
    for lat in range(-60, 61, 30):
        _, y = _latlon_to_xy(float(lat), 0.0, w, h)
        draw_base.line([(0, y), (w, y)], fill=grid_color, width=1)

    # Equatore più marcato
    _, eq_y = _latlon_to_xy(0.0, 0.0, w, h)
    draw_base.line([(0, eq_y), (w, eq_y)], fill=(58, 78, 106, 255), width=1)

    # Contorni continenti/paesi e paesi coinvolti
    draw_countries_layer(
        draw_base,
        w,
        h,
        home_coords=home_coords,
        destinations=destinations,
        geojson_path=geojson_path,
    )

    # Ombra notturna leggera: nessun riempimento a blocchi grandi.
    _draw_smooth_grayline(draw_ov, w, h, ref_dt)

    img = Image.alpha_composite(base, overlay)
    draw = ImageDraw.Draw(img, "RGBA")
    font = ImageFont.load_default()

    # Tratte great-circle per ciascuno spot risolto
    drawn_paths = 0
    labels_to_draw: list[tuple[int, int, str, str]] = []
    for spot, priority, dst in resolved_spots:
        arc = _great_circle_points(
            home_coords[0], home_coords[1], dst[0], dst[1], steps=70
        )
        if priority == "HIGH":
            color = (255, 72, 72, 225)
            lw = 3
        else:
            color = (64, 205, 255, 175)
            lw = 2

        _draw_segmented_polyline(draw, arc, w, h, fill=color, line_width=lw)
        dx_x, dx_y = _latlon_to_xy(dst[0], dst[1], w, h)
        r = 5 if priority == "HIGH" else 3
        draw.ellipse(
            [dx_x - r, dx_y - r, dx_x + r, dx_y + r],
            fill=color,
            outline=(255, 255, 255, 200),
        )
        call_label = (spot.get("dx_call") or "").strip()
        dx_locator = resolve_spot_locator(spot)
        if dx_locator:
            call_label = f"{call_label} [{dx_locator}]" if call_label else dx_locator
        if call_label:
            labels_to_draw.append((dx_x, dx_y, call_label, priority))
        drawn_paths += 1

    # Punto QTH di riferimento
    hx, hy = _latlon_to_xy(home_coords[0], home_coords[1], w, h)
    draw.ellipse(
        [hx - 6, hy - 6, hx + 6, hy + 6],
        fill=(90, 245, 130, 255),
        outline=(255, 255, 255, 255),
    )
    if home_locator:
        home_label = f"QTH [{home_locator}]"
        draw.rectangle([hx + 8, hy - 8, hx + 8 + len(home_label) * 6, hy + 5], fill=(15, 22, 34, 210))
        draw.text((hx + 11, hy - 7), home_label, fill=(220, 255, 230, 255), font=font)

    if drawn_paths == 0:
        return None

    _draw_labels_non_overlapping(draw, labels_to_draw, w, h, font)

    stamp = ref_dt.strftime("%Y-%m-%d %H:%M UTC")
    locator_txt = f" | QTH: {home_locator}" if home_locator else ""
    header_txt = f"DX Paths & Grayline (~6 deg) | {stamp} | Paths: {drawn_paths}{locator_txt}"
    draw.rectangle([8, 8, 650, 28], fill=(15, 22, 34, 210))
    draw.text((14, 12), header_txt, fill=(235, 242, 250, 255), font=font)

    out_dir = os.path.dirname(os.path.abspath(out_path))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    img.convert("RGB").save(out_path, format="PNG", optimize=True)
    return out_path


def send_photo_to_chats(
    image_path: str,
    caption: str,
    bot_token: str,
    chat_ids: list[str],
    silent: bool = False,
) -> None:
    """Invia il PNG generato tramite Telegram sendPhoto verso una lista di chat_id."""
    if (
        not image_path
        or not os.path.exists(image_path)
        or not bot_token
        or not chat_ids
    ):
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    for cid in chat_ids:
        try:
            with open(image_path, "rb") as fh:
                resp = request_with_retry(
                    lambda: requests.post(
                        url,
                        data={
                            "chat_id": cid,
                            "caption": caption[:1024],
                            "parse_mode": "HTML",
                            "disable_notification": silent,
                        },
                        files={"photo": ("dx_paths.png", fh, "image/png")},
                        timeout=20,
                    ),
                    attempts=3,
                )
            resp.raise_for_status()
        except requests.RequestException as err:
            print(f"Avviso Telegram (sendPhoto) verso {cid}: {err}")