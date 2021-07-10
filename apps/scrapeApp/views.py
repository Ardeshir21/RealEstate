from django.shortcuts import render
from django.views import generic
from .management.commands import runscraper
from . import models
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from apps.baseApp import models as baseAppModel
from apps.blogApp import models as blogAppModel
from .scrapers import AJAX
from django.db.models import Q

# Here is the Extra Context ditionary which is used in get_context_data of Views classes
def get_extra_context():
    extraContext = {
        'DEBUG_VALUE': settings.DEBUG,
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

class HomeStoreView(generic.ListView):
    context_object_name = 'stores'
    template_name = 'scrapeApp/all-stores.html'
    model = models.Store

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        # Append shared extraContext
        context.update(get_extra_context())

        # This title is different for this view
        context['slideContent'] = baseAppModel.Slide.objects.get(useFor__exact='STORE_HOME', active__exact=True)
        context['pageTitle'] = 'خرید کالا از ترکیه'
        context['featured_brands'] = models.ProductBrand.objects.filter(featured=True)

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
        context['slideContent'] = models.Store.objects.get(slug=self.kwargs['store'])

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

        # We have the The_Product but we need all its size variants to display on the template
        # from ProductSizeVariants model method. Here is the structure:
                # calculated_data = {
                # 'Currency_Rate': currency_rate,
                # 'Product_Original_Price': product_original_price,
                # 'Product_Final_Price': product_final_price,
                # 'Transport_Margin_Upper': transport_plus_margin_upper,
                # 'Transport_Margin_Lower': transport_plus_margin_lower,
                # 'Final_Price_With_Cost': final_price_with_cost
                # }
        all_related_variants = self.get_object().size_variants.all()
        # create a list of dictionaries with size_variants and their calc_toman values
        calculated_variants = []
        for variant in all_related_variants:
            temp_dict = {}
            temp_dict['variant_obj'] = variant
            temp_dict['calculated_values'] = variant.calc_tomans()
            calculated_variants.append(temp_dict)

        context['variants_calculated_data'] = calculated_variants
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
        context['slideContent'] = baseAppModel.Slide.objects.get(useFor__exact='STORE_HOME', active__exact=True)
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

        # Here we use two other functions to scrape the data and make the calculations
        # AJAX.GoScrape structure
                # result= {
                # 'Original_Name': original_name,
                # 'Image': image_main,
                # 'Images': images_urls_list,
                # 'Original_Price': original_price,
                # 'Final_Price': final_price,
                # 'Size_Variants': calculated_variants,   ***Note: This is a calculated dictionary
                # }
        scraped_data= AJAX.GoScrape(requested_url)

        if scraped_data:
            context['scraped_data'] = scraped_data

            # Save requested URL into the database
            instance = models.RequestedLinks(url=requested_url,
                                            client_ip=client_ip)
            instance.save()
        # Not showing any table
        else:
            context['scraped_data'] = False

        context['RequestedLink'] = requested_url
        return context
