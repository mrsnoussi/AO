"""Fusion et dedoublonnage des offres issues de plusieurs sources."""
from __future__ import annotations

from flight_watch.core.models import Offer


def merge_offers(offers: list[Offer]) -> list[Offer]:
    """Fusionne des offres de plusieurs providers et deduplique.

    Pour chaque cle (destination, date de depart, nombre de nuits), ne garde
    que l'offre la moins chere toutes sources confondues, en conservant sa
    source d'origine (offer.source).
    """
    best_by_key: dict[tuple[str, str, int], Offer] = {}
    for offer in offers:
        key = offer.pair_key
        current_best = best_by_key.get(key)
        if current_best is None or offer.price_eur < current_best.price_eur:
            best_by_key[key] = offer
    return sorted(best_by_key.values(), key=lambda o: (o.destination, o.depart_date, o.nights))
