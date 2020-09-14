from django.utils import timezone
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from apps.baseApp.models import Asset, FAQCategories
from apps.blogApp.models import Post
from django.db.models import F

class StaticSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.5
    protocol = 'https'

    def items(self):
        return ['baseApp:index', 'baseApp:properties', 'baseApp:about_us',
                'FAbaseApp:index', 'FAbaseApp:properties', 'FAbaseApp:about_us']

    def location(self, item):
        return reverse(item)

    def lastmod(self, item):
        # This part check between created and updated date of lastest Asset and use the latest date
        latest_updated_item = Asset.objects.all().order_by(F('updated').desc(nulls_last=True))[0]
        latest_created_item = Asset.objects.all().order_by(F('created').desc(nulls_last=True))[0]
        if latest_updated_item.updated:
            if latest_updated_item.updated >= latest_created_item.created:
                latest_item = latest_updated_item
                return latest_item.updated
            else:
                # Use the last created of Asset for each page
                latest_item = latest_created_item
                return latest_item.created
        else:
            latest_item = latest_created_item
            return latest_item.created

# All Post Page
class AllPostSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6
    protocol = 'https'

    def items(self):
        return ['blogApp:all_posts',
                'FAblogApp:all_posts']

    def location(self, item):
        return reverse(item)

    def lastmod(self, item):
        # This part check between created and updated date of lastest Asset and use the latest date
        latest_updated_item = Post.objects.all().order_by(F('updated_on').desc(nulls_last=True))[0]
        latest_created_item = Post.objects.all().order_by(F('created_on').desc(nulls_last=True))[0]
        if latest_updated_item.updated_on:
            if latest_updated_item.updated_on >= latest_created_item.created_on:
                latest_item = latest_updated_item
                return latest_item.updated_on
            else:
                # Use the last created of Asset for each page
                latest_item = latest_created_item
                return latest_item.created_on
        else:
            latest_item = latest_created_item
            return latest_item.created_on

# Asset sitemap EN
class AssetSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6
    protocol = 'https'

    def items(self):
        return Asset.objects.all()

    def lastmod(self, item):
        if item.updated:
            return item.updated
        else: return item.created
    # for method location it will use the get_absolute_url of the main models
    # it creates urls for all asset in English language

# Asset sitemap FA
class AssetFaSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6
    protocol = 'https'

    def items(self):
        return Asset.objects.all()

    def lastmod(self, item):
        if item.updated:
            return item.updated
        else: return item.created

    # it creates urls for all asset in English language
    def location(self, item):
        return reverse('FAbaseApp:propertyView', args=(item.id,))

# Posts EN
class PostSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8
    protocol = 'https'

    def items(self):
        return Post.objects.filter(language='EN', status=True)

    def lastmod(self, item):
        if item.updated_on:
            return item.updated_on
        else: return item.created_on

# Posts FA
class PostFaSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8
    protocol = 'https'

    def items(self):
        return Post.objects.filter(language='FA', status=True)

    def lastmod(self, item):
        if item.updated_on:
            return item.updated_on
        else: return item.created_on

    def location(self, item):
        return reverse('FAblogApp:post_detail', args=(item.slug,))

# FAQ EN
class FAQCategoriesSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.9
    protocol = 'https'

    def items(self):
        return FAQCategories.objects.filter(category_lang='EN')

    def lastmod(self, item):
        # Take all ManyToMany question for current Category, and take the first one which is ordered by updated field
        # Sometimes the query result and empty queryset
        if item.categories.all().exists():
            latest_updated_item = item.categories.all().order_by(F('updated').desc(nulls_last=True))[0]
            latest_created_item = item.categories.all().order_by(F('created').desc(nulls_last=True))[0]
            if latest_updated_item.updated:
                if latest_updated_item.updated >= latest_created_item.created:
                    latest_item = latest_updated_item
                    return latest_item.updated
                else:
                    # Use the last created of Asset for each page
                    latest_item = latest_created_item
                    return latest_item.created
            else:
                latest_item = latest_created_item
                return latest_item.created
        else: return timezone.now().date()

# FAQ FA
class FAQCategoriesFaSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.9
    protocol = 'https'

    def items(self):
        return FAQCategories.objects.filter(category_lang='FA')

    def location(self, item):
        return reverse('FAbaseApp:faq', args=(item.slug,))

    def lastmod(self, item):
        # Take all ManyToMany question for current Category, and take the first one which is ordered by updated field
        # Sometimes the query result and empty queryset
        if item.categories.all().exists():
            latest_updated_item = item.categories.all().order_by(F('updated').desc(nulls_last=True))[0]
            latest_created_item = item.categories.all().order_by(F('created').desc(nulls_last=True))[0]
            if latest_updated_item.updated:
                if latest_updated_item.updated >= latest_created_item.created:
                    latest_item = latest_updated_item
                    return latest_item.updated
                else:
                    # Use the last created of Asset for each page
                    latest_item = latest_created_item
                    return latest_item.created
            else:
                latest_item = latest_created_item
                return latest_item.created
        else: return timezone.now().date()
