from django.urls import path, re_path
from . import views

app_name = 'FAbaseApp'

urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),
    path('املاک/', views.AssetFilterView.as_view(), name='properties'),
    path('املاک/<int:pk>/', views.AssetSingleView.as_view(), name='propertyView'),
    path('درباره-ما/', views.ContactView.as_view(), name='about_us'),
    re_path(r'^سوالات-متداول/(?P<category>[-\w]+)/$', views.FAQCategoryView.as_view(), name='faq'),
    path('FAQsearch/', views.FAQSearch.as_view(), name='faq_search'),
]
