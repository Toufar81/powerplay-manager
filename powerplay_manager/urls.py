# file: powerplay_manager/urls.py
"""Project URL configuration for ``powerplay_manager``.

Routes:
* Django admin, Django JET (admin & dashboard), and ``nested_admin`` helpers.
* Public site at root (``powerplay_app.site.urls``).
* Internal portal under ``/portal/`` (``powerplay_app.portal.urls``).
* Media files served by Django only when ``DEBUG`` is ``True``.

Internal documentation is English; user-facing strings are handled in views/templates.
"""

from __future__ import annotations

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import URLPattern, URLResolver, include, path

# --- URL patterns ----------------------------------------------------------

urlpatterns: list[URLPattern | URLResolver] = [
    path("jet/", include("jet.urls", "jet")),
    path("jet/dashboard/", include("jet.dashboard.urls", "jet-dashboard")),
    path("_nested_admin/", include("nested_admin.urls")),
    path("admin/", admin.site.urls),
    path("", include("powerplay_app.site.urls")),        # public site
    path("portal/", include("powerplay_app.portal.urls")),  # internal portal
]

# Media files (development only)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
