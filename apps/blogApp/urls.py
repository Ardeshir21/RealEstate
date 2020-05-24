from . import views
from django.urls import path

app_name = 'blogApp'

urlpatterns = [
    path('', views.PostList.as_view(), name='all_posts'),
    path('category/<slug:category>/', views.CategoryListView.as_view(), name='category_list'),
    path('<slug:slug>/', views.PostDetail.as_view(), name='post_detail'),
    path('search/keyword/', views.PostSearch.as_view(), name='search'),
]
