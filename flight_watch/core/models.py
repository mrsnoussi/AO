from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from urllib.parse import quote


@dataclass(frozen=True)
class Offer:
    """Une offre de vol aller-retour normalisee, quelle que soit sa source."""

    origin: str
    destination: str
    depart_date: date
    return_date: date
    nights: int
    price_eur: float
    airlines: tuple[str, ...]
    stops_outbound: int
    stops_return: int
    duration_outbound_minutes: int | None
    duration_return_minutes: int | None
    source: str
    fetched_at: datetime

    @property
    def pair_key(self) -> tuple[str, str, int]:
        """Cle d'unicite pour la fusion/dedoublonnage et le suivi d'etat."""
        return (self.destination, self.depart_date.isoformat(), self.nights)

    @property
    def google_flights_link(self) -> str:
        query = (
            f"Flights from {self.origin} to {self.destination} "
            f"on {self.depart_date.isoformat()} through {self.return_date.isoformat()}"
        )
        return f"https://www.google.com/travel/flights?q={quote(query)}"

    @property
    def airlines_label(self) -> str:
        return ", ".join(self.airlines) if self.airlines else "?"

    @property
    def stops_label(self) -> str:
        return f"{self.stops_outbound} aller / {self.stops_return} retour"

    @property
    def duration_label(self) -> str:
        def fmt(minutes: int | None) -> str:
            if minutes is None:
                return "?"
            hours, mins = divmod(int(minutes), 60)
            return f"{hours}h{mins:02d}"

        return f"{fmt(self.duration_outbound_minutes)} aller / {fmt(self.duration_return_minutes)} retour"
