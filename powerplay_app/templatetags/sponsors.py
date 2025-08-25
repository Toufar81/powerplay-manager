# file: powerplay_app/templatetags/sponsors_strip.py
"""Sponsor strip inclusion tag for the public Site.

Exposes two components:

- :class:`SponsorVM` – immutable view model used by the partial to render the
  sponsor name and optional logo/URL.
- ``{% sponsors_strip %}`` – inclusion tag that supplies a list of sponsors to
  ``site/_partials/sponsors_strip.html``. Data are read from
  ``settings.POWERPLAY_SPONSORS`` when present; otherwise a small default list
  is used.

Configuration (``POWERPLAY_SPONSORS``):
    Accepts a list of items defined either as dictionaries or tuples/lists.
    Examples::

        POWERPLAY_SPONSORS = [
            {"name": "Acme Tools", "logo": "site/img/sponsors/acme.svg", "url": "https://acme.example"},
            ("Nordic Ice", "site/img/sponsors/nordic.svg", "https://nordic.example"),
        ]

    ``logo`` should be a static URL already resolvable by the frontend. No i18n
    is introduced here by design.

Usage::

    {% load sponsors_strip %}
    {% sponsors_strip %}

Internal documentation is in English; user-facing output remains Czech. Behavior
is unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, Optional

from django import template
from django.conf import settings

register = template.Library()


@dataclass(frozen=True)
class SponsorVM:
    """Immutable view model for a sponsor.

    Attributes:
        name: Sponsor display name (brand).
        logo: Optional static path to the logo (e.g., ``"site/img/sponsors/acme.svg"``).
        url: Optional external URL for the sponsor's website.
    """

    name: str
    logo: Optional[str] = None
    url: Optional[str] = None


_DEF_LIST: Final[list[SponsorVM]] = [
    SponsorVM(name="Acme Tools"),
    SponsorVM(name="Nordic Ice"),
    SponsorVM(name="PuckTech"),
    SponsorVM(name="Fit&Go"),
]


def _from_settings() -> list[SponsorVM]:
    """Build a list of sponsors from ``settings.POWERPLAY_SPONSORS``.

    Accepts items as ``dict`` (``name``, ``logo``, ``url``) or as
    ``(name, logo?, url?)`` tuples/lists. Items missing a name are ignored.
    """
    data: Any = getattr(settings, "POWERPLAY_SPONSORS", None)
    if not data:
        return []

    out: list[SponsorVM] = []
    for item in data:
        if isinstance(item, dict):
            out.append(
                SponsorVM(
                    name=item.get("name", ""),
                    logo=item.get("logo"),
                    url=item.get("url"),
                )
            )
        elif isinstance(item, (list, tuple)):
            name = item[0] if len(item) > 0 else ""
            logo = item[1] if len(item) > 1 else None
            url = item[2] if len(item) > 2 else None
            out.append(SponsorVM(name=name, logo=logo, url=url))
    return [s for s in out if s.name]


@register.inclusion_tag("site/_partials/sponsors_strip.html")
def sponsors_strip() -> dict[str, list[SponsorVM]]:
    """Provide sponsors for the ``sponsors_strip`` partial.

    Returns:
        Context mapping with key ``sponsors`` containing either the configured
        sponsors or the default list when the setting is absent or empty.
    """
    sponsors = _from_settings() or _DEF_LIST
    return {"sponsors": sponsors}
