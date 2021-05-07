from apps.scrapeApp.management.commands.runscraper import domain_list
from urllib.parse import urlparse
from apps.scrapeApp import models


# Scrape the required URL from available scraper codes
def GoScrape(requested_url):

    # Check the domain for the products' url
    product_domain = urlparse(requested_url).netloc

    # if the domain is in scrapers list
    if product_domain in domain_list.keys():
        # Use appropriate module to scrape the data. It runs GoScrape() functions for required domain
        # result structure
                # result= {
                # 'Original_Name': original_name,
                # 'Image': image_main,
                # 'Images': images_urls_list,
                # 'Original_Price': original_price,
                # 'Final_Price': final_price,
                # 'Size_Variants': size_variants_list,
                # }
        product_scraped_object = domain_list[product_domain](requested_url)

        # if the URL exists and valid, we make a calculated tomans with it
        if product_scraped_object is not None:
            # calc tomans for each variant and replace it with  'Size_Variants': size_variants_list
            # each variant has the following dictionary structure
                    # {'Size'
                    # 'Original_Price'
                    # 'Discounted_Price'
                    # 'Stock'}
            # create a list of dictionaries with size_variants and their calc_toman values
            calculated_variants = []
            for variant in product_scraped_object['Size_Variants']:
                # check Stock Availability
                if variant['Stock'] == 0:
                    variant['Stock'] = False
                else:
                    variant['Stock'] = True

                temp_dict = {}
                temp_dict['variant_obj'] = variant
                temp_dict['calculated_values'] = calc_tomans(variant)
                calculated_variants.append(temp_dict)

            # replace the new dictionary with 'Size_Variants': size_variants_list
            product_scraped_object['Size_Variants'] = calculated_variants
            return product_scraped_object

    # if the domain is not in the scrapers List
    else:
        return False

# Toman Price Calculator for AJAX and GoScrape
def calc_tomans(scraped_object):
    '''
    The input dictionary must have this two keys:
        Original_Price
        Discounted_Price
    The latest SalesParameter are used
    Note: Calculation is based on 500 gr garment product
    '''
    # Get latest Parameters
    last_sales_params = models.SalesParameter.objects.filter(weight_category='Garment').latest('date')
    last_currency_data = models.CurrencyRate.objects.latest('date')
    currency_rate = last_currency_data.rate_TurkishLira

    # Do some calculation on result
    product_original_price = float(scraped_object['Original_Price']) * currency_rate
    product_final_price = float(scraped_object['Discounted_Price']) * currency_rate
    # calculation is based on 500 gr garment product
    transport_plus_margin = (0.5 * last_sales_params.pricePerKilo) + (product_final_price * (last_sales_params.margin_percent/100))

    # Sum all the cost and prices of LOWER
    final_price_with_cost = product_final_price + transport_plus_margin

    calculated_data = {
    'Currency_Rate': int(currency_rate),
    'Product_Original_Price': int(product_original_price),
    'Product_Final_Price': int(product_final_price),
    'Transport_Margin': int(transport_plus_margin),
    'Final_Price_With_Cost': int(final_price_with_cost)
    }
    return calculated_data

# Custome method to if product has discount
# It's used in Templates
def is_discounted(self):
        '''
        output: True or False
        '''
        if self.original_price > self.final_price:
            return True
        else:
            return False




# def calc_tomans(scraped_data):
#         '''
#         This function is used for AJAX call
#         scraped_data must be taken from GoScrape functions.
#         The latest SalesParameter are used
#         '''
#         # Get latest Parameters
#         last_sales_params = models.SalesParameter.objects.latest('date')
#         last_currency_data = models.CurrencyRate.objects.latest('date')
#         currency_rate = last_currency_data.rate_TurkishLira
#
#         # Do some calculation on result
#         product_original_price = scraped_data['Original_Price'] * currency_rate
#         product_final_price = scraped_data['Final_Price'] * currency_rate
#
#         transport_plus_margin = last_sales_params.pricePerKilo + (product_final_price * (last_sales_params.margin_percent/100))
#
#         final_price_with_cost = product_price + transport_plus_margin
#
#         calculated_data = {
#         'Currency_Rate': currency_rate,
#         'Product_Original_Price': product_original_price,
#         'Product_Final_Price': product_final_price,
#         'Transport_Margin': transport_plus_margin,
#         'Final_Price_With_Cost': final_price_with_cost
#         }
#
#         return calculated_data
