## @file urls.py
#  @brief Top-level URL configuration for the weatherview_project Django project.
#
#  Delegates all URL matching to the weather application's own url module.
#
#  @author Jari Jankkila
#  @date 2026

from django.urls import path, include
from django.views.generic.base import RedirectView

urlpatterns = [  ##< Top-level URL patterns. All traffic is delegated to the weather app.
    path('', include('weather.urls')),
    path('favicon.ico', RedirectView.as_view(url='/static/weather/favicon.svg', permanent=True)),
]
