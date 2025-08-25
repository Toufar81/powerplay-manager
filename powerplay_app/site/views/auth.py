# file: powerplay_app/site/auth.py
"""Authentication for the public *Site* section.

Exposes a custom authentication form that accepts either username or e‑mail and
simple login/logout views tailored for the Site → Portal flow:

- :class:`EmailOrUsernameAuthenticationForm` – if the input contains ``@``,
  resolves the canonical username by e‑mail and delegates to Django's default
  validation; unknown e‑mails fall back to standard error handling.
- :class:`SiteLoginView` – uses the custom form, skips the form for already
  authenticated users, and always redirects to the Portal dashboard after
  success (``?next=`` is ignored by design).
- :class:`SiteLogoutView` – POST-only logout with a redirect to the Site home.

Internal documentation is in English; user-facing labels remain Czech.
"""

from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse


class EmailOrUsernameAuthenticationForm(AuthenticationForm):
    """Accept either username **or** e‑mail in the username field.

    Why:
        Many users attempt to log in with their e‑mail address. If an "@" is
        present, we resolve the username by e‑mail and continue with the
        standard authentication pipeline.

    Notes:
        - No error is raised when the e‑mail is unknown—Django's default
          validation handles incorrect credentials uniformly.
        - E‑mail uniqueness is not enforced here; first exact match wins to
          keep current app assumptions intact.
    """

    def clean(self) -> dict[str, Any]:  # type: ignore[override]
        username = self.cleaned_data.get("username")
        if username and "@" in username:
            User = get_user_model()
            try:
                user = User.objects.get(email__iexact=username)
                # Replace with canonical username so parent ``clean`` works.
                self.cleaned_data["username"] = user.get_username()
            except User.DoesNotExist:
                # Fall through to default validation (uniform error message).
                pass
        return super().clean()


class SiteLoginView(LoginView):
    """Public-site login using the custom form; always redirect to Portal.

    Behavior:
        - Uses :class:`EmailOrUsernameAuthenticationForm`.
        - ``redirect_authenticated_user = True`` to skip the form when already
          logged in.
        - Ignores any ``?next=`` param and consistently goes to Portal dashboard.
    """

    template_name = "site/auth/login.html"
    form_class = EmailOrUsernameAuthenticationForm
    redirect_authenticated_user = True

    def get_success_url(self) -> str:  # type: ignore[override]
        """After successful login, go to the Portal dashboard.

        Why:
            Portal is the primary destination for logged-in users in this app.
        """
        return reverse("portal:dashboard")


class SiteLogoutView(LogoutView):
    """Logout endpoint constrained to POST with a simple redirect to Home."""

    http_method_names = ["post"]  # POST-only to avoid CSRF via GET
    next_page = "site:home"       # Named URL; Django resolves to absolute URL
