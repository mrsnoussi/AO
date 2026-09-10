"""Tests de la mise a jour de l'etat (historique, dernier prix, plus bas prix)."""
from __future__ import annotations

from datetime import date, datetime, timezone

from flight_watch.core.models import Offer
from flight_watch.core.state import update_state_with_offers


def _offer(price: float, fetched_at: datetime | None = None) -> Offer:
    return Offer(
        origin="PAR",
        destination="HKT",
        depart_date=date(2026, 11, 5),
        return_date=date(2026, 11, 19),
        nights=14,
        price_eur=price,
        airlines=("XX",),
        stops_outbound=0,
        stops_return=0,
        duration_outbound_minutes=600,
        duration_return_minutes=600,
        source="travelpayouts",
        fetched_at=fetched_at or datetime.now(timezone.utc),
    )


def test_update_state_creates_pair_and_history_entry():
    state = {"pairs": {}}

    update_state_with_offers(state, [_offer(320)], date(2026, 9, 10))

    pair = state["pairs"]["HKT|2026-11-05|14"]
    assert pair["last_price_eur"] == 320
    assert pair["lowest_price_eur"] == 320
    assert pair["lowest_seen_date"] == "2026-09-10"
    assert pair["history"] == [{"date": "2026-09-10", "price_eur": 320}]


def test_update_state_tracks_lowest_price_across_runs():
    state = {"pairs": {}}
    update_state_with_offers(state, [_offer(320)], date(2026, 9, 10))
    update_state_with_offers(state, [_offer(280)], date(2026, 9, 12))
    update_state_with_offers(state, [_offer(310)], date(2026, 9, 14))

    pair = state["pairs"]["HKT|2026-11-05|14"]
    assert pair["last_price_eur"] == 310  # dernier prix vu = le plus recent
    assert pair["lowest_price_eur"] == 280  # le plus bas jamais vu
    assert pair["lowest_seen_date"] == "2026-09-12"
    assert len(pair["history"]) == 3


def test_update_state_same_day_rerun_overwrites_not_duplicates():
    state = {"pairs": {}}
    update_state_with_offers(state, [_offer(320)], date(2026, 9, 10))
    update_state_with_offers(state, [_offer(300)], date(2026, 9, 10))

    pair = state["pairs"]["HKT|2026-11-05|14"]
    assert len(pair["history"]) == 1
    assert pair["history"][0]["price_eur"] == 300
    assert pair["last_price_eur"] == 300
