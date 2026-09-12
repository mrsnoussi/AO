"""Regles de declenchement des alertes mail."""
from __future__ import annotations

from flight_watch import config
from flight_watch.core.models import Offer


def _state_key(offer: Offer) -> str:
    return f"{offer.destination}|{offer.depart_date.isoformat()}|{offer.nights}"


def should_alert(offer: Offer, pair_state: dict | None) -> bool:
    """Une offre merite un nouveau mail si elle n'a jamais ete vue, ou si son
    prix baisse d'au moins MIN_PRICE_DROP_EUR par rapport au dernier prix vu
    pour ce meme couple destination/date de depart/duree. On ne re-alerte
    jamais deux fois la meme offre au meme prix."""
    if pair_state is None:
        return True
    last_price = pair_state.get("last_price_eur")
    if last_price is None:
        return True
    return offer.price_eur <= last_price - config.MIN_PRICE_DROP_EUR


def filter_alertable_offers(
    offers: list[Offer], state: dict, budgets: dict[str, float]
) -> list[Offer]:
    """Filtre les offres a notifier : sous le budget de leur route, et
    nouvelles ou en baisse de prix suffisante. Doit etre appele avec l'etat
    *avant* sa mise a jour par le scan courant."""
    pairs = state.get("pairs", {})
    alertable: list[Offer] = []
    for offer in offers:
        budget = budgets.get(offer.destination)
        if budget is not None and offer.price_eur > budget:
            continue
        pair_state = pairs.get(_state_key(offer))
        if should_alert(offer, pair_state):
            alertable.append(offer)
    return alertable
