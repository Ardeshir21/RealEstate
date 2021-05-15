from django.urls import path
from django.contrib.auth.decorators import login_required
from django.contrib.sitemaps.views import sitemap
from . import views, sitemaps

app_name = 'baseApp'

sitemaps_dict = {'Static_sitemap': sitemaps.StaticSitemap,
                'AllPostSitemap': sitemaps.AllPostSitemap,
                'Asset_sitemap': sitemaps.AssetSitemap,
                'AssetFa_sitemap': sitemaps.AssetFaSitemap,
                'Post_sitemap': sitemaps.PostSitemap,
                'PostFa_sitemap': sitemaps.PostFaSitemap,
                'FAQ_sitemap': sitemaps.FAQCategoriesSitemap,
                'FAQFa_sitemap': sitemaps.FAQCategoriesFaSitemap,
                'Store_sitemap': sitemaps.StoreSitemap,
                'Product_sitemap': sitemaps.ProductSitemap
                }

urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),
    path('properties/', views.AssetFilterView.as_view(), name='properties'),
    path('properties/<int:pk>/', views.AssetSingleView.as_view(), name='propertyView'),
    path('about-us/', views.ContactView.as_view(), name='about_us'),
    path('FAQ/<slug:category>/', views.FAQCategoryView.as_view(), name='faq'),
    path('FAQsearch/', views.FAQSearch.as_view(), name='faq_search'),


    # AJAX test
    path('ajaxtest/', views.AJAX_TEST.as_view(), name='ajax_test'),

    # All Asset Download Excel file
    path('export-page/', login_required(views.ExcelOutputAssets.as_view()), name='export_page'),

    # This is for sitemap.xml
    path('RealSiteMap.xml', sitemap, {'sitemaps': sitemaps_dict},
     name='django.contrib.sitemaps.views.sitemap'),
]


handler404 = 'apps.baseApp.views.error_404'
handler500 = 'apps.baseApp.views.error_500'
