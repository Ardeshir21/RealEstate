from django.db import models
from django.urls import reverse_lazy, reverse
from ckeditor_uploader.fields import RichTextUploadingField
from django.utils import timezone
from django.utils.html import mark_safe
import requests

# Customer field for limited range integers
class IntegerRangeField(models.IntegerField):
    def __init__(self, verbose_name=None, name=None, min_value=None, max_value=None, **kwargs):
        self.min_value, self.max_value = min_value, max_value
        models.IntegerField.__init__(self, verbose_name, name, **kwargs)
    def formfield(self, **kwargs):
        defaults = {'min_value': self.min_value, 'max_value':self.max_value}
        defaults.update(kwargs)
        return super(IntegerRangeField, self).formfield(**defaults)

# Variables
YES_NO_CHOICES = [(True, 'Yes'), (False, 'No')]

WEIGHT_CHOICES = [  ('50gr',  '50 - 100 gr'),
                    ('100gr', '100 - 150 gr'),
                    ('150gr', '150 - 200 gr'),
                    ('200gr', '200 - 300 gr'),
                    ('300gr', '300 - 400 gr'),
                    ('400gr', '400 - 600 gr'),
                    ('600gr', '600 - 1 kg'),
                    ('1000gr', '1 - 1.5 kg'),
                    ('1500gr', '1.5 - 2 kg'),
                    ('2001gr', ' >2 kg'),]

WEIGHT_CATEGORIES = [('Garment', 'پوشاک'),
                    ('Bag_Shoes', 'کیف و کفش'),
                    ('Cosmetics', 'آرایشی')]

GENDER_CHOICES = [('Female', 'زنانه'),
                    ('Male', 'مردانه'),
                    ('None', 'بدون جنسیت')]

AGE_CHOICES = [('Adults', 'بزرگسال'),
                    ('Kids', 'بچه گانه')]
# Convert Variables
WEIGHT_CHOICES_Converted = {'50gr': [0.05, 0.1],
                            '100gr': [0.1, 0.15],
                            '150gr': [0.15, 0.2],
                            '200gr': [0.2, 0.3],
                            '300gr': [0.3, 0.4],
                            '400gr': [0.4, 0.6],
                            '600gr': [0.6, 1],
                            '1000gr': [1, 1.5],
                            '1500gr': [1.5, 2],
                            '2001gr': [2, 10]}

class RequestedLinks(models.Model):

    url = models.CharField(max_length=1000)
    client_ip = models.CharField(max_length=15)
    created_on = models.DateTimeField(editable=False)

    def __str__(self):
        return self.url

    def save(self, *args, **kwargs):
        if not self.id:
            self.created_on = timezone.now()
        return super(RequestedLinks, self).save(*args, **kwargs)

    class Meta():
        verbose_name_plural = "Requested Links"

class CurrencyRate(models.Model):
    date = models.DateField()
    rate_TurkishLira = models.IntegerField()
    created_on = models.DateTimeField(editable=False)

    def save(self, *args, **kwargs):
        if not self.id:
            self.created_on = timezone.now()
        return super(CurrencyRate, self).save(*args, **kwargs)

    class Meta():
        verbose_name_plural = "Currency Rates"
        ordering = ['-date']

class SalesParameter(models.Model):
    date = models.DateField()
    pricePerKilo = models.IntegerField()
    weight_category = models.CharField(max_length=20, choices=WEIGHT_CATEGORIES, default='Garment')
    margin_percent = IntegerRangeField(min_value=1, max_value=100)
    created_on = models.DateTimeField(editable=False)

    def save(self, *args, **kwargs):
        if not self.id:
            self.created_on = timezone.now()
        return super(SalesParameter, self).save(*args, **kwargs)

    class Meta():
        verbose_name_plural = "Sales Parameters"
        ordering = ['-date']

class Store(models.Model):
    name = models.CharField(max_length=50)
    slug = models.SlugField(max_length=300, unique=True, blank=True, null=True, allow_unicode=True)
    description = models.TextField(max_length=500)
    logo = models.ImageField(upload_to='scrapeApp/store/', null=True,
                                help_text='Thumbnail Image 600x600')
    website_url = models.CharField(max_length=100)
    image = models.ImageField(upload_to='scrapeApp/store/', null=True,
                                help_text='Thumbnail Image 1600x1200')
    created_on = models.DateTimeField(editable=False)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.id:
            self.created_on = timezone.now()
        return super(Store, self).save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('scrapeApp:store_page', args=(self.slug,))

class ProductBrand(models.Model):
    name = models.CharField(max_length=50)
    description = models.TextField(max_length=500, null=True, blank=True)
    logo = models.ImageField(upload_to='scrapeApp/brands/', null=True, blank=True,
                                help_text='Thumbnail Image 600x600')
    created_on = models.DateTimeField(editable=False)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.id:
            self.created_on = timezone.now()
        return super(ProductBrand, self).save(*args, **kwargs)

class Product(models.Model):
    store = models.ForeignKey(Store, related_name='products', on_delete=models.CASCADE)
    brand = models.ForeignKey(ProductBrand, related_name='brands', on_delete=models.CASCADE, null=True)
    main_url = models.CharField(max_length=1000)
    name = models.CharField(max_length=250)
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, default='Female')
    age = models.CharField(max_length=20, choices=AGE_CHOICES, default='Adults')
    weight_category = models.CharField(max_length=20, choices=WEIGHT_CATEGORIES, default='Garment')
    weight = models.CharField(max_length=20, choices=WEIGHT_CHOICES, default='600gr')
    featured = models.BooleanField(choices=YES_NO_CHOICES, default=False)
    original_name = models.CharField(max_length=600, null=True, blank=True)
    original_price = models.DecimalField(max_digits=10, decimal_places=2, default=10.00, null=True, blank=True)
    final_price = models.DecimalField(max_digits=10, decimal_places=2, default=10.00, null=True, blank=True)
    image_url = models.CharField(max_length=1000, null=True, blank=True)
    active = models.BooleanField(choices=YES_NO_CHOICES, null=True, blank=True, default=True)
    slug = models.SlugField(max_length=300, blank=True, null=True, allow_unicode=True)
    updated_on = models.DateTimeField(editable=False, null=True)
    created_on = models.DateTimeField(editable=False)

    def __str__(self):
        return self.name

    class Meta():
        ordering = ['-created_on']
        unique_together = ['id', 'slug']

    def save(self, *args, **kwargs):
        if not self.id:
            self.created_on = timezone.now()
        else:
            self.updated_on = timezone.now()
        return super(Product, self).save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('scrapeApp:product_page', args=(self.store.slug, self.id, self.slug))

    # Display Thumbnails
    def image_tag(self):
        return mark_safe('<img src="%s" width="100" height="100" />' % (self.image_url))
    image_tag.short_description = 'Image'

    # Custome method to calculate the Toman Price
    # Toman Price Calculator for Database
    def calc_tomans(self):
        '''
        The latest SalesParameter are used
        '''
        # Get latest Parameters
        last_sales_params = SalesParameter.objects.filter(weight_category=self.weight_category).latest('date')
        last_currency_data = CurrencyRate.objects.latest('date')
        currency_rate = last_currency_data.rate_TurkishLira

        # Do some calculation on result
        product_original_price = float(self.original_price) * currency_rate
        product_final_price = float(self.final_price) * currency_rate

        # if >2 kg was the choice
        if WEIGHT_CHOICES_Converted[self.weight][1] > 3:
            transport_plus_margin_upper = 'Heavy Product'
        else:
            transport_plus_margin_upper = (WEIGHT_CHOICES_Converted[self.weight][1] * last_sales_params.pricePerKilo) + (product_final_price * (last_sales_params.margin_percent/100))

        transport_plus_margin_lower = (WEIGHT_CHOICES_Converted[self.weight][0] * last_sales_params.pricePerKilo) + (product_final_price * (last_sales_params.margin_percent/100))

        # Sum all the cost and prices of LOWER
        final_price_with_cost = product_final_price + transport_plus_margin_lower

        calculated_data = {
        'Currency_Rate': int(currency_rate),
        'Product_Original_Price': int(product_original_price),
        'Product_Final_Price': int(product_final_price),
        'Transport_Margin_Upper': transport_plus_margin_upper,
        'Transport_Margin_Lower': int(transport_plus_margin_lower),
        'Final_Price_With_Cost': int(final_price_with_cost)
        }

        return calculated_data

    # Custome method to validate the image_url
    # It's used in Templates
    def is_image_url_valid(self):
        '''
        output: True or False
        '''
        if self.image_url is not None:
            x = requests.get(self.image_url)
            if x.status_code==200:
                return True
            else:
                return False
        # None value for image_url
        else:
            return False

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

class ProductImagesUrls(models.Model):
    product = models.ForeignKey(Product, related_name='product_images_urls', on_delete=models.CASCADE)
    image_url = models.CharField(max_length=1000, null=True, blank=True)
    display_order = models.PositiveIntegerField(null=True, blank=True)
    active = models.BooleanField(choices=YES_NO_CHOICES, default=True)

    # Display Thumbnails
    def image_tag(self):
        return mark_safe('<img src="%s" width="100" height="100" />' % (self.image_url))
    image_tag.short_description = 'Image'

    class Meta():
        verbose_name_plural = "Products Images Urls"
        ordering = ['display_order']

class ProductSizeVariants(models.Model):
    main_product = models.ForeignKey(Product, related_name='size_variants', on_delete=models.CASCADE)
    size = models.CharField(max_length=15)
    original_price = models.DecimalField(max_digits=10, decimal_places=2, default=10.00, null=True, blank=True)
    final_price = models.DecimalField(max_digits=10, decimal_places=2, default=10.00, null=True, blank=True)
    active = models.BooleanField(choices=YES_NO_CHOICES, default=True)
    updated_on = models.DateTimeField(editable=False, null=True)
    created_on = models.DateTimeField(editable=False)

    def __str__(self):
        return self.size

    def save(self, *args, **kwargs):
        if not self.id:
            self.created_on = timezone.now()
        else:
            self.updated_on = timezone.now()
        return super(ProductSizeVariants, self).save(*args, **kwargs)

    # Custome method to calculate the Toman Price
    # Toman Price Calculator for Database
    def calc_tomans(self):
        '''
        The latest SalesParameter are used
        '''
        # Get latest Parameters
        last_sales_params = SalesParameter.objects.filter(weight_category=self.main_product.weight_category).latest('date')
        last_currency_data = CurrencyRate.objects.latest('date')
        currency_rate = last_currency_data.rate_TurkishLira

        # Do some calculation on result
        product_original_price = float(self.original_price) * currency_rate
        product_final_price = float(self.final_price) * currency_rate

        # if >2 kg was the choice
        if WEIGHT_CHOICES_Converted[self.main_product.weight][1] > 3:
            transport_plus_margin_upper = 'Heavy Product'
        else:
            transport_plus_margin_upper = (WEIGHT_CHOICES_Converted[self.main_product.weight][1] * last_sales_params.pricePerKilo) + (product_final_price * (last_sales_params.margin_percent/100))

        transport_plus_margin_lower = (WEIGHT_CHOICES_Converted[self.main_product.weight][0] * last_sales_params.pricePerKilo) + (product_final_price * (last_sales_params.margin_percent/100))

        # Sum all the cost and prices of LOWER
        final_price_with_cost = product_final_price + transport_plus_margin_lower

        calculated_data = {
        'Currency_Rate': int(currency_rate),
        'Product_Original_Price': int(product_original_price),
        'Product_Final_Price': int(product_final_price),
        'Transport_Margin_Upper': transport_plus_margin_upper,
        'Transport_Margin_Lower': int(transport_plus_margin_lower),
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
