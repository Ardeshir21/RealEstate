from django.urls import path
from . import views

app_name = 'FAbaseApp'

urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),
    path('properties/', views.AssetFilterView.as_view(), name='properties'),
    path('properties/<int:pk>/', views.AssetSingleView.as_view(), name='propertyView'),
    path('about-us/', views.ContactView.as_view(), name='about_us')
]


handler404 = 'apps.FAbaseApp.views.error_404'
