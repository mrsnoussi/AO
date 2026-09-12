"""Helper HTTP partage : backoff exponentiel sur 429/5xx et timeouts."""
from __future__ import annotations

import logging
import time
from typing import Any, Mapping

import requests

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class RequestFailed(RuntimeError):
    """Requete HTTP definitivement en echec apres tous les retries."""


def get_with_backoff(
    url: str,
    *,
    params: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
    timeout: float = 10.0,
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> requests.Response:
    """GET avec backoff exponentiel (1s, 2s, 4s, ...) sur 429/5xx/timeouts.

    Leve RequestFailed si toutes les tentatives echouent ; toute autre erreur
    HTTP (4xx non retryable) est propagee immediatement via raise_for_status.
    """
    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=timeout)
        except requests.RequestException as exc:
            last_error = exc
            logger.warning(
                "Requete vers %s echouee (tentative %d/%d): %s", url, attempt + 1, max_retries, exc
            )
        else:
            if response.status_code == 200:
                return response
            if response.status_code not in RETRYABLE_STATUS_CODES:
                response.raise_for_status()
            last_error = RequestFailed(f"HTTP {response.status_code} depuis {url}")
            logger.warning(
                "Requete vers %s a retourne %d (tentative %d/%d)",
                url,
                response.status_code,
                attempt + 1,
                max_retries,
            )

        if attempt < max_retries - 1:
            delay = base_delay * (2**attempt)
            time.sleep(delay)

    raise RequestFailed(f"Echec definitif apres {max_retries} tentatives vers {url}") from last_error
