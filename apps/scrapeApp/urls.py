from . import views
from django.urls import path, re_path

app_name = 'scrapeApp'

urlpatterns = [
    path('', views.AllStoreView.as_view(), name='all_stores'),
    path('<slug:store>/', views.StoreView.as_view(), name='store_page'),
    re_path(r'^(?P<store>[-\w]+)/(?P<product_id>[0-9]+)/(?P<product_slug>[-\w]+)/$', views.ProductView.as_view(), name='product_page'),
    path('scraper/', views.AJAX_SCRAPE.as_view(), name='link_scraper'),
    # re_path(r'^category/(?P<category>[-\w]+)/$', views.CategoryListView.as_view(), name='category_list'),
    # re_path(r'^(?P<slug>[-\w]+)/$', views.PostDetail.as_view(), name='post_detail'),
    # path('search/keyword/', views.PostSearch.as_view(), name='search'),
]
