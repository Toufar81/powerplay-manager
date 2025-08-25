# file: powerplay_app/views/home.py
"""Public site homepage view.

Exposes :class:`HomeView`, a lightweight template view that renders
``site/home.html`` and injects a Czech ``title`` ("Domů") into the context for
use by the layout. The view performs no database queries or side effects and
serves as the landing page for the public site.

Internal documentation is in English; user-facing strings remain Czech.
"""

from __future__ import annotations

from typing import Any

from django.views.generic import TemplateView


class HomeView(TemplateView):
    """Render the site homepage with a simple title."""

    template_name = "site/home.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:  # type: ignore[override]
        """Return template context for the homepage.

        Returns:
            Context including the Czech ``title`` key used by the layout.
        """
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Domů"
        return ctx
