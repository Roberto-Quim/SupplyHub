from django.urls import path

from . import views

app_name = "supplyhub"

urlpatterns = [
    path("", views.hub_index, name="hub_index"),
    path("ad-login/", views.active_directory_login_view, name="ad_login"),
    path("nomina-login/", views.payroll_login_view, name="payroll_login"),
]
