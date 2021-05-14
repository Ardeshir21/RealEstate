# This scraper will use the javascript tag of the DOM to grab data

import requests
from bs4 import BeautifulSoup
import re
import json

def GoScrape(URL):
    try:
        page = requests.get(URL)
    # When the request is not a valid URL
    except: return None

    page_soup = BeautifulSoup(page.content, 'html.parser')
    scraped_data = javascriptScraper(page_soup)

    original_name = scraped_data.product.name
    image_main = 'https://cdn.dsmcdn.com' + scraped_data.product.images[0]
    images_urls_list = ['https://cdn.dsmcdn.com'+url for url in scraped_data.product.images]
    original_price = priceMaker(scraped_data.product.price.originalPrice.text)
    discounted_price = priceMaker(scraped_data.product.price.discountedPrice.text)
    indirim_price = priceMaker(scraped_data.product.price.sellingPrice.text)
    prices_list = [original_price, discounted_price, indirim_price]

    try:
        final_price = min(i for i in prices_list if i is not None)
    # the situation that the list is empty
    except:
        final_price = None

    # Size Variants Objects List
    size_variants = scraped_data.product.variants
    # Make the required structure from each Object
    size_variants_list = []
    for variant in size_variants:
        temp_dict = {}
        temp_dict['Size'] = variant.attributeValue
        # if there is no size variant i.e. One Size only
        if temp_dict['Size'] == "":
            temp_dict['Size'] = "تک سایز"
        temp_dict['Original_Price'] = priceMaker(variant.price.originalPrice.text)
        temp_dict['Discounted_Price'] = priceMaker(variant.price.discountedPrice.text)
        # in Trendyol Stock:null or Stock:int means Available
        # But Stock:0 means Not Available
        temp_dict['Stock'] = variant.stock
        # add the built dictionary to the list
        size_variants_list.append(temp_dict)

    # The structure of the result dictionary must be the same in other websites scrapes
    # This will be used in command > runscraper.py
    result= {
    'Original_Name': original_name,
    'Image': image_main,
    'Images': images_urls_list,
    'Original_Price': original_price,
    'Final_Price': final_price,
    'Size_Variants': size_variants_list,
    }

    return result

# a class to convert json to dictionary
class Generic:
    @classmethod
    def from_dict(cls, dict):
        obj = cls()
        obj.__dict__.update(dict)
        return obj

def javascriptScraper(soup):
    # take the first script with this type
    temp_script= soup.find('script', type='application/javascript').string

    # locate the "product" and end of "product" in script
    start_product = [m.start() for m in re.finditer('{"product"', temp_script)]
    end_product =[m.start() for m in re.finditer(',"htmlContent"', temp_script)]
    # use json library and the Generic class to convert Json to Python Object
    # Usage: result.product.price....
    # You may check the structure with result.__dict__
    result = json.loads(temp_script[start_product[0]:end_product[0]]+'}',
                            object_hook=Generic.from_dict)

    return result

def priceMaker(text):
    try:
        text = text.strip('TL')
        text = text.replace(',', '.')
        price = float(text)
        return price
    except:
        return None
