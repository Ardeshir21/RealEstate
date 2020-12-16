from . import views
from django.urls import path, re_path

app_name = 'scrapeApp'

urlpatterns = [
    path('', views.LinkQuotation.as_view(), name='quotation'),
    path('scraper/', views.AJAX_SCRAPE.as_view(), name='link_scraper'),
    # re_path(r'^category/(?P<category>[-\w]+)/$', views.CategoryListView.as_view(), name='category_list'),
    # re_path(r'^(?P<slug>[-\w]+)/$', views.PostDetail.as_view(), name='post_detail'),
    # path('search/keyword/', views.PostSearch.as_view(), name='search'),
]
