"""Tests de la regle de declenchement des alertes (nouveaute / baisse >= 5 EUR)."""
from __future__ import annotations

from datetime import date, datetime, timezone

from flight_watch.core.alerting import filter_alertable_offers
from flight_watch.core.models import Offer

DEPART = date(2026, 11, 5)
RETURN = date(2026, 11, 19)


def _offer(destination: str, price: float) -> Offer:
    return Offer(
        origin="PAR",
        destination=destination,
        depart_date=DEPART,
        return_date=RETURN,
        nights=14,
        price_eur=price,
        airlines=("XX",),
        stops_outbound=0,
        stops_return=0,
        duration_outbound_minutes=600,
        duration_return_minutes=600,
        source="travelpayouts",
        fetched_at=datetime.now(timezone.utc),
    )


def test_new_offer_under_budget_is_alertable():
    offer = _offer("HKT", 290)
    state = {"pairs": {}}

    result = filter_alertable_offers([offer], state, {"HKT": 300})

    assert result == [offer]


def test_offer_over_budget_is_never_alertable():
    offer = _offer("HKT", 320)
    state = {"pairs": {}}

    result = filter_alertable_offers([offer], state, {"HKT": 300})

    assert result == []


def test_same_price_seen_again_is_not_alertable():
    offer = _offer("HKT", 290)
    state = {"pairs": {"HKT|2026-11-05|14": {"last_price_eur": 290}}}

    result = filter_alertable_offers([offer], state, {"HKT": 300})

    assert result == []


def test_price_drop_below_5_euros_threshold_is_not_alertable():
    offer = _offer("HKT", 288)  # -2 EUR vs dernier prix vu
    state = {"pairs": {"HKT|2026-11-05|14": {"last_price_eur": 290}}}

    result = filter_alertable_offers([offer], state, {"HKT": 300})

    assert result == []


def test_price_drop_of_at_least_5_euros_is_alertable():
    offer = _offer("HKT", 284)  # -6 EUR vs dernier prix vu
    state = {"pairs": {"HKT|2026-11-05|14": {"last_price_eur": 290}}}

    result = filter_alertable_offers([offer], state, {"HKT": 300})

    assert result == [offer]


def test_price_increase_is_not_alertable_even_under_budget():
    offer = _offer("HKT", 295)  # +5 EUR vs dernier prix vu, toujours sous budget
    state = {"pairs": {"HKT|2026-11-05|14": {"last_price_eur": 290}}}

    result = filter_alertable_offers([offer], state, {"HKT": 300})

    assert result == []
