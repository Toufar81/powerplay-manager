# file: powerplay_app/auth/backends.py
from __future__ import annotations

"""Custom authentication backend: username **or** email (case-insensitive).

Usage:
    In Django settings, enable the backend (preferably before ModelBackend):

        AUTHENTICATION_BACKENDS = [
            "powerplay_app.auth.backends.UsernameOrEmailBackend",
            "django.contrib.auth.backends.ModelBackend",
        ]

Notes:
    - Internal documentation is English.
    - No user-facing strings are introduced here.
    - Email is matched case-insensitively; the first match wins if duplicates exist.
      If you rely on email login, consider enforcing unique emails at the DB level.
"""

from typing import Any, Optional

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.base_user import AbstractBaseUser
from django.db.models import Q

UserModel = get_user_model()


def _normalize_login(value: str) -> str:
    """Return a normalized login identifier.

    Currently trims surrounding whitespace. Case-insensitivity is handled in the
    ORM query via `__iexact`.
    """

    return value.strip()


class UsernameOrEmailBackend(ModelBackend):
    """Authenticate against username **or** email.

    The lookup is performed using a case-insensitive filter on either
    `username` or `email`. The first matching user (ordered by primary key) is
    selected to avoid multiple DB hits.

    Security:
        - `user_can_authenticate()` is respected (e.g. blocks inactive users).
        - The same timing/profile as `ModelBackend` is preserved reasonably.

    Compatibility:
        - Signature matches Django's `ModelBackend.authenticate` method.
        - Works with custom user models as long as they expose `username` and
          `email` fields compatible with the query below.
    """

    def authenticate(
        self,
        request: Any,
        username: Optional[str] = None,
        password: Optional[str] = None,
        **kwargs: Any,
    ) -> Optional[AbstractBaseUser]:  # type: ignore[override]
        """Return an authenticated user or ``None``.

        Args:
            request: The current request (may be ``None`` in some auth flows).
            username: The login identifier; may be a username **or** an email.
            password: The raw password to check.
            **kwargs: May contain ``email`` if the client posts that field.

        Returns:
            The authenticated user instance if credentials are valid, otherwise
            ``None``.
        """

        # Accept either `username` or explicit `email` kw, mirroring common UIs.
        login_value: Optional[str] = username or kwargs.get("email")
        if login_value is None or password is None:
            return None

        login_value = _normalize_login(login_value)

        try:
            # Use default manager in case a custom manager changes visibility.
            user = (
                UserModel._default_manager  # type: ignore[attr-defined]
                .filter(Q(username__iexact=login_value) | Q(email__iexact=login_value))
                .order_by("id")
                .first()
            )
            if not user:
                return None

            if user.check_password(password) and self.user_can_authenticate(user):
                return user
        except Exception:
            # Be conservative: never leak errors from auth flow.
            return None

        return None
