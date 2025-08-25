# file: powerplay_app/views/players.py
"""Players listing and detail views for the public Site.

Provides :class:`PlayersListView` for listing players of the *primary* team
with optional position filtering and per-position counts, and
:class:`PlayerDetailView` for showing a single player's details including a
computed age. The primary team is resolved via
:func:`powerplay_app.context._resolve_primary_team`.

Listing flow:
    - Read optional ``?pos=<forward|defense|goalie>`` filter.
    - Build a team-scoped base queryset ordered by jersey number and last name.
    - Apply position filter when present and compute counts per position via
      ``values('position').annotate(Count('id'))`` for badge rendering.
    - Expose a prepared ``pos_list`` with Czech labels for the UI.

Detail flow:
    - Compute ``age`` from ``player.birth_date`` using the local helper
      :func:`_age` and inject it into the template context.

Docstrings and internal comments are English; UI labels remain Czech. Behavior
is unchanged.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Final

from django.db.models import Count
from django.views.generic import DetailView, TemplateView

from powerplay_app.context import _resolve_primary_team
from powerplay_app.models import Player


# Czech UI labels by position value
POS_LABELS: Final[dict[str, str]] = {
    "forward": "Útočníci",
    "defense": "Obránci",
    "goalie": "Brankáři",
}


def _age(born: date | None) -> int | None:
    """Return age in years for a given birth date or ``None`` when unknown."""
    # Why: Age is a common convenience on the player detail page; returning
    # None lets the template hide the field gracefully.
    if not born:
        return None
    today = date.today()
    years = today.year - born.year - (
        (today.month, today.day) < (born.month, born.day)
    )
    return years


class PlayersListView(TemplateView):
    """Render a list of players for the primary team with position filters.

    Context keys:
        - ``players``: queryset of players (optionally filtered by position).
        - ``pos_labels``: mapping of position value to Czech label.
        - ``pos_counts``: counts per position for filter badges.
        - ``pos_list``: list of dicts ``{"key", "label", "count"}`` for UI.
        - ``selected_pos``: selected position value or ``None``.
        - ``total_count``: total number of players on the team.
    """

    template_name = "site/players.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:  # type: ignore[override]
        """Build listing context with optional position filtering and counts."""
        ctx = super().get_context_data(**kwargs)
        team = _resolve_primary_team()
        selected = self.request.GET.get("pos")

        qs = Player.objects.none()
        pos_counts: dict[str, int] = {}
        total_count = 0

        if team:
            base = Player.objects.filter(team=team)
            qs = base.order_by("jersey_number", "last_name")
            if selected in POS_LABELS:
                qs = qs.filter(position=selected)

            # counts for filter badges
            counts = base.values("position").annotate(c=Count("id"))
            pos_counts = {row["position"]: row["c"] for row in counts}
            total_count = base.count()

        # precomputed list for template (label + count)
        pos_list = [
            {"key": key, "label": label, "count": pos_counts.get(key, 0)}
            for key, label in POS_LABELS.items()
        ]

        ctx.update(
            {
                "players": qs,
                "pos_labels": POS_LABELS,
                "pos_counts": pos_counts,
                "pos_list": pos_list,
                "selected_pos": selected if selected in POS_LABELS else None,
                "total_count": total_count,
            }
        )
        return ctx


class PlayerDetailView(DetailView):
    """Player detail view with computed age in the context."""

    model = Player
    template_name = "site/player_detail.html"
    context_object_name = "player"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:  # type: ignore[override]
        """Attach computed ``age`` for display alongside player details."""
        ctx = super().get_context_data(**kwargs)
        p: Player = ctx["player"]
        ctx.update({
            "age": _age(getattr(p, "birth_date", None)),
        })
        return ctx
