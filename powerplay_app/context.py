# powerplay_app/context.py
"""Context helpers for injecting the primary team into templates.

Internal documentation is in English; all user-facing strings stay in Czech.
Behavior is preserved. Only docstrings, type hints, and light formatting were
added.

Notes:
    - ``_resolve_primary_team`` uses settings-driven resolution order and is
      cached with ``lru_cache(maxsize=1)`` for efficiency. Call
      ``_resolve_primary_team.cache_clear()`` after data changes (e.g., when the
      primary team is updated) to refresh the value within the running process.
    - ``select_related("league")`` is used to avoid extra queries in templates
      that display the league name.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from django.conf import settings

from .models import Team


@lru_cache(maxsize=1)
def _resolve_primary_team() -> Team | None:
    """Return the app's *primary team* according to settings.

    Resolution order:
        1. If ``settings.PRIMARY_TEAM_ID`` is set, return that team.
        2. Else if ``settings.PRIMARY_TEAM_NAME`` is set, perform a
           case-insensitive name match.
        3. Otherwise, return the first team in the database (lowest ``id``) as
           a safe fallback so pages can render something.

    Returns:
        Team | None: The resolved team, or ``None`` if the database is empty.

    Why:
        Keeps template logic simple, while centralizing the resolution and
        making it easily cacheable. Cache invalidation is manual via
        ``_resolve_primary_team.cache_clear()`` when necessary.
    """

    team_id = getattr(settings, "PRIMARY_TEAM_ID", None)
    team_name = getattr(settings, "PRIMARY_TEAM_NAME", None)

    qs = Team.objects.select_related("league")

    if team_id:
        return qs.filter(id=team_id).first()

    if team_name:
        # Loose match by name (can be swapped to slug if available).
        return qs.filter(name__iexact=team_name).first()

    # Fallback – first team in DB (ensures something renders)
    return qs.order_by("id").first()


def primary_team(request: Any) -> dict[str, Team | None]:
    """Django context processor that exposes the primary team.

    Args:
        request: The current HTTP request (unused).

    Returns:
        dict[str, Team | None]: Mapping with a single key ``"primary_team"``
        used by templates.

    Why:
        Making the primary team globally available avoids repetitive lookups in
        individual views and template tags.
    """

    return {"primary_team": _resolve_primary_team()}
