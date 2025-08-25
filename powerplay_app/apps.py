# file: powerplay_app/apps.py
"""App configuration for the Powerplay application.

This module defines :class:`PowerplayAppConfig`, the Django ``AppConfig`` that
registers the app and configures default model primary keys.

Key points:
    * ``name`` is fixed to ``"powerplay_app"`` to keep the app label and import
      paths stable.
    * ``default_auto_field`` is set to ``BigAutoField`` for models without an
      explicit primary key field.

No side effects are executed on import (e.g., no signal registration); the
configuration is intentionally minimal.
"""

from __future__ import annotations

from django.apps import AppConfig


# --- AppConfig -------------------------------------------------------------

class PowerplayAppConfig(AppConfig):
    """App registration and defaults for ``powerplay_app``.

    This ``AppConfig`` is discovered by Django and used to initialize the
    application. It does not override ``ready()`` and performs no implicit
    runtime hooks.
    """

    default_auto_field: str = "django.db.models.BigAutoField"
    name: str = "powerplay_app"
