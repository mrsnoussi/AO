"""Orchestration : scan de la matrice route x duree, fusion, alertes, recap."""
from __future__ import annotations

import logging
import os
import sys
from datetime import date, datetime, timezone

from dotenv import load_dotenv

from flight_watch import config
from flight_watch.core import alerting, mailer, merge
from flight_watch.core import state as state_module
from flight_watch.core.digest import compute_digest, mark_digest_sent, should_send_digest
from flight_watch.core.matrix import search_window, stay_durations
from flight_watch.core.models import Offer
from flight_watch.providers.base import Provider, ProviderError
from flight_watch.providers.serpapi import SerpApiProvider
from flight_watch.providers.travelpayouts import TravelpayoutsProvider

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("flight_watch")


def build_providers() -> list[Provider]:
    providers: list[Provider] = []

    try:
        providers.append(TravelpayoutsProvider())
    except ProviderError as exc:
        logger.error("Travelpayouts indisponible: %s", exc)

    if os.environ.get("SERPAPI_ENABLED", "false").strip().lower() == "true":
        try:
            providers.append(SerpApiProvider())
        except ProviderError as exc:
            logger.error("SerpAPI indisponible: %s", exc)
    else:
        logger.info("SerpAPI desactive (SERPAPI_ENABLED != true)")

    return providers


def scan(providers: list[Provider], today: date) -> list[Offer]:
    window_start, window_end = search_window(today)
    logger.info("Fenetre de recherche: %s -> %s", window_start.isoformat(), window_end.isoformat())

    all_offers: list[Offer] = []
    for route in config.ROUTES:
        for nights in stay_durations():
            for provider in providers:
                try:
                    offers = provider.search(route.origin, route.destination, nights, window_start, window_end)
                except ProviderError as exc:
                    logger.error(
                        "%s a echoue pour %s->%s (%d nuits): %s",
                        provider.name,
                        route.origin,
                        route.destination,
                        nights,
                        exc,
                    )
                    continue
                except Exception:  # noqa: BLE001 - un provider ne doit jamais interrompre le run
                    logger.exception(
                        "Erreur inattendue du provider %s pour %s->%s (%d nuits)",
                        provider.name,
                        route.origin,
                        route.destination,
                        nights,
                    )
                    continue

                all_offers.extend(offers)
    return all_offers


def budgets_by_destination() -> dict[str, float]:
    return {route.destination: route.budget_eur for route in config.ROUTES}


def main() -> int:
    load_dotenv()
    today = datetime.now(timezone.utc).date()
    logger.info("Demarrage du scan (%s)", today.isoformat())

    providers = build_providers()
    if not providers:
        logger.error("Aucun provider disponible, arret.")
        return 1

    raw_offers = scan(providers, today)
    merged_offers = merge.merge_offers(raw_offers)
    logger.info(
        "%d offre(s) brute(s) toutes sources, %d apres fusion/dedoublonnage",
        len(raw_offers),
        len(merged_offers),
    )

    state = state_module.load_state(config.STATE_FILE)

    budgets = budgets_by_destination()
    alertable = alerting.filter_alertable_offers(merged_offers, state, budgets)
    logger.info("%d offre(s) sous budget et nouvelle(s)/en baisse suffisante -> alerte", len(alertable))

    # Mise a jour de l'etat APRES avoir calcule les alertes (qui comparent au
    # dernier prix vu), avec TOUTES les offres scannees pour que le recap
    # reflete le vrai marche.
    state_module.update_state_with_offers(state, merged_offers, today)

    sent_alerts = 0
    for offer in alertable:
        subject, html = mailer.render_alert_email(offer)
        try:
            mailer.send_email(subject, html)
            sent_alerts += 1
        except mailer.MailerError as exc:
            logger.error("Envoi du mail d'alerte echoue pour %s le %s: %s", offer.destination, offer.depart_date, exc)

    if should_send_digest(state, today):
        digest_data = compute_digest(state, today)
        subject, html = mailer.render_digest_email(digest_data, today.isoformat())
        try:
            mailer.send_email(subject, html)
            mark_digest_sent(state, today)
        except mailer.MailerError as exc:
            logger.error("Envoi du recap echoue: %s", exc)
    else:
        logger.info("Recap pas encore du")

    state_module.save_state(config.STATE_FILE, state)
    logger.info("Termine: %d alerte(s) envoyee(s)", sent_alerts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
