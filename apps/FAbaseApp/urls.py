from django.urls import path
from . import views

app_name = 'FAbaseApp'

urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),
    path('properties/', views.AssetFilterView.as_view(), name='properties'),
    path('properties/<int:pk>/', views.AssetSingleView.as_view(), name='propertyView'),
]
