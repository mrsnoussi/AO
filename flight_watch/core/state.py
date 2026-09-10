"""Persistance de l'historique des prix dans un fichier JSON versionne."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from flight_watch.core.models import Offer

STATE_VERSION = 1


def _empty_state() -> dict:
    return {"version": STATE_VERSION, "last_digest_date": None, "pairs": {}}


def load_state(path: str) -> dict:
    file_path = Path(path)
    if not file_path.exists():
        return _empty_state()
    with file_path.open("r", encoding="utf-8") as f:
        state = json.load(f)
    state.setdefault("version", STATE_VERSION)
    state.setdefault("last_digest_date", None)
    state.setdefault("pairs", {})
    return state


def save_state(path: str, state: dict) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def pair_key(offer: Offer) -> str:
    return f"{offer.destination}|{offer.depart_date.isoformat()}|{offer.nights}"


def update_state_with_offers(state: dict, offers: list[Offer], today: date) -> None:
    """Met a jour l'historique pour toutes les offres scannees (meme au-dessus
    du budget), pour que le recap reflete le vrai marche, pas seulement les
    offres qui ont declenche une alerte."""
    pairs = state.setdefault("pairs", {})
    today_iso = today.isoformat()
    for offer in offers:
        key = pair_key(offer)
        pair = pairs.setdefault(
            key,
            {
                "destination": offer.destination,
                "depart_date": offer.depart_date.isoformat(),
                "nights": offer.nights,
                "last_price_eur": None,
                "last_seen": None,
                "lowest_price_eur": None,
                "lowest_seen_date": None,
                "history": [],
            },
        )
        pair["last_price_eur"] = offer.price_eur
        pair["last_seen"] = offer.fetched_at.isoformat()
        if pair["lowest_price_eur"] is None or offer.price_eur < pair["lowest_price_eur"]:
            pair["lowest_price_eur"] = offer.price_eur
            pair["lowest_seen_date"] = today_iso

        history = pair["history"]
        if history and history[-1]["date"] == today_iso:
            history[-1]["price_eur"] = offer.price_eur
        else:
            history.append({"date": today_iso, "price_eur": offer.price_eur})
