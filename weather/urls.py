## @file urls.py
#  @brief URL routing for the weather application.
#
#  Maps URL patterns to view functions defined in weather.views.
#  All routes are included under the project root by weatherview_project.urls.
#
#  @author Jari Jankkila
#  @date 2026

from django.urls import path

from . import views

urlpatterns = [  ##< URL patterns for the weather app: index, station list, station data, settings.
    path('', views.index, name='index'),
    path('api/stations/', views.api_stations, name='api_stations'),
    path('api/station/<int:station_id>/', views.api_station_data, name='api_station_data'),
    path('api/station-history/<int:station_id>/', views.api_station_history, name='api_station_history'),
    path('api/settings/', views.api_settings_get, name='api_settings_get'),
    path('api/settings/save/', views.api_settings_save, name='api_settings_save'),
    path('api/nearest-station/', views.api_nearest_station, name='api_nearest_station'),
]
