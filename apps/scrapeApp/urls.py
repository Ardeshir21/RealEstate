from . import views
from django.urls import path, re_path

app_name = 'scrapeApp'

urlpatterns = [
    path('', views.AllStoreView.as_view(), name='all_stores'),
    path('stores/<slug:store>/', views.StoreView.as_view(), name='store_page'),
    re_path(r'^stores/(?P<store>[-\w]+)/(?P<product_id>[0-9]+)/(?P<product_slug>[-\w]+)/$', views.ProductView.as_view(), name='product_page'),
    path('scraper/url', views.AJAX_SCRAPE.as_view(), name='link_scraper'),
    path('scraper/run/', views.RUN_SCRAPER.as_view(), name='runscraper'),
    # re_path(r'^category/(?P<category>[-\w]+)/$', views.CategoryListView.as_view(), name='category_list'),
    # re_path(r'^(?P<slug>[-\w]+)/$', views.PostDetail.as_view(), name='post_detail'),
    # path('search/keyword/', views.PostSearch.as_view(), name='search'),
]
