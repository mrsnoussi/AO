"""Recap periodique : declenchement et calcul des statistiques."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from flight_watch import config


@dataclass
class DigestData:
    # destination -> (prix, date de depart, date a laquelle il a ete vu)
    lowest_by_destination: dict[str, tuple[float, str, str]]
    # (destination, "YYYY-MM") -> (prix, date de depart)
    lowest_by_destination_month: dict[tuple[str, str], tuple[float, str]]
    # destination -> (delta en euros, delta en %) ou None si pas assez de donnees
    trends: dict[str, tuple[float, float] | None]


def should_send_digest(state: dict, today: date) -> bool:
    last = state.get("last_digest_date")
    if not last:
        return True
    last_date = date.fromisoformat(last)
    return (today - last_date).days >= config.DIGEST_INTERVAL_DAYS


def mark_digest_sent(state: dict, today: date) -> None:
    state["last_digest_date"] = today.isoformat()


def _price_at_or_before(history: list[dict], cutoff: date) -> float | None:
    best: tuple[date, float] | None = None
    for entry in history:
        entry_date = date.fromisoformat(entry["date"])
        if entry_date <= cutoff and (best is None or entry_date > best[0]):
            best = (entry_date, entry["price_eur"])
    return best[1] if best else None


def compute_digest(state: dict, today: date) -> DigestData:
    cutoff = today - timedelta(days=config.DIGEST_INTERVAL_DAYS)

    lowest_by_destination: dict[str, tuple[float, str, str]] = {}
    lowest_by_destination_month: dict[tuple[str, str], tuple[float, str]] = {}
    trend_current: dict[str, float] = {}
    trend_past: dict[str, float] = {}

    for pair in state.get("pairs", {}).values():
        destination = pair["destination"]
        depart_date = pair["depart_date"]
        depart_month = depart_date[:7]
        lowest_price = pair.get("lowest_price_eur")
        lowest_seen = pair.get("lowest_seen_date")

        if lowest_price is not None:
            current = lowest_by_destination.get(destination)
            if current is None or lowest_price < current[0]:
                lowest_by_destination[destination] = (lowest_price, depart_date, lowest_seen)

            month_key = (destination, depart_month)
            current_month = lowest_by_destination_month.get(month_key)
            if current_month is None or lowest_price < current_month[0]:
                lowest_by_destination_month[month_key] = (lowest_price, depart_date)

        history = pair.get("history", [])
        latest_price = _price_at_or_before(history, today)
        past_price = _price_at_or_before(history, cutoff)
        if latest_price is not None:
            trend_current[destination] = min(trend_current.get(destination, latest_price), latest_price)
        if past_price is not None:
            trend_past[destination] = min(trend_past.get(destination, past_price), past_price)

    trends: dict[str, tuple[float, float] | None] = {}
    for destination in set(trend_current) | set(trend_past):
        current_price = trend_current.get(destination)
        past_price = trend_past.get(destination)
        if current_price is None or past_price is None or past_price == 0:
            trends[destination] = None
            continue
        delta_eur = current_price - past_price
        delta_pct = (delta_eur / past_price) * 100
        trends[destination] = (delta_eur, delta_pct)

    return DigestData(
        lowest_by_destination=lowest_by_destination,
        lowest_by_destination_month=lowest_by_destination_month,
        trends=trends,
    )
