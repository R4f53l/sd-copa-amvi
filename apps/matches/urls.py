from django.urls import path

from apps.matches import views

app_name = "matches"

urlpatterns = [
    path("", views.public_match_list, name="list"),
]
