from django.urls import path
from django.contrib.sitemaps.views import sitemap
from . import views, sitemaps

app_name = 'baseApp'

sitemaps_dict = {'Static_sitemap': sitemaps.StaticSitemap,
                'Asset_sitemap': sitemaps.AssetSitemap,
                'AssetFa_sitemap': sitemaps.AssetFaSitemap,
                }

urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),
    path('properties/', views.AssetFilterView.as_view(), name='properties'),
    path('properties/<int:pk>/', views.AssetSingleView.as_view(), name='propertyView'),

    # This is for sitemap.xml
    path('RealSiteMap.xml', sitemap, {'sitemaps': sitemaps_dict},
     name='django.contrib.sitemaps.views.sitemap'),
]
