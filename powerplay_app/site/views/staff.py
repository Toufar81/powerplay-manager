# file: powerplay_app/site/views/staff.py
"""Public Site views for staff listing and detail.

Exposes :class:`StaffListView` for listing **active** staff members of the
*primary* team (resolved via :func:`powerplay_app.context._resolve_primary_team`)
ordered by ``order``, ``last_name``, ``first_name``; and
:class:`StaffDetailView` for rendering a single staff member.

The list view also provides a small ``_dbg`` payload (IDs, counts) meant for
troubleshooting; it can be hidden in production templates if undesired. UI
strings remain Czech; internal documentation is English. Behavior is unchanged.
"""

from __future__ import annotations

from typing import Any

from django.views.generic import DetailView, TemplateView

from powerplay_app.context import _resolve_primary_team
from powerplay_app.models import Staff


class StaffListView(TemplateView):
    """Render the active staff members for the primary team.

    Context keys:
        - ``staff``: queryset of active staff for the primary team (ordered).
        - ``_dbg``: small debug payload (IDs, counts) for troubleshooting.
    """

    template_name = "site/staff.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:  # type: ignore[override]
        """Return context with staff filtered by the resolved primary team."""
        ctx = super().get_context_data(**kwargs)
        team = _resolve_primary_team()

        qs = Staff.objects.none()
        debug: dict[str, Any] = {}
        if team:
            qs = (
                Staff.objects
                .filter(team=team, is_active=True)
                .select_related("team")
                .order_by("order", "last_name", "first_name")
            )
            debug = {
                "team_id": team.id,
                "team_name": team.name,
                "count_team_active": Staff.objects.filter(team=team, is_active=True).count(),
                "ids": list(qs.values_list("id", flat=True)),
            }

        ctx.update({"staff": qs, "_dbg": debug})
        return ctx


class StaffDetailView(DetailView):
    """Detail page for a single staff member."""

    model = Staff
    template_name = "site/staff_detail.html"
    context_object_name = "member"
