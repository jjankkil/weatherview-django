from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('api/stations/', views.api_stations, name='api_stations'),
    path('api/station/<int:station_id>/', views.api_station_data, name='api_station_data'),
    path('api/settings/', views.api_settings_get, name='api_settings_get'),
    path('api/settings/save/', views.api_settings_save, name='api_settings_save'),
]
