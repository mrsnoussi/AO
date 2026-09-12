"""Source optionnelle : SerpAPI Google Flights.

Desactivee par defaut (SERPAPI_ENABLED != "true"), a activer si vous
souscrivez un plan payant pour une couverture quasi complete. Le tier
gratuit (250 requetes/mois, partagees entre tous les produits SerpAPI) ne
couvre qu'une fraction de la matrice complete : on echantillonne donc les
dates de depart par pas de config.DEPARTURE_STEP_DAYS, borne par un budget
d'appels configurable (SERPAPI_MAX_CALLS_PER_RUN), plutot que de tout
scanner.

Limite connue : pour un aller-retour, SerpAPI retourne les segments
aller et retour melanges dans `flights[]` sans separation explicite. On ne
tente pas de les re-scinder precisement : les compagnies sont agregees et le
nombre d'escales est reporte en tant que total (aller+retour confondus).
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta, timezone

from flight_watch import config
from flight_watch.core.matrix import departure_dates
from flight_watch.core.models import Offer
from flight_watch.providers.base import Provider, ProviderError
from flight_watch.providers.http_utils import RequestFailed, get_with_backoff

logger = logging.getLogger(__name__)

API_URL = "https://serpapi.com/search"


class SerpApiProvider(Provider):
    name = "serpapi"

    def __init__(
        self,
        api_key: str | None = None,
        currency: str = "EUR",
        timeout: float = 20.0,
        max_retries: int = 3,
        max_calls_per_run: int | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.environ.get("SERPAPI_API_KEY")
        self.currency = currency
        self.timeout = timeout
        self.max_retries = max_retries
        self.max_calls_per_run = (
            max_calls_per_run if max_calls_per_run is not None else config.SERPAPI_MAX_CALLS_PER_RUN
        )
        self._calls_made = 0
        if not self.api_key:
            raise ProviderError("SERPAPI_API_KEY manquant")

    def search(
        self,
        origin: str,
        destination: str,
        nights: int,
        window_start: date,
        window_end: date,
    ) -> list[Offer]:
        offers: list[Offer] = []
        for depart_date in departure_dates(window_start, window_end):
            if self._calls_made >= self.max_calls_per_run:
                logger.info(
                    "SerpAPI: budget d'appels (%d) epuise pour ce run, echantillonnage arrete",
                    self.max_calls_per_run,
                )
                break
            return_date = depart_date + timedelta(days=nights)
            self._calls_made += 1
            offer = self._search_one(origin, destination, depart_date, return_date, nights)
            if offer is not None:
                offers.append(offer)

        logger.info(
            "SerpAPI %s->%s (%d nuits): %d offre(s) trouvee(s) (%d appel(s) utilise(s))",
            origin,
            destination,
            nights,
            len(offers),
            self._calls_made,
        )
        return offers

    def _search_one(
        self, origin: str, destination: str, depart_date: date, return_date: date, nights: int
    ) -> Offer | None:
        params = {
            "engine": "google_flights",
            "departure_id": origin,
            "arrival_id": destination,
            "outbound_date": depart_date.isoformat(),
            "return_date": return_date.isoformat(),
            "currency": self.currency,
            "type": "1",
            "api_key": self.api_key,
        }
        try:
            response = get_with_backoff(
                API_URL, params=params, timeout=self.timeout, max_retries=self.max_retries
            )
        except RequestFailed as exc:
            logger.warning("SerpAPI %s->%s le %s a echoue: %s", origin, destination, depart_date, exc)
            return None

        try:
            payload = response.json()
        except ValueError as exc:
            logger.warning("SerpAPI: reponse JSON invalide pour %s->%s: %s", origin, destination, exc)
            return None

        candidates = payload.get("best_flights") or payload.get("other_flights") or []
        priced = [c for c in candidates if isinstance(c.get("price"), (int, float))]
        if not priced:
            return None

        cheapest = min(priced, key=lambda item: item["price"])
        return self._parse_offer(cheapest, origin, destination, depart_date, return_date, nights)

    def _parse_offer(
        self,
        item: dict,
        origin: str,
        destination: str,
        depart_date: date,
        return_date: date,
        nights: int,
    ) -> Offer | None:
        price = item.get("price")
        if price is None:
            return None

        legs = item.get("flights", [])
        airlines = tuple(dict.fromkeys(leg["airline"] for leg in legs if leg.get("airline")))
        stops_total = max(len(legs) - 2, 0) if legs else 0

        return Offer(
            origin=origin,
            destination=destination,
            depart_date=depart_date,
            return_date=return_date,
            nights=nights,
            price_eur=float(price),
            airlines=airlines,
            stops_outbound=stops_total,
            stops_return=0,
            duration_outbound_minutes=item.get("total_duration"),
            duration_return_minutes=None,
            source=self.name,
            fetched_at=datetime.now(timezone.utc),
        )
