"""Tests du declenchement et du calcul du recap bi-hebdomadaire."""
from __future__ import annotations

from datetime import date

from flight_watch.core.digest import compute_digest, mark_digest_sent, should_send_digest


def test_should_send_digest_when_never_sent():
    assert should_send_digest({}, date(2026, 9, 10)) is True


def test_should_not_send_digest_before_interval_elapsed():
    state = {"last_digest_date": "2026-09-01"}
    assert should_send_digest(state, date(2026, 9, 10)) is False  # 9 jours < 14


def test_should_send_digest_exactly_at_interval():
    state = {"last_digest_date": "2026-09-01"}
    assert should_send_digest(state, date(2026, 9, 15)) is True  # 14 jours


def test_should_send_digest_after_interval():
    state = {"last_digest_date": "2026-09-01"}
    assert should_send_digest(state, date(2026, 9, 20)) is True


def test_mark_digest_sent_updates_state():
    state: dict = {}
    mark_digest_sent(state, date(2026, 9, 10))
    assert state["last_digest_date"] == "2026-09-10"


def test_compute_digest_lowest_by_destination_and_by_month():
    state = {
        "pairs": {
            "HKT|2026-11-05|14": {
                "destination": "HKT",
                "depart_date": "2026-11-05",
                "lowest_price_eur": 300,
                "lowest_seen_date": "2026-09-05",
                "history": [{"date": "2026-09-05", "price_eur": 300}],
            },
            "HKT|2026-12-10|14": {
                "destination": "HKT",
                "depart_date": "2026-12-10",
                "lowest_price_eur": 280,
                "lowest_seen_date": "2026-09-08",
                "history": [{"date": "2026-09-08", "price_eur": 280}],
            },
            "KBV|2026-11-20|21": {
                "destination": "KBV",
                "depart_date": "2026-11-20",
                "lowest_price_eur": 340,
                "lowest_seen_date": "2026-09-02",
                "history": [{"date": "2026-09-02", "price_eur": 340}],
            },
        }
    }

    digest = compute_digest(state, date(2026, 9, 10))

    assert digest.lowest_by_destination["HKT"] == (280, "2026-12-10", "2026-09-08")
    assert digest.lowest_by_destination["KBV"] == (340, "2026-11-20", "2026-09-02")
    assert digest.lowest_by_destination_month[("HKT", "2026-11")] == (300, "2026-11-05")
    assert digest.lowest_by_destination_month[("HKT", "2026-12")] == (280, "2026-12-10")


def test_compute_digest_trend_percent_and_euros():
    today = date(2026, 9, 10)  # cutoff = 2026-08-27
    state = {
        "pairs": {
            "HKT|2026-11-05|14": {
                "destination": "HKT",
                "depart_date": "2026-11-05",
                "lowest_price_eur": 280,
                "lowest_seen_date": "2026-09-08",
                "history": [
                    {"date": "2026-08-20", "price_eur": 350},
                    {"date": "2026-09-08", "price_eur": 280},
                ],
            },
        }
    }

    digest = compute_digest(state, today)

    delta_eur, delta_pct = digest.trends["HKT"]
    assert delta_eur == -70
    assert round(delta_pct, 1) == -20.0


def test_compute_digest_trend_none_without_enough_history():
    today = date(2026, 9, 10)
    state = {
        "pairs": {
            "HKT|2026-11-05|14": {
                "destination": "HKT",
                "depart_date": "2026-11-05",
                "lowest_price_eur": 280,
                "lowest_seen_date": "2026-09-08",
                "history": [{"date": "2026-09-08", "price_eur": 280}],
            },
        }
    }

    digest = compute_digest(state, today)

    assert digest.trends["HKT"] is None
