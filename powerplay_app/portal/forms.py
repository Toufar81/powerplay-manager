# file: powerplay_app/portal/forms.py
"""Portal forms for account/profile and lightweight feedback.

Internal documentation is **English**; all user-facing labels stay **Czech**.
Behavior is preserved 1:1. Forms are used inside the authenticated portal.

Highlights
---------
- `ProfileForm` updates only the e‑mail field; names are read-only.
- `FeedbackForm` offers an optional target (event or game) limited to ±30 days
  around *now* and exposes the selected window via `._range_start/_range_end`.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, TYPE_CHECKING

from django import forms
from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone

from powerplay_app.models.feedback import GameFeedback
from powerplay_app.models.games import Game
from powerplay_app.models import TeamEvent

if TYPE_CHECKING:  # for type hints only; avoids runtime import coupling
    from powerplay_app.models import Team


class ProfileForm(forms.ModelForm):
    """Allow a user to update their e‑mail address.

    Notes:
        - First/last name are displayed as disabled & read-only; they are not
          meant to be edited via this portal screen.
        - Unique e‑mail constraint is enforced case-insensitively.
    """

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "inp", "placeholder": "Jméno"}),
            "last_name": forms.TextInput(attrs={"class": "inp", "placeholder": "Příjmení"}),
            "email": forms.EmailInput(attrs={"class": "inp", "placeholder": "e-mail"}),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        super().__init__(*args, **kwargs)
        # keep names visible but not editable in the portal
        for f in ("first_name", "last_name"):
            self.fields[f].disabled = True
            self.fields[f].widget.attrs["readonly"] = True

    def clean_email(self) -> str:
        """Validate that the e‑mail is unique (case-insensitive).

        Returns:
            The normalized e‑mail value (or an empty string if cleared).

        Raises:
            forms.ValidationError: If the e‑mail belongs to a different user.
        """
        email = (self.cleaned_data.get("email") or "").strip()
        if not email:
            return email
        exists = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists()
        if exists:
            raise forms.ValidationError("Tento e-mail už používá jiný účet.")
        return email

    def save(self, commit: bool = True) -> User:  # type: ignore[override]
        """Persist only the e‑mail change for the bound ``User`` instance.

        Why: Names are intentionally read-only in this view.
        """
        instance: User = self.instance
        email = self.cleaned_data.get("email")
        if email is not None:
            instance.email = email
            if commit:
                instance.save(update_fields=["email"])
        return instance


class FeedbackForm(forms.ModelForm):
    """Lightweight feedback form with an optional target association.

    The synthetic ``target`` choice offers two opt-groups:
        - "Události (±30 dní)": team-bound events within the window.
        - "Zápasy (±30 dní)": games (home/away) within the window.

    Choice values are encoded as ``E:<id>`` or ``G:<id>`` and are later parsed
    by the view to assign ``related_event`` or ``related_game`` on save.

    Attributes set on instances:
        _range_start: ``timezone-aware datetime`` – start of the window.
        _range_end:   ``timezone-aware datetime`` – end of the window.
    """

    target = forms.ChoiceField(
        label="Cíl (událost / zápas, nepovinné)",
        required=False,
        choices=[("", "— vyber událost nebo zápas —")],
    )

    class Meta:
        model = GameFeedback
        fields = ("subject", "message")  # related_* resolved from `target` in view
        widgets = {
            "subject": forms.TextInput(attrs={"placeholder": "Předmět (volitelné)"}),
            "message": forms.Textarea(attrs={"rows": 4, "placeholder": "Napiš připomínku…"}),
        }

    def __init__(self, *args: Any, team: Team | None = None, **kwargs: Any) -> None:  # type: ignore[override]
        super().__init__(*args, **kwargs)

        now = timezone.now()
        start = now - timedelta(days=30)
        end = now + timedelta(days=30)

        # --- Team events in ±30 days (ascending) ---
        ev_qs = TeamEvent.objects.none()
        if team:
            ev_qs = (
                TeamEvent.objects
                .filter(team=team, starts_at__gte=start, starts_at__lte=end)
                .select_related("stadium")
                .order_by("starts_at", "id")
            )

        # --- Games in ±30 days (ascending) ---
        g_qs = Game.objects.none()
        if team:
            g_qs = (
                Game.objects
                .filter(Q(home_team=team) | Q(away_team=team), starts_at__gte=start, starts_at__lte=end)
                .select_related("home_team", "away_team", "stadium")
                .order_by("starts_at", "id")
            )

        # Build choices with opt-groups, keep Czech labels
        ev_choices = [
            (
                f"E:{e.id}",
                f"{e.starts_at:%Y-%m-%d %H:%M} • {e.get_event_type_display()} — {e.title or '—'}"
                + (f" • {e.stadium.name}" if e.stadium_id else ""),
            )
            for e in ev_qs
        ]
        g_choices = [
            (
                f"G:{g.id}",
                f"{g.starts_at:%Y-%m-%d %H:%M} • {g.home_team.name} vs {g.away_team.name}"
                + (f" • {g.stadium.name}" if g.stadium_id else ""),
            )
            for g in g_qs
        ]

        self.fields["target"].choices = [
            ("", "— vyber událost nebo zápas —"),
            ("Události (±30 dní)", ev_choices),
            ("Zápasy (±30 dní)", g_choices),
        ]

        # Expose the time window for the template (informational)
        self._range_start = start
        self._range_end = end
