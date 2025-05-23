"""RealEstate URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    # Nothing after domain name will direct you to BaseApp
    path('', include('apps.baseApp.urls')),
    path('blog/', include('apps.blogApp.urls')),
    path('fa/', include('apps.FAbaseApp.urls')),
    path('fa/راهنمای-ترکیه/', include('apps.FAblogApp.urls')),
    path('chat/', include('apps.chatApp.urls')),
    path('telegram/', include('apps.telegramApp.urls')),

    # This is for Blog Editor in blogApp.models.py
    path('ckeditor/', include('ckeditor_uploader.urls')),
    path('robots.txt', include('robots.urls')),
    path('captain/', admin.site.urls),
    ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


# Fot Debug analysis
# if settings.DEBUG:
#     import debug_toolbar
#     urlpatterns = [
#         path('__debug__/', include(debug_toolbar.urls)),
#     ] + urlpatterns
