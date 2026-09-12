"""Tests des providers a partir de reponses API simulees (fixtures JSON)."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import patch

from flight_watch.providers.serpapi import SerpApiProvider
from flight_watch.providers.travelpayouts import TravelpayoutsProvider

FIXTURES = Path(__file__).parent / "fixtures"


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict:
        return self._payload


def _load_fixture(name: str) -> dict:
    with (FIXTURES / name).open("r", encoding="utf-8") as f:
        return json.load(f)


def test_travelpayouts_parses_offer_within_window():
    payload = _load_fixture("travelpayouts_latest.json")
    provider = TravelpayoutsProvider(token="fake-token")

    with patch("flight_watch.providers.travelpayouts.get_with_backoff", return_value=FakeResponse(payload)):
        offers = provider.search(
            "PAR", "HKT", nights=14, window_start=date(2026, 10, 1), window_end=date(2027, 6, 30)
        )

    # Le 2e item de la fixture est daté 2019 (hors fenêtre) et doit être filtré.
    assert len(offers) == 1
    offer = offers[0]
    assert offer.price_eur == 320.0
    assert offer.source == "travelpayouts"
    assert offer.origin == "PAR"
    assert offer.destination == "HKT"
    assert offer.nights == 14
    assert offer.airlines == ("via Mytrip.com",)


def test_travelpayouts_filters_offers_outside_window():
    payload = _load_fixture("travelpayouts_latest.json")
    provider = TravelpayoutsProvider(token="fake-token")

    with patch("flight_watch.providers.travelpayouts.get_with_backoff", return_value=FakeResponse(payload)):
        offers = provider.search(
            "PAR", "HKT", nights=14, window_start=date(2030, 1, 1), window_end=date(2030, 12, 31)
        )

    assert offers == []


def test_serpapi_picks_cheapest_candidate():
    payload = _load_fixture("serpapi_google_flights.json")
    provider = SerpApiProvider(api_key="fake-key", max_calls_per_run=1)

    with patch("flight_watch.providers.serpapi.get_with_backoff", return_value=FakeResponse(payload)):
        offers = provider.search(
            "PAR", "BKK", nights=14, window_start=date(2026, 10, 1), window_end=date(2026, 10, 1)
        )

    # Deux candidats dans la fixture (410 et 480), le moins cher doit être retenu.
    assert len(offers) == 1
    assert offers[0].price_eur == 410.0
    assert offers[0].source == "serpapi"
    assert offers[0].airlines == ("Thai Airways",)


def test_serpapi_respects_call_budget():
    payload = _load_fixture("serpapi_google_flights.json")
    provider = SerpApiProvider(api_key="fake-key", max_calls_per_run=1)

    with patch("flight_watch.providers.serpapi.get_with_backoff", return_value=FakeResponse(payload)) as mocked:
        provider.search(
            "PAR", "BKK", nights=14, window_start=date(2026, 10, 1), window_end=date(2027, 6, 30)
        )

    # La fenêtre couvre des dizaines de dates par pas de 7 jours, mais le
    # budget d'appels est fixé à 1 : un seul appel HTTP doit être effectué.
    assert mocked.call_count == 1
