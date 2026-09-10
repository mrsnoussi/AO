"""Interface abstraite commune a toutes les sources de prix."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from flight_watch.core.models import Offer


class ProviderError(RuntimeError):
    """Erreur definitive d'un provider. Doit toujours etre catchee par
    l'appelant : une source en echec ne doit jamais faire planter le run."""


class Provider(ABC):
    name: str

    @abstractmethod
    def search(
        self,
        origin: str,
        destination: str,
        nights: int,
        window_start: date,
        window_end: date,
    ) -> list[Offer]:
        """Retourne les offres aller-retour trouvees pour cette route et cette
        duree de sejour, avec une date de depart dans [window_start, window_end].

        Doit lever ProviderError apres epuisement des retries plutot que de
        laisser fuiter une exception non geree.
        """
        raise NotImplementedError
