"""Source principale : Travelpayouts / Aviasales Data API (prix caches).

Endpoint v2/prices/latest : prix les moins chers vus dans le cache par les
utilisateurs d'Aviasales durant les dernieres 48h, pour une route et une
duree de sejour donnees. Gratuit, inscription simple, aucun seuil de trafic
requis (contrairement a l'API de recherche temps reel, qui exige 50 000 MAU
et interdit l'usage automatise). Cette source ne permet pas d'interroger une
date de depart precise : on filtre les dates realistes retournees par
l'API sur la fenetre de recherche voulue.

Schema reel de la reponse (verifie par appel live, differe de la doc
publique et des autres endpoints Aviasales) : depart_date/return_date sont
des dates simples (pas de datetime), le prix est dans `value` (pas
`price`), le nombre d'escales dans `number_of_changes` (une seule valeur,
non scindee aller/retour), et il n'y a PAS de champ compagnie aerienne :
seul `gate` (le site vendeur, ex. "Mytrip.com") est disponible.
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timezone

from flight_watch import config
from flight_watch.core.models import Offer
from flight_watch.providers.base import Provider, ProviderError
from flight_watch.providers.http_utils import RequestFailed, get_with_backoff

logger = logging.getLogger(__name__)

API_URL = "https://api.travelpayouts.com/v2/prices/latest"

# trip_duration Travelpayouts est exprime en semaines.
_NIGHTS_TO_WEEKS = {14: 2, 21: 3}


class TravelpayoutsProvider(Provider):
    name = "travelpayouts"

    def __init__(
        self,
        token: str | None = None,
        currency: str = "eur",
        timeout: float = 10.0,
        max_retries: int = 3,
        limit: int = 100,
    ) -> None:
        self.token = token if token is not None else os.environ.get("TRAVELPAYOUTS_TOKEN")
        self.currency = currency
        self.timeout = timeout
        self.max_retries = max_retries
        self.limit = limit
        if not self.token:
            raise ProviderError("TRAVELPAYOUTS_TOKEN manquant")

    def search(
        self,
        origin: str,
        destination: str,
        nights: int,
        window_start: date,
        window_end: date,
    ) -> list[Offer]:
        weeks = _NIGHTS_TO_WEEKS.get(nights)
        if weeks is None:
            logger.warning("Travelpayouts: duree de sejour %d nuits non supportee, ignoree", nights)
            return []

        params = {
            "origin": origin,
            "destination": destination,
            "currency": self.currency,
            "one_way": "false",
            "trip_duration": weeks,
            "limit": self.limit,
            "sorting": "price",
            "token": self.token,
        }
        try:
            response = get_with_backoff(
                API_URL, params=params, timeout=self.timeout, max_retries=self.max_retries
            )
        except RequestFailed as exc:
            raise ProviderError(f"Travelpayouts: {exc}") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderError(f"Travelpayouts: reponse JSON invalide: {exc}") from exc

        if payload.get("success") is False:
            raise ProviderError(f"Travelpayouts a repondu success=false pour {origin}->{destination}")

        raw_items = payload.get("data", [])
        offers: list[Offer] = []
        for item in raw_items:
            offer = self._parse_offer(item, origin, destination, window_start, window_end)
            if offer is not None:
                offers.append(offer)

        logger.info(
            "Travelpayouts %s->%s (%d nuits): %d offre(s) en cache, %d dans la fenetre",
            origin,
            destination,
            nights,
            len(raw_items),
            len(offers),
        )
        return offers

    def _parse_offer(
        self,
        item: dict,
        origin: str,
        destination: str,
        window_start: date,
        window_end: date,
    ) -> Offer | None:
        try:
            depart_raw = item["depart_date"]
            return_raw = item["return_date"]
            price = float(item["value"])
        except (KeyError, TypeError, ValueError):
            return None

        depart_date = _parse_date(depart_raw)
        return_date = _parse_date(return_raw)
        if depart_date is None or return_date is None:
            return None
        if not (window_start <= depart_date <= window_end):
            return None

        actual_nights = (return_date - depart_date).days
        # Le cache n'est qu'approximativement aligne sur trip_duration : on ne
        # retient que les sejours reellement dans la fourchette demandee
        # (14-21 nuits), pas une tolerance autour de la cible interrogee.
        if not (config.STAY_MIN_NIGHTS <= actual_nights <= config.STAY_MAX_NIGHTS):
            return None

        # Pas de compagnie aerienne sur cet endpoint : on retombe sur le site
        # vendeur (gate) comme information utile a la place.
        gate = item.get("gate")
        airlines = (f"via {gate}",) if gate else ()

        # number_of_changes n'est pas scinde aller/retour ; on reporte la
        # meme valeur des deux cotes plutot que d'inventer un 0 trompeur.
        changes = int(item.get("number_of_changes", 0) or 0)

        return Offer(
            origin=origin,
            destination=destination,
            depart_date=depart_date,
            return_date=return_date,
            nights=actual_nights,
            price_eur=price,
            airlines=airlines,
            stops_outbound=changes,
            stops_return=changes,
            # `duration` sur cet endpoint est le temps de vol total aller+retour
            # combine (pas juste l'aller) : on ne le reutilise pas ici pour ne
            # pas afficher une duree de vol aller trompeuse.
            duration_outbound_minutes=None,
            duration_return_minutes=None,
            source=self.name,
            fetched_at=datetime.now(timezone.utc),
        )


def _parse_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None
