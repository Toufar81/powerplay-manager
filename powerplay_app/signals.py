# file: powerplay_app/signals.py
"""Signal handlers for score recomputation and calendar-event synchronization.

This module wires Django model signals to two domain behaviors:

* Recompute derived game statistics whenever a :class:`Goal` or
  :class:`Penalty` is created, updated, or deleted.
* Keep a one-to-one :class:`TeamEvent` synchronized for each :class:`Game`:
  create/update it after saves and remove it after deletes.

All user-facing text remains **Czech**; internal documentation is in English.
"""

from __future__ import annotations

from typing import Any

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Game, Goal, Penalty, TeamEvent
from powerplay_app.services.stats import recompute_game
from .models.games import LineAssignment
from django.db import transaction



# --- Score recomputation triggers (Goal/Penalty) ---------------------------


@receiver(post_save, sender=Goal)
@receiver(post_delete, sender=Goal)
@receiver(post_save, sender=Penalty)
@receiver(post_delete, sender=Penalty)
def _events_changed(sender: type[Any], instance: Goal | Penalty, **kwargs: Any) -> None:
    """Recompute game scores/statistics when a goal or penalty changes.

    Args:
        sender: Model class that emitted the signal (``Goal`` or ``Penalty``).
        instance: The saved or deleted instance.
        **kwargs: Additional signal arguments (unused).

    Why:
        Maintains consistency of derived statistics after atomic edits from
        admin/API without requiring manual recomputation.
    """
    recompute_game(instance.game)


# --- Calendar event helpers -----------------------------------------------


def _event_title_for(game: Game) -> str:
    """Build a localized title for a game-backed calendar event.

    The prefix reflects competition type (Liga/Turnaj/Přátelský) when present.

    Args:
        game: Game instance to render the title for.

    Returns:
        Czech title, e.g. ``"Liga NHL 2025/2026 – Zápas: Home vs Away"``.
    """
    prefix = "Zápas"
    if getattr(game, "competition", None) == "league" and getattr(game, "league", None):
        prefix = f"Liga {game.league}"
    elif getattr(game, "competition", None) == "tournament" and getattr(game, "tournament", None):
        prefix = f"Turnaj {game.tournament.name}"
    elif getattr(game, "competition", None) == "friendly":
        prefix = "Přátelský"
    return f"{prefix} – Zápas: {game.home_team.name} vs {game.away_team.name}"


def _sync_event_for_game(game: Game, *, create_if_missing: bool = True) -> None:
    """Ensure there is exactly one ``TeamEvent`` per game (``team=None``).

    If the event exists, update key fields to mirror the game; otherwise create
    it when ``create_if_missing`` is ``True``.

    Args:
        game: ``Game`` to synchronize with a calendar event.
        create_if_missing: Whether to create the event if none exists.
    """
    ev, created = TeamEvent.objects.get_or_create(
        related_game=game,
        defaults=dict(
            team=None,
            event_type=TeamEvent.EventType.GAME,
            title=_event_title_for(game),
            starts_at=game.starts_at,
            ends_at=game.starts_at,
            stadium=game.stadium,
            source=TeamEvent.Source.GAME,
            auto_synced=True,
        ),
    )

    if not created:
        changed = False
        desired = {
            "title": _event_title_for(game),
            "starts_at": game.starts_at,
            "ends_at": game.starts_at,
            "stadium": game.stadium,
            "event_type": TeamEvent.EventType.GAME,
            "source": TeamEvent.Source.GAME,
            "auto_synced": True,
        }
        for k, v in desired.items():
            if getattr(ev, k) != v:
                setattr(ev, k, v)
                changed = True
        if changed:
            ev.save(update_fields=list(desired.keys()))


# --- Calendar event sync receivers (Game) ----------------------------------


@receiver(post_save, sender=Game)
def _game_saved_sync_event(sender: type[Game], instance: Game, created: bool, **kwargs: Any) -> None:
    """
    Po uložení hry:
      - udrž kalendářovou událost v synchronu (beze změny chování),
      - a pokud jde o nový zápas nebo se měnilo skóre, přepočítej statistiky.

    Používáme transaction.on_commit, aby se přepočet spustil až po dopsání
    všech změn do DB (bezpečné i vůči inline formulářům, API apod.).
    """
    # (původní chování – sync kalendáře)
    _sync_event_for_game(instance, create_if_missing=True)

    # Rozhodnutí: přepočítat při vytvoření hry nebo při změně skóre.
    update_fields = kwargs.get("update_fields")
    score_changed = (
        update_fields is None  # save() bez update_fields – bereme jako „možná změna“
        or "score_home" in update_fields
        or "score_away" in update_fields
        or created
    )

    if score_changed:
        transaction.on_commit(lambda: recompute_game(instance))




@receiver(post_delete, sender=Game)
def _game_deleted_remove_event(sender: type[Game], instance: Game, **kwargs: Any) -> None:
    """Remove the related calendar event after a game is deleted."""
    TeamEvent.objects.filter(related_game=instance).delete()


@receiver(post_save, sender=LineAssignment)
@receiver(post_delete, sender=LineAssignment)
def _lineup_changed(sender, instance: LineAssignment, **kwargs: Any) -> None:
    """
    Po změně sestavy přepočítáme zápas – důležité hlavně pro GA gólmanů.
    """
    try:
        recompute_game(instance.line.game)
    except Exception:
        pass