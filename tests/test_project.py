import json
import os
import tempfile

import pytest

import config
import main
import propagation
import map_paths
from fetch_ng3k_dxpeditions import parse_ng3k_date
from project_utils import atomic_json_dump
from locators import maidenhead_to_latlon, normalize_locator, extract_locator


def test_normalize_frequency():
    assert main.normalize_freq_khz("14.200") == "14200.0"
    assert main.normalize_freq_khz("14200") == "14200.0"
    assert main.normalize_freq_khz("invalid") == "invalid"


def test_dedup_key_with_band():
    spot = {"dx_call": "k1abc", "band": "20m", "freq": "14200"}
    assert main._build_spot_dedup_key(spot) == "K1ABC|20M"


def test_dedup_key_frequency_bucket():
    spot = {"dx_call": "K1ABC", "band": "", "freq": "14203"}
    assert main._build_spot_dedup_key(spot) == "K1ABC|~14204kHz"


def test_dxpedition_alias_and_date_match():
    entries = [{
        "callsign": "3B9",
        "aliases": ["3B9/M0CFW", "3B9KW"],
        "start_date": "2026-10-20",
        "end_date": "2026-11-28",
    }]
    assert main.match_dxpedition("3B9KW", "1141 2026-11-22", entries) == entries[0]
    assert main.match_dxpedition("3B9KW", "1141 2026-12-01", entries) is None


def test_ng3k_date():
    assert parse_ng3k_date("2026 Oct20") == "2026-10-20"
    assert parse_ng3k_date("2026 Oct 20") == "2026-10-20"
    assert parse_ng3k_date("invalid") is None


def test_config_rejects_invalid_mode(monkeypatch):
    monkeypatch.setenv("TELEGRAM_NOTIFY_MODE", "LOW")
    with pytest.raises(ValueError, match="TELEGRAM_NOTIFY_MODE"):
        config.load_config()


def test_config_coordinates(monkeypatch):
    monkeypatch.setenv("MY_LAT", "44.5")
    monkeypatch.delenv("MY_LON", raising=False)
    with pytest.raises(ValueError, match="MY_LAT and MY_LON"):
        config.load_config()


def test_atomic_json_dump():
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, "state.json")
        atomic_json_dump({"ok": True}, path)
        with open(path, "r", encoding="utf-8") as handle:
            assert json.load(handle) == {"ok": True}


def test_seen_spots_prune(tmp_path):
    path = tmp_path / "seen.json"
    path.write_text(json.dumps({"OLD|20M": 1, "FRESH|20M": 9999999999}), encoding="utf-8")
    seen = main.load_seen_spots(str(path), window_minutes=30)
    assert "OLD|20M" not in seen


def test_solar_classification():
    assert propagation.classify_conditions({"k_index": 4, "a_index": 5, "sfi": 200}) == "Disturbed (K>=4)"
    assert propagation.classify_conditions({"k_index": 2, "a_index": 5, "sfi": 160}) == "Good HF / High bands"


def test_maidenhead_to_latlon():
    lat, lon = maidenhead_to_latlon("FN31pr")
    assert round(lat, 2) == 41.73
    assert round(lon, 2) == -72.71
    assert maidenhead_to_latlon("invalid") is None


def test_normalize_locator():
    assert normalize_locator("FN31pr") == "FN31PR"
    assert normalize_locator("fn31pr") == "FN31PR"
    assert normalize_locator("invalid") is None


def test_maidenhead_conversion():
    assert normalize_locator("jn45") == "JN45"
    assert normalize_locator("invalid") is None
    lat, lon = maidenhead_to_latlon("JN45")
    assert round(lat, 1) == 45.5
    assert round(lon, 1) == 9.0


def test_extract_locator():
    assert extract_locator("QSO from JN45AB, 20m") == "JN45AB"
    assert extract_locator("no grid here") == ""


def test_spot_locator_field(monkeypatch):
    monkeypatch.setenv("MY_QTH_LOCATOR", "JN45AB")
    config.load_config()


def test_locator_priority(monkeypatch):
    """The locator is preferred when valid; lat/lon remain fallbacks."""
    monkeypatch.setenv("MY_QTH_LOCATOR", "JN45AB")
    monkeypatch.setenv("MY_LAT", "44.5")
    monkeypatch.setenv("MY_LON", "-75.0")

    app_config = config.load_config()
    assert app_config.qth_locator == "JN45AB"

    monkeypatch.setenv("MY_QTH_LOCATOR", "FN31PR")
    app_config = config.load_config()
    assert app_config.qth_locator == "FN31PR"


def test_map_resolves_dx_locator_first():
    spot = {"dx_call": "K1ABC", "dx_locator": "FN31PR", "dxcc_entity": "United States"}
    lat, lon = map_paths._resolve_dx_coords(spot)
    assert round(lat, 2) == 41.73
    assert round(lon, 2) == -72.71
