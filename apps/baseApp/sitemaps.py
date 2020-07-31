from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from apps.baseApp.models import Asset

class StaticSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6
    protocol = 'https'

    def items(self):
        return ['baseApp:index', 'baseApp:properties',
                'FAbaseApp:index', 'FAbaseApp:properties']

    def location(self, item):
        return reverse(item)

# Asset sitemap EN
class AssetSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.7
    protocol = 'https'

    def items(self):
        return Asset.objects.all()

    def lastmod(self, obj):
        return obj.created

# Asset sitemap FA
class AssetFaSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.7
    protocol = 'https'

    def items(self):
        return Asset.objects.all()

    def lastmod(self, item):
        return item.created

    def location(self, item):
        return reverse('FAbaseApp:propertyView', args=(item.id,))

# Posts EN
class PostSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8
    protocol = 'https'

    def items(self):
        return Post.objects.all()

    def lastmod(self, item):
        return item.updated_on

# Posts EN
class PostSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8
    protocol = 'https'

    def items(self):
        return Post.objects.all()

    def lastmod(self, item):
        return item.updated_on

    def location(self, item):
        return reverse('FAblogApp:post_detail', args=(item.slug,))
