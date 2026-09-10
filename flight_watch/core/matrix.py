"""Construction de la grille de recherche (fenetre de dates, durees de sejour)."""
from __future__ import annotations

from datetime import date, timedelta

from flight_watch import config


def stay_durations() -> list[int]:
    """Durees de sejour a tester, en nuits (14 puis 21)."""
    durations = []
    nights = config.STAY_MIN_NIGHTS
    while nights <= config.STAY_MAX_NIGHTS:
        durations.append(nights)
        nights += config.STAY_STEP_DAYS
    return durations


def search_window(today: date) -> tuple[date, date]:
    """Fenetre de dates de depart valides : [today+14j, today+9mois]."""
    start = today + timedelta(days=config.SEARCH_WINDOW_START_DAYS)
    end = today + timedelta(days=config.SEARCH_WINDOW_MONTHS * 30)
    return start, end


def departure_dates(window_start: date, window_end: date) -> list[date]:
    """Grille de dates de depart, par pas de DEPARTURE_STEP_DAYS jours."""
    dates = []
    current = window_start
    while current <= window_end:
        dates.append(current)
        current += timedelta(days=config.DEPARTURE_STEP_DAYS)
    return dates
