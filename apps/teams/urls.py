from django.urls import path

from . import views

app_name = "teams"

# rotas web para cadastros de times, jogadores, estadios e cidades
urlpatterns = [
    path("", views.TeamListView.as_view(), name="team_list"),
    path("new/", views.TeamCreateView.as_view(), name="team_create"),
    path(
        "<uuid:pk>/edit/",
        views.TeamUpdateView.as_view(),
        name="team_update",
    ),
    path("players/", views.PlayerListView.as_view(), name="player_list"),
    path(
        "players/new/",
        views.PlayerCreateView.as_view(),
        name="player_create",
    ),
    path(
        "players/<uuid:pk>/edit/",
        views.PlayerUpdateView.as_view(),
        name="player_update",
    ),
    path("stadiums/", views.StadiumListView.as_view(), name="stadium_list"),
    path(
        "stadiums/new/",
        views.StadiumCreateView.as_view(),
        name="stadium_create",
    ),
    path(
        "stadiums/<uuid:pk>/edit/",
        views.StadiumUpdateView.as_view(),
        name="stadium_update",
    ),
    path("cities/", views.CityListView.as_view(), name="city_list"),
    path("cities/new/", views.CityCreateView.as_view(), name="city_create"),
    path(
        "cities/<int:pk>/edit/",
        views.CityUpdateView.as_view(),
        name="city_update",
    ),
]
