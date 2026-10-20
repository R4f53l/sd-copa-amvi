from django.urls import path

from . import views

app_name = "championships"

# rotas web para campeonatos, inscricao de times e elenco de jogadores
urlpatterns = [
    path("", views.ChampionshipListView.as_view(), name="list"),
    path("new/", views.ChampionshipCreateView.as_view(), name="create"),
    path("<uuid:pk>/", views.ChampionshipDetailView.as_view(), name="detail"),
    path(
        "<uuid:pk>/edit/",
        views.ChampionshipUpdateView.as_view(),
        name="update",
    ),
    path(
        "<uuid:pk>/teams/",
        views.ChampionshipTeamsView.as_view(),
        name="teams",
    ),
    path(
        "<uuid:pk>/teams/<uuid:entry_pk>/players/",
        views.TeamRosterView.as_view(),
        name="roster",
    ),
    path(
        "<uuid:pk>/teams/<uuid:entry_pk>/players/<uuid:reg_pk>/edit/",
        views.PlayerRegistrationUpdateView.as_view(),
        name="registration_update",
    ),
]
