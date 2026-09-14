"""Configuration centrale de l'agent de veille de vols.

Toutes les valeurs metier (routes, budgets, fenetre de recherche, durees de
sejour, regles d'alerte) sont centralisees ici.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RouteConfig:
    origin: str
    destination: str
    label: str
    budget_eur: int


ROUTES: list[RouteConfig] = [
    RouteConfig(origin="PAR", destination="HKT", label="Paris - Phuket", budget_eur=300),
    RouteConfig(origin="PAR", destination="URT", label="Paris - Surat Thani", budget_eur=300),
    RouteConfig(origin="PAR", destination="KBV", label="Paris - Krabi", budget_eur=300),
    RouteConfig(origin="PAR", destination="BKK", label="Paris - Bangkok", budget_eur=300),
    RouteConfig(origin="PAR", destination="MIA", label="Paris - Miami", budget_eur=300),
    RouteConfig(origin="PAR", destination="LAS", label="Paris - Las Vegas", budget_eur=300),
    RouteConfig(origin="PAR", destination="JFK", label="Paris - New York (JFK)", budget_eur=300),
    RouteConfig(origin="PAR", destination="LAX", label="Paris - Los Angeles", budget_eur=300),
    RouteConfig(origin="PAR", destination="IAD", label="Paris - Washington (Dulles)", budget_eur=300),
    RouteConfig(origin="PAR", destination="ORD", label="Paris - Chicago", budget_eur=300),
]

# Fenetre de recherche : de aujourd'hui + SEARCH_WINDOW_START_DAYS jusqu'a
# aujourd'hui + SEARCH_WINDOW_MONTHS mois (approxime a 30 jours/mois),
# balayee par pas de DEPARTURE_STEP_DAYS jours sur la date de depart.
SEARCH_WINDOW_START_DAYS = 14
SEARCH_WINDOW_MONTHS = 9
DEPARTURE_STEP_DAYS = 7

# Duree de sejour, de STAY_MIN_NIGHTS a STAY_MAX_NIGHTS nuits par pas de
# STAY_STEP_DAYS jours (-> 14 et 21 nuits).
STAY_MIN_NIGHTS = 14
STAY_MAX_NIGHTS = 21
STAY_STEP_DAYS = 7

# Ne re-alerter que si le prix baisse d'au moins ce montant vs le dernier prix
# vu pour le meme couple destination/date de depart/duree.
MIN_PRICE_DROP_EUR = 5

# Cadence du recap en jours, mesuree depuis state["last_digest_date"] (pas un
# jour de semaine fixe).
DIGEST_INTERVAL_DAYS = 14

STATE_FILE = "data/state.json"

# Budget d'appels SerpAPI par execution (source optionnelle, desactivee par
# defaut). Reparti entre les combinaisons route x duree scannees dans un run.
SERPAPI_MAX_CALLS_PER_RUN = 20
