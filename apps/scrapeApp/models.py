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
    description = models.CharField(max_length=500)
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

class Product(models.Model):
    store = models.ForeignKey(Store, related_name='products', on_delete=models.CASCADE)
    main_url = models.CharField(max_length=1000)
    name = models.CharField(max_length=250)
    original_price = models.DecimalField(max_digits=10, decimal_places=2, default=10.00, null=True, blank=True)
    final_price = models.DecimalField(max_digits=10, decimal_places=2, default=10.00, null=True, blank=True)
    image_url = models.CharField(max_length=1000, null=True, blank=True)
    active = models.BooleanField(choices=YES_NO_CHOICES, default=True)
    featured = models.BooleanField(choices=YES_NO_CHOICES, default=False)
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

    # Display Thumbnails
    def image_tag(self):
        return mark_safe('<img src="%s" width="100" height="100" />' % (self.image_url))
    image_tag.short_description = 'Image'

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
