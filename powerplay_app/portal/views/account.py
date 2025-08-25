# file: powerplay_app/site/views/account.py
"""Account/profile portal view combining profile and password flows.

Renders a single account page with both the profile form and the password
change form. POST handling is routed by a hidden ``action`` field with values
``"profile"`` or ``"password"``. The view keeps the user authenticated after a
successful password change to avoid unexpected logout.

UI labels remain Czech; internal documentation is English.
"""

from __future__ import annotations

from typing import Any

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.views.generic import TemplateView

from ..forms import ProfileForm


class AccountView(LoginRequiredMixin, TemplateView):
    """Account and password management page for authenticated users.

    Displays two forms on one page and distinguishes POST handling via the
    hidden ``action`` field.
    """

    template_name: str = "portal/account.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        """Build context with both forms prefilled for the current user.

        Args:
            **kwargs: Extra context kwargs passed by Django.

        Returns:
            Template context including ``profile_form``, ``password_form``, and
            the current menu marker.
        """
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ctx.update(
            {
                "profile_form": ProfileForm(instance=user),
                "password_form": PasswordChangeForm(user=user),
                "current": "account",
            }
        )
        return ctx

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        """Process profile or password submission based on ``action`` value.

        Keeps the session authenticated after a successful password change to
        prevent unexpected logout.

        Args:
            request: Current HTTP request.
            *args: Unused positional arguments.
            **kwargs: Unused keyword arguments.

        Returns:
            Redirect back to the account page or a rendered response with form
            errors.
        """
        user = request.user
        action = request.POST.get("action")

        if action == "profile":
            profile_form = ProfileForm(request.POST, instance=user)
            password_form = PasswordChangeForm(user=user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, "E‑mail byl uložen.")
                return redirect("portal:account")
            else:
                messages.error(request, "Zkontroluj prosím formulář.")
                return self.render_to_response(
                    {
                        "profile_form": profile_form,
                        "password_form": password_form,
                        "current": "account",
                    }
                )

        if action == "password":
            profile_form = ProfileForm(instance=user)
            password_form = PasswordChangeForm(user=user, data=request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)  # avoid logout after password change
                messages.success(request, "Heslo bylo změněno.")
                return redirect("portal:account")
            else:
                # Surface detailed errors in the global messages area for clarity.
                for err in password_form.non_field_errors():
                    messages.error(request, err)
                for field, errs in password_form.errors.items():
                    for err in errs:
                        messages.error(
                            request, f"{password_form.fields[field].label}: {err}"
                        )
                return self.render_to_response(
                    {
                        "profile_form": profile_form,
                        "password_form": password_form,
                        "current": "account",
                    }
                )

        return redirect("portal:account")
