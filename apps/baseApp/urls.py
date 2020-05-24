from django.urls import path
from . import views

app_name = 'baseApp'

urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),
    path('search/', views.AssetFilterView.as_view(), name='search'),
    # Not using this form, because the Admin page form is enough for property entry
    # path('form/newAsset', views.AssetCreateForm.as_view(), name='newAssetForm'),
    path('properties/<int:pk>/', views.AssetSingleView.as_view(), name='propertyView')
]
