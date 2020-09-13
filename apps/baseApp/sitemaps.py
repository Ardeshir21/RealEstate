from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from apps.baseApp.models import Asset, FAQCategories
from apps.blogApp.models import Post

class StaticSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.5
    protocol = 'https'

    def items(self):
        return ['baseApp:index', 'baseApp:properties', 'baseApp:about_us',
                'FAbaseApp:index', 'FAbaseApp:properties', 'FAbaseApp:about_us']

    def location(self, item):
        return reverse(item)


# Asset sitemap EN
class AssetSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.6
    protocol = 'https'

    def items(self):
        return Asset.objects.all()

    def lastmod(self, item):
        return item.updated
    # for method location it will use the get_absolute_url of the main models
    # it creates urls for all asset in English language

# Asset sitemap FA
class AssetFaSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.6
    protocol = 'https'

    def items(self):
        return Asset.objects.all()

    def lastmod(self, item):
        return item.updated

    # it creates urls for all asset in English language
    def location(self, item):
        return reverse('FAbaseApp:propertyView', args=(item.id,))

# Posts EN
class PostSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.8
    protocol = 'https'

    def items(self):
        return Post.objects.filter(language='EN', status=True)

    def lastmod(self, item):
        return item.updated_on

# Posts FA
class PostFaSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.8
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

    def lastmod(self, item):
        # Take all ManyToMany question for current Category, and take the first one which is ordered by updated field
        latestFAQ_item = item.categories.all()[0]
        # Use the last update of question for each Category
        return latestFAQ_item.updated

# FAQ FA
class FAQCategoriesFaSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.9
    protocol = 'https'

    def items(self):
        return FAQCategories.objects.filter(category_lang='FA')

    def location(self, item):
        return reverse('FAbaseApp:faq', args=(item.slug,))

    def lastmod(self, item):
        # Take all ManyToMany question for current Category, and take the first one which is ordered by updated field
        latestFAQ_item = item.categories.all()[0]
        # Use the last update of question for each Category
        return latestFAQ_item.updated
