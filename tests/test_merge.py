"""Tests de la fusion multi-sources et du dedoublonnage."""
from __future__ import annotations

from datetime import date, datetime, timezone

from flight_watch.core.merge import merge_offers
from flight_watch.core.models import Offer


def _offer(destination: str, depart_date: date, nights: int, price: float, source: str) -> Offer:
    return Offer(
        origin="PAR",
        destination=destination,
        depart_date=depart_date,
        return_date=depart_date,
        nights=nights,
        price_eur=price,
        airlines=("XX",),
        stops_outbound=0,
        stops_return=0,
        duration_outbound_minutes=600,
        duration_return_minutes=600,
        source=source,
        fetched_at=datetime.now(timezone.utc),
    )


def test_merge_keeps_cheapest_across_sources_for_same_pair():
    d = date(2026, 11, 5)
    offers = [
        _offer("HKT", d, 14, 350, "travelpayouts"),
        _offer("HKT", d, 14, 310, "serpapi"),
        _offer("HKT", d, 14, 330, "travelpayouts"),
    ]

    merged = merge_offers(offers)

    assert len(merged) == 1
    assert merged[0].price_eur == 310
    assert merged[0].source == "serpapi"


def test_merge_keeps_distinct_destinations_dates_and_durations_separate():
    offers = [
        _offer("HKT", date(2026, 11, 5), 14, 300, "travelpayouts"),
        _offer("HKT", date(2026, 11, 12), 14, 300, "travelpayouts"),
        _offer("HKT", date(2026, 11, 5), 21, 300, "travelpayouts"),
        _offer("KBV", date(2026, 11, 5), 14, 500, "travelpayouts"),
    ]

    merged = merge_offers(offers)

    assert len(merged) == 4
    keys = {o.pair_key for o in merged}
    assert len(keys) == 4


def test_merge_empty_list_returns_empty():
    assert merge_offers([]) == []
