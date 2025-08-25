# file: powerplay_app/views/contact.py
"""Contact page view for the public Site.

Exposes :class:`ContactView`, a template view that renders ``site/contact.html``
and lists active staff members for the *primary* team. The primary team is
resolved centrally via :func:`powerplay_app.context._resolve_primary_team` to
keep view logic consistent across the app. Staff entries are filtered by
``is_active=True`` and ordered by ``order``, ``last_name``, ``first_name``.

Internal documentation is in English; user-facing strings remain Czech.
Behavior is unchanged.
"""

from __future__ import annotations

from typing import Any

from django.views.generic import TemplateView

from powerplay_app.context import _resolve_primary_team
from powerplay_app.models import Staff


class ContactView(TemplateView):
    """Render the contact page with active staff of the primary team.

    Notes:
        - Primary team is resolved via a shared context helper to avoid
          duplicating logic and to keep scoping uniform.
        - Query uses ``select_related('team')`` for display without N+1.
    """

    template_name = "site/contact.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:  # type: ignore[override]
        """Return template context with ``team`` and its active ``staff``.

        Args:
            **kwargs: Parent template context parameters.

        Returns:
            Context mapping containing ``team`` and ``staff``.
        """
        ctx = super().get_context_data(**kwargs)

        team = _resolve_primary_team()

        staff_qs = Staff.objects.none()
        if team:
            staff_qs = (
                Staff.objects.filter(team=team, is_active=True)
                .select_related("team")
                .order_by("order", "last_name", "first_name")
            )

        ctx.update({
            "team": team,
            "staff": staff_qs,
        })
        return ctx
