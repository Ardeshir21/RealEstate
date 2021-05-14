import requests
from bs4 import BeautifulSoup


def GoScrape(URL):
    try:
        page = requests.get(URL)
    # When the request is not a valid URL
    except: return None

    page_soup = BeautifulSoup(page.content, 'html.parser')

    original_name = titleScraper(page_soup)
    image_main = mainImageScraper(page_soup)
    images_urls_list = imagesScraper(page_soup)
    original_price = priceMaker(originalPriceScraper(page_soup))
    discounted_price = priceMaker(discountedPriceScraper(page_soup))
    prices_list = [original_price, discounted_price]

    try:
        final_price = min(i for i in prices_list if i is not None)
    # the situation that the list is empty
    except:
        final_price = None

    # Size Variants List
    size_variants = sizeVariantsScraper(page_soup)
    # Make the required structure from each item
    size_variants_list = []
    for variant in size_variants:
        temp_dict = {}
        temp_dict['Size'] = variant['size_name']
        # if there is One Size only
        if len(size_variants) == 1:
            temp_dict['Size'] = "تک سایز"
        temp_dict['Original_Price'] = original_price
        temp_dict['Discounted_Price'] = discounted_price
        # If not available the value is 0, other values means available
        temp_dict['Stock'] = variant['size_stock']
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



def titleScraper(soup):
    temp_= soup.find("meta", {"name" : "ProductName"})
    if temp_:
        return temp_.attrs['content']

def mainImageScraper(soup):
    temp_= soup.select_one('div.mobile-main-slider')
    if temp_:
        return temp_.img.attrs['data-large-img-url']

def imagesScraper(soup):
    temp_= soup.select_one('div.mobile-main-slider')
    temp_list = []
    if temp_:
        for image in temp_.find_all('img'):
            temp_list.append(image.attrs['data-large-img-url'])
        return temp_list

def originalPriceScraper(soup):
    temp_= soup.find("meta", {"name" : "CashPrice_1"})
    if temp_:
        return temp_.attrs['content']


def discountedPriceScraper(soup):
    temp_= soup.find("meta", {"name" : "DiscountPrice_1"})
    if temp_:
        return temp_.attrs['content']

def sizeVariantsScraper(soup):
    # This the result list
    result = []

    # Size Names
    temp_size_name= soup.find("meta", {"name" : "Size"})
    if temp_size_name:
        text_ = temp_size_name.attrs['content']
        size_names = [x.strip() for x in text_.split(',')]

    # Size Codes
    temp_size_code= soup.find("meta", {"name" : "SizeId"})
    if temp_size_code:
        text_ = temp_size_code.attrs['content']
        size_codes = [x.strip() for x in text_.split(',')]

    # make a list of name and id code of sizes
    size_name_id = list(zip(size_names, size_codes))

    # Stock info and making the dictionary
    for size_item in size_name_id:
        temp_dict = {}
        # get the Stock info
        temp_stock= soup.find("meta", {"name" : "StockInfos_"+size_item[1]})
        if temp_stock:
            stock_info = temp_stock.attrs['content']

        # add information to the dictionary
        temp_dict['size_name'] = size_item[0]
        temp_dict['size_id'] = size_item[1]
        # If not available the value is 0, other values means available
        temp_dict['size_stock'] = int(stock_info)

        # add to the result list
        result.append(temp_dict)

    return result

def priceMaker(text):
    try:
        text = text.replace(',', '.')
        price = float(text)
        return price
    except:
        return None
