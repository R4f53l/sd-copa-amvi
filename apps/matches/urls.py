from django.urls import path

from . import views

app_name = "matches"

urlpatterns = [
    path("", views.MatchListView.as_view(), name="list"),
    path("stats/", views.StatisticsView.as_view(), name="stats"),
    path(
        "new/<uuid:championship_pk>/",
        views.MatchCreateView.as_view(),
        name="create",
    ),
    path("<uuid:pk>/edit/", views.MatchUpdateView.as_view(), name="update"),
    path("<uuid:pk>/sheet/", views.MatchSheetView.as_view(), name="sheet"),
    path("<uuid:pk>/live/", views.MatchLiveView.as_view(), name="live"),
    path(
        "<uuid:pk>/lineup/<str:side>/",
        views.LineupView.as_view(),
        name="lineup",
    ),
    path(
        "<uuid:pk>/events/<uuid:event_pk>/cancel/",
        views.EventCancelView.as_view(),
        name="event_cancel",
    ),
]
