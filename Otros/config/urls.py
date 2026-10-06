from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from supplyhub.views import logout_view, main_login_view

urlpatterns = [
    path(settings.DJANGO_ADMIN_URL, admin.site.urls),
    path("login/", main_login_view, name="login"),
    path("logout/", logout_view, name="logout"),
    path("", include("supplyhub.urls")),
]

if getattr(settings, "GOOGLE_OAUTH_ENABLED", False):
    urlpatterns += [path("accounts/", include("allauth.urls"))]
