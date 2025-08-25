# file: powerplay_app/services/team.py
"""Team-related service helpers.

Internal documentation is in English; user-facing strings remain Czech.
"""

from __future__ import annotations

from typing import Optional

from django.conf import settings
from powerplay_app.models import Team


def get_primary_team() -> Optional[Team]:
    """Return the *primary* team used to scope public-facing views.

    Resolution precedence:
        1. ``settings.PRIMARY_TEAM_ID`` – exact ID match.
        2. ``settings.PRIMARY_TEAM_SLUG`` – case-insensitive match against ``Team.name``.
        3. Fallback: the first team by ``id`` (if any).

    Returns:
        Optional[Team]: The resolved team instance, or ``None`` when no team
        exists in the database.
    """
    team: Optional[Team] = None

    tid = getattr(settings, "PRIMARY_TEAM_ID", None)
    slug = getattr(settings, "PRIMARY_TEAM_SLUG", None)

    if tid:
        team = Team.objects.filter(id=tid).first()

    if not team and slug:
        team = Team.objects.filter(name__iexact=slug).first()

    if not team:
        team = Team.objects.order_by("id").first()

    return team
