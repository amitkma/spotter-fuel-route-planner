"""URL configuration for the Spotter project."""

# Django imports
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("", include("spotter.urls")),
    path("admin/", admin.site.urls, name="admin"),
]

admin.site.site_header = "Spotter Administration"
admin.site.site_title = "Spotter Site Admin"
