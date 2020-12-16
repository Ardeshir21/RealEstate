from django.shortcuts import render
from django.views import generic
from . import models
from apps.baseApp import models as baseAppModel
from apps.blogApp import models as blogAppModel
from .spiders import Trendyol
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


class LinkQuotation(generic.TemplateView):
    template_name = 'scrapeApp/link_quotation.html'

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        # Append shared extraContext
        context.update(get_extra_context())

        # This title is different for this view
        context['slideContent'] = baseAppModel.Slide.objects.get(useFor__exact='BLOG_HOME', active__exact=True)

        return context

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

        # Here we use a scraper code to get required data from a website
        scraped_data= Trendyol.GoScrape(requested_url)

        # Do some calculation on result
        last_sales_params = models.SalesParameter.objects.latest('date')
        last_currency_data = models.CurrencyRate.objects.latest('date')
        currency_rate = last_currency_data.rate_TurkishLira
        product_price = scraped_data['Final_Price'] * currency_rate
        transport_plus_margin = last_sales_params.pricePerKilo + (product_price * (last_sales_params.margin_percent/100))
        final_price = product_price + transport_plus_margin

        calculated_data = {
        'Currency_Rate': currency_rate,
        'Product_Price': product_price,
        'Transport_Margin': transport_plus_margin,
        'Final_Price': final_price
        }

        if scraped_data:
            context['scraped_data'] = scraped_data
            context['calculated_data'] = calculated_data
            # Save to database
            instance = models.RequestedLinks(url=requested_url,
                                            client_ip=client_ip)
            instance.save()

        return context
