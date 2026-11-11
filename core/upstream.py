import logging
import requests
from django.conf import settings

UPSTREAM_SEARCH_URL = "https://schemas.pub/api/search"

logger = logging.getLogger("schemaindex")


def should_search_upstream(is_id_value_query):
    if not getattr(settings, "UPSTREAM_API_KEY", None):
        return False
    fallback = getattr(settings, "UPSTREAM_SEARCH_FALLBACK", None)
    return fallback == "all" or (fallback == "$id" and is_id_value_query)


def search_upstream(query):
    """
    Searches public schemas on Schemas.Pub.
    Returns a list of dicts with url, id, name, and description,
    or an empty list if the request fails.
    """
    try:
        response = requests.get(
            UPSTREAM_SEARCH_URL,
            params={"query": query or ""},
            headers={"Authorization": f"Bearer {settings.UPSTREAM_API_KEY}"},
        )
        response.raise_for_status()
        return response.json()["data"]
    except (requests.exceptions.RequestException, ValueError, KeyError):
        logger.exception("Upstream search failed for query %r", query)
        return []
