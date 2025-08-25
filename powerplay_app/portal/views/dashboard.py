# file: powerplay_app/portal/views/dashboard.py
"""Portal dashboard view for authenticated users.

Exposes :class:`DashboardView`, a login-protected template view that renders
``portal/dashboard.html``. The view injects a single context key ``current``
with value ``"dashboard"`` used by the navigation to highlight the active
item. No database queries or side effects are performed; it serves as a
lightweight landing page.

Internal documentation is in English; user-facing strings remain Czech.
"""

from __future__ import annotations

from typing import Any

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView


class DashboardView(LoginRequiredMixin, TemplateView):
    """Dashboard page for logged-in users."""

    template_name: str = "portal/dashboard.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:  # override
        """Build minimal context required by the dashboard template.

        Returns:
            Template context with ``current`` set to ``"dashboard"`` for
            active navigation highlighting.
        """
        ctx = super().get_context_data(**kwargs)
        ctx["current"] = "dashboard"
        return ctx
