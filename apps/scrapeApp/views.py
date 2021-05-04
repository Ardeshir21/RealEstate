from django.shortcuts import render
from django.views import generic
from .management.commands import runscraper
from . import models
from django.contrib.auth.mixins import LoginRequiredMixin
from apps.baseApp import models as baseAppModel
from apps.blogApp import models as blogAppModel
from .scrapers import Trendyol
from django.db.models import Q

# Here is the Extra Context ditionary which is used in get_context_data of Views classes
def get_extra_context():
    extraContext = {
        'featuredProperties': baseAppModel.Asset.objects.filter(featured=True),
        # All blog categories
        'blogCategories_All': blogAppModel.PostCategories.objects.filter(category_lang='FA'),
        # Blog Categories with EN language filter
        'blogCategories': blogAppModel.PostCategories.objects.filter(category_lang='FA').exclude(pk__in=[24, 27, 30]),
        # Item for Navbar from Blog CategoryListView
        'blogCategoriesNav': blogAppModel.PostCategories.objects.filter(category_lang='FA', pk__in=[24, 27, 30]),
        # Default page for FAQ section.
        'navbar_FAQ': 'all'
        }
    return extraContext

class AllStoreView(generic.ListView):
    context_object_name = 'stores'
    template_name = 'scrapeApp/all-stores.html'
    model = models.Store

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        # Append shared extraContext
        context.update(get_extra_context())

        # This title is different for this view
        context['slideContent'] = baseAppModel.Slide.objects.get(useFor__exact='BLOG_HOME', active__exact=True)

        return context

class StoreView(generic.ListView):
    context_object_name = 'products'
    template_name = 'scrapeApp/store.html'
    model = models.Product
    paginate_by = 16

    def get_queryset(self, **kwargs):
        result = super(StoreView, self).get_queryset()

        # Categories -- For filtering based on the categories
        result= result.filter(store__slug=self.kwargs['store'], active=True)
        return result

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        # Append shared extraContext
        context.update(get_extra_context())

        context['the_store'] = models.Store.objects.get(slug=self.kwargs['store'])
        # This title is different for this view
        context['slideContent'] = baseAppModel.Slide.objects.get(useFor__exact='BLOG_HOME', active__exact=True)

        return context

class ProductView(generic.DetailView):
    context_object_name = 'the_product'
    template_name = 'scrapeApp/product.html'
    model = models.Product
    slug_url_kwarg = 'product_slug'
    pk_url_kwarg = 'product_id'
    query_pk_and_slug = True

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        # Append shared extraContext
        context.update(get_extra_context())

        # form Product model method. Here is the structure:
                # calculated_data = {
                # 'Currency_Rate': currency_rate,
                # 'Product_Original_Price': product_original_price,
                # 'Product_Final_Price': product_final_price,
                # 'Transport_Margin_Upper': transport_plus_margin_upper,
                # 'Transport_Margin_Lower': transport_plus_margin_lower,
                # 'Final_Price_With_Cost': final_price_with_cost
                # }
        context['calculated_data'] = self.get_object().calc_tomans()

        # This title is different for this view
        context['slideContent'] = baseAppModel.Slide.objects.get(useFor__exact='BLOG_HOME', active__exact=True)

        return context

# Run scraper to update the database
class RUN_SCRAPER(LoginRequiredMixin, generic.TemplateView):
    template_name = 'scrapeApp/scraper.html'

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        # Append shared extraContext
        context.update(get_extra_context())

        args = []
        options = {}
        command_obj = runscraper.Command()
        command_obj.handle(*args, **options)

        return context

# AJAX call which is used to scrape product with URL by client
class AJAX_SCRAPE(generic.TemplateView):
    template_name = 'scrapeApp/scrape_result.html'

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        # Append shared extraContext
        context.update(get_extra_context())

        # We recieve the request information
        client_ip = self.request.META['REMOTE_ADDR']
        requested_url = self.request.GET.get('requested_url')

        # Here we use a scraper code from spiders folder to get required data from a website
        scraped_data= Trendyol.GoScrape(requested_url)

        calculated_data = calc_tomans_ajax(scraped_data)

        if scraped_data:
            context['scraped_data'] = scraped_data
            context['calculated_data'] = calculated_data
            # Save to database
            instance = models.RequestedLinks(url=requested_url,
                                            client_ip=client_ip)
            instance.save()

        return context

# Toman Price Calculator for AJAX and GoScrape
def calc_tomans_ajax(scraped_data):
    '''
    This function is used for AJAX call
    scraped_data must be taken from GoScrape functions.
    The latest SalesParameter are used
    '''
    # Get latest Parameters
    last_sales_params = models.SalesParameter.objects.latest('date')
    last_currency_data = models.CurrencyRate.objects.latest('date')
    currency_rate = last_currency_data.rate_TurkishLira

    # Do some calculation on result
    product_original_price = scraped_data['Original_Price'] * currency_rate
    product_final_price = scraped_data['Final_Price'] * currency_rate

    transport_plus_margin = last_sales_params.pricePerKilo + (product_final_price * (last_sales_params.margin_percent/100))

    final_price_with_cost = product_price + transport_plus_margin

    calculated_data = {
    'Currency_Rate': currency_rate,
    'Product_Original_Price': product_original_price,
    'Product_Final_Price': product_final_price,
    'Transport_Margin': transport_plus_margin,
    'Final_Price_With_Cost': final_price_with_cost
    }

    return calculated_data
