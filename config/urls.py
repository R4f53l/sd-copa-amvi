from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

# REST API for external systems. The website itself uses the web routes.
api_v1 = [
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain"),
    path(
        "auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"
    ),
    path("accounts/", include("apps.accounts.api.urls")),
    path("teams/", include("apps.teams.api.urls")),
    path("championships/", include("apps.championships.api.urls")),
    path("matches/", include("apps.matches.api.urls")),
]

# Server-rendered website (public portal and table official panel).
web = [
    path("accounts/", include("apps.accounts.urls")),
    path("teams/", include("apps.teams.urls")),
    path("championships/", include("apps.championships.urls")),
    path("matches/", include("apps.matches.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),
    path("api/v1/", include(api_v1)),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
    path("", include(web)),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
    )
