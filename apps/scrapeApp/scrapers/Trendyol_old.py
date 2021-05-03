import requests
from bs4 import BeautifulSoup


def GoScrape(URL):
    try:
        page = requests.get(URL)
    # When the request is not a valid URL
    except: return None

    page_soup = BeautifulSoup(page.content, 'html.parser')

    title = titleScraper(page_soup)
    image_main = mainImageScraper(page_soup)
    images_urls_list = imagesScraper(page_soup)
    original_price = priceMaker(originalPriceScraper(page_soup))
    discounted_price = priceMaker(discountedPriceScraper(page_soup))
    indirim_price = priceMaker(indirimPriceScraper(page_soup))
    prices_list = [original_price, discounted_price, indirim_price]

    try:
        final_price = min(i for i in prices_list if i is not None)
    # the situation that the list is empty
    except:
        final_price = None


    # When the request is URL but not related to Trendyol Product page
    # if title==None and discounted_price==None:
    #     return False

    result= {
    'Title': title,
    'Image': image_main,
    'Images': images_urls_list,
    'Final_Price': final_price
    }

    return result


def titleScraper(soup):
    temp_= soup.select_one('h1.pr-new-br span')
    if temp_:
        return temp_.text

def mainImageScraper(soup):
    temp_= soup.select_one('img.ph-gl-img')
    if temp_:
        return temp_['src']

def imagesScraper(soup):
    temp_= soup.select('.ph-gl-w.ph-gl-sml.pd-img img')
    if temp_:
        return [item['src'] for item in temp_]

def originalPriceScraper(soup):
    temp_= soup.select_one('span.prc-org')
    if temp_:
        return temp_.text


def discountedPriceScraper(soup):
    temp_= soup.select_one('span.prc-slg')
    if temp_:
        return temp_.text

    temp_= soup.select_one('span.prc-slg.prc-slg-w-dsc')
    if temp_:
        return temp_.text

def indirimPriceScraper(soup):
    temp_= soup.select_one('span.prc-dsc')
    if temp_:
        return temp_.text

def priceMaker(text):
    try:
        text = text.strip('TL')
        text = text.replace(',', '.')
        price = float(text)
        return price
    except:
        return None
