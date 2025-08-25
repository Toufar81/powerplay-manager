# file: powerplay_app/portal/views/feedback.py
"""Portal feedback view for listing and submitting team feedback.

Exposes :class:`FeedbackView`, a login-protected page that lists existing
:class:`~powerplay_app.models.feedback.GameFeedback` for the *primary* team and
provides a submission form. ``GET`` renders the list and form; ``POST``
validates input and creates a new feedback record linked to the primary team
and optionally to a game or a team event.

Context keys:
    - ``primary_team`` – resolved primary team used to scope queries/forms.
    - ``items`` – feedback queryset ordered by ``-created_at`` with related
      game/event data selected for display.
    - ``form`` – submission form pre-scoped by team and exposing optional
      range hints.
    - ``range_start`` / ``range_end`` – optional date bounds supplied by the
      form (if available).

Linking semantics:
    - ``target`` cleaned value encodes linkage: ``"G:<id>"`` → Game,
      ``"E:<id>"`` → TeamEvent.

The view uses Django messages for success/error UX and snapshots the author's
current display name into the model. UI strings remain Czech; internal docs are
English. Behavior is unchanged.
"""

from __future__ import annotations

from typing import Any

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.views.generic import TemplateView

from powerplay_app.context import _resolve_primary_team
from powerplay_app.models.feedback import GameFeedback
from ..forms import FeedbackForm


class FeedbackView(LoginRequiredMixin, TemplateView):
    """Portal page for feedback listing and submission."""

    template_name = "portal/feedback.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:  # type: ignore[override]
        """Assemble list and form for the primary team.

        Args:
            **kwargs: Extra context kwargs passed by Django.

        Returns:
            Template context including ``primary_team``, ``items``, ``form``,
            optional range hints, and the current menu marker.
        """
        ctx = super().get_context_data(**kwargs)
        team = _resolve_primary_team()

        qs = GameFeedback.objects.none()
        if team:
            qs = (
                GameFeedback.objects
                .filter(team=team)
                .select_related(
                    "related_game",
                    "related_game__home_team",
                    "related_game__away_team",
                    "related_event",
                    "related_event__stadium",
                )
                .order_by("-created_at")
            )

        form = FeedbackForm(team=team)
        ctx.update({
            "primary_team": team,
            "current": "feedback",
            "items": qs,
            "form": form,
            "range_start": getattr(form, "_range_start", None),
            "range_end": getattr(form, "_range_end", None),
        })
        return ctx

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        """Validate and create a feedback entry; preserve original UX.

        Args:
            request: Current HTTP request.
            *args: Unused positional arguments.
            **kwargs: Unused keyword arguments.

        Returns:
            Redirect back to the feedback page on success or team resolution
            failure, otherwise a rendered response with form errors.
        """
        team = _resolve_primary_team()
        form = FeedbackForm(request.POST, team=team)

        if not team:
            messages.error(request, "Nepodařilo se určit primární tým.")
            return redirect("portal:feedback")

        if form.is_valid():
            cd = form.cleaned_data
            obj = GameFeedback(
                team=team,
                subject=cd.get("subject") or "",
                message=cd["message"],
                created_by=request.user,
                created_by_name=(
                    f"{request.user.first_name} {request.user.last_name}".strip()
                    or request.user.get_username()
                ),
            )

            target = cd.get("target") or ""
            if target.startswith("G:"):
                obj.related_game_id = int(target.split(":", 1)[1])
            elif target.startswith("E:"):
                obj.related_event_id = int(target.split(":", 1)[1])

            obj.save()
            messages.success(request, "Připomínka byla uložena.")
            return redirect("portal:feedback")

        # invalid – re-render with form-bound errors and range hints
        ctx = self.get_context_data()
        ctx["form"] = form
        ctx["range_start"] = getattr(form, "_range_start", None)
        ctx["range_end"] = getattr(form, "_range_end", None)
        return self.render_to_response(ctx)
