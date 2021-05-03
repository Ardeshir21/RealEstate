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

    image_main = 'https://www.trendyol.com/' + scraped_data.product.images[0]
    images_urls_list = ['https://www.trendyol.com/'+url for url in scraped_data.product.images]
    original_price = priceMaker(scraped_data.product.price.originalPrice.text)
    discounted_price = priceMaker(scraped_data.product.price.discountedPrice.text)
    indirim_price = priceMaker(scraped_data.product.price.sellingPrice.text)
    prices_list = [original_price, discounted_price, indirim_price]

    try:
        final_price = min(i for i in prices_list if i is not None)
    # the situation that the list is empty
    except:
        final_price = None

    # The structure of the result dictionary must be the same in other websites scrapes
    # This will be used in command > runscraper.py 
    result= {
    'Image': image_main,
    'Images': images_urls_list,
    'Original_Price': original_price,
    'Final_Price': final_price
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
