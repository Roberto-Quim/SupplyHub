from django.urls import path

from . import views

app_name = "supplyhub"

urlpatterns = [
    path("", views.hub_index, name="hub_index"),
]
