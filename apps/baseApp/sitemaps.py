from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from apps.baseApp.models import Asset, FAQCategories
from apps.blogApp.models import Post

class StaticSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.5
    protocol = 'https'

    def items(self):
        return ['baseApp:index', 'baseApp:properties',
                'FAbaseApp:index', 'FAbaseApp:properties']

    def location(self, item):
        return reverse(item)

# Asset sitemap EN
class AssetSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.5
    protocol = 'https'

    def items(self):
        return Asset.objects.all()

    def lastmod(self, obj):
        return obj.created

# Asset sitemap FA
class AssetFaSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.5
    protocol = 'https'

    def items(self):
        return Asset.objects.all()

    def lastmod(self, item):
        return item.created

    def location(self, item):
        return reverse('FAbaseApp:propertyView', args=(item.id,))

# Posts EN
class PostSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.7
    protocol = 'https'

    def items(self):
        return Post.objects.filter(language='EN', status=True)

    def lastmod(self, item):
        return item.updated_on

# Posts FA
class PostFaSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.7
    protocol = 'https'

    def items(self):
        return Post.objects.filter(language='FA', status=True)

    def lastmod(self, item):
        return item.updated_on

    def location(self, item):
        return reverse('FAblogApp:post_detail', args=(item.slug,))

# FAQ EN
class FAQCategoriesSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.9
    protocol = 'https'

    def items(self):
        return FAQCategories.objects.filter(category_lang='EN')

# FAQ FA
class FAQCategoriesFaSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.9
    protocol = 'https'

    def items(self):
        return FAQCategories.objects.filter(category_lang='FA')

    def location(self, item):
        return reverse('FAbaseApp:faq', args=(item.slug,))
