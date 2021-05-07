from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError
from urllib.parse import urlparse
from apps.scrapeApp import models
from apps.scrapeApp.scrapers import Trendyol


domain_list = {'www.trendyol.com': Trendyol.GoScrape,
                # 'www.lcwaikiki.com': Trendyol.GoScrape
}

class Command(BaseCommand):
    help = 'Does some magical work'

    def handle(self, *args, **options):
        # Get all the active products
        all_products = models.Product.objects.filter(active=True)

        # Loop over all the active product to scrape their information and update the database
        for product in all_products:
            # Check the domain for the products' url
            product_domain = urlparse(product.main_url).netloc

            # if the domain is in scrapers list
            if product_domain in domain_list.keys():
                # Use appropriate module to scrape the data. It runs GoScrape() function
                product_scraped_object = domain_list[product_domain](product.main_url)

                # if the URL exists and valid make the Product Instance
                if product_scraped_object is not None:
                    # insert new information into product
                    product.original_name = product_scraped_object['Original_Name']
                    product.original_price = product_scraped_object['Original_Price']
                    product.final_price = product_scraped_object['Final_Price']

                    # Add main image
                    product.image_url = product_scraped_object['Image']

                    # Other images
                    # first delete all instances to prevent duplicates
                    all_images = models.ProductImagesUrls.objects.filter(product=product)
                    all_images.delete()
                    # now add new images_urls to the model
                    for image_url in product_scraped_object['Images']:
                        try:
                            image = models.ProductImagesUrls(
                                                            product=product,
                                                            image_url=image_url,
                                                            display_order = 2)
                            image.save()
                        except IntegrityError: continue

                    # Size Variants
                    # first delete all instances to prevent duplicates
                    all_variantes = models.ProductSizeVariants.objects.filter(main_product=product)
                    all_variantes.delete()
                    # add new vriantes to the model
                    for size_item in product_scraped_object['Size_Variants']:
                        try:
                            # Check Availability of Stock
                            if size_item['Stock'] == 0:
                                is_avaiable = False
                            else:
                                is_avaiable = True

                            temp_variant = models.ProductSizeVariants(
                                                            main_product=product,
                                                            size=size_item['Size'],
                                                            original_price = size_item['Original_Price'],
                                                            final_price = size_item['Discounted_Price'],
                                                            active = is_avaiable)
                            temp_variant.save()
                        except IntegrityError:
                            continue

                    # Deactivate the product with some conditions
                    if product.final_price is None:
                        product.active = False
                    # if there is no Size Variants list, it means the product is Sold Out
                    if len(product_scraped_object['Size_Variants']) == 0:
                        product.active = False

                    product.save()
                    self.stdout.write('{} has been updated'.format(product.name))

            # if the domain is not in the scrapers List
            else:
                product.active = False
                product.save()
                self.stdout.write('ERROR: from different domain - {}'.format(product.name))
        return
