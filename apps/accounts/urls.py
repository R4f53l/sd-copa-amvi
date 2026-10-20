from django.contrib.auth import views as auth_views
from django.urls import path

app_name = "accounts"

# Server-rendered pages (Django templates). API routes live in api/urls.py.
# Minimal session login so the back-office pages can require
# authentication. Password recovery is still to be added here.
urlpatterns = [
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
