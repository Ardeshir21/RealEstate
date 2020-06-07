from django.db import models
from django.urls import reverse_lazy, reverse
from ckeditor_uploader.fields import RichTextUploadingField
# from django_google_maps import fields as map_fields


# Variables
YES_NO_CHOICES = [(True, 'Yes'), (False, 'No')]


ASSET_TYPES = [('FL', 'Flat'),
                ('VI', 'Villa'),
                ('OF', 'Office'),
                ('ST', 'Store')]

TAG_CHOICES =[('FS', 'For Sale'),
                ('FR', 'For Rent')]

COMPLEX_FEATURES_CATEGORY = [('GENERAL', 'General'),
                            ('TECHNICAL', 'Technical'),
                            ('SPORT', 'Sport'),
                            ('TOP', 'Top'),
                            ('LOCATION', 'Location')]

PAGE_CHOICES = [('HOME', 'Homepage'),
                ('PROPERTY_SEARCH', 'Property Search'),
                ('PROPERTY_PAGE', 'Property View'),
                ('BLOG_HOME', 'Blog Homepage'),
                ('BLOG_SEARCH', 'Blog Search'),
                ('BLOG_CATEGORY', 'Blog Categories'),
                ('BLOG_POST', 'Blog Post')]
# Models
class Country(models.Model):

    # List of Countries
    TURKEY = 'TR'
    IRAN = 'IR'
    AUSTRALIA = 'AU'

    countryList = [(TURKEY, 'Turkey'),
                    (IRAN, 'Iran'),
                    (AUSTRALIA, 'Australia')
                    ]

    name = models.CharField(max_length=150,
                            choices=countryList,
                            default=TURKEY,
                            )

    # flag = models.ImageField(upload_to='flag/', blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta():
        verbose_name_plural = "Countries"

class City(models.Model):

    country = models.ForeignKey(Country, related_name='countries', on_delete=models.CASCADE)
    name = models.CharField(max_length=150)

    def __str__(self):
        return self.name

    class Meta():
        verbose_name_plural = "Cities"

class Region(models.Model):

    city = models.ForeignKey(City, related_name='cities', on_delete=models.CASCADE)
    name = models.CharField(max_length=150, unique=True)
    description = RichTextUploadingField(null=True, blank=True)

    def __str__(self):
        return self.name


class ComplexFeatures(models.Model):
    category = models.CharField(max_length=150, choices=COMPLEX_FEATURES_CATEGORY, default='GENERAL')
    features = models.CharField(max_length=150, unique=True)

    class Meta():
        verbose_name_plural = "Complex Features"
        ordering = ['category', 'features']

    def __str__(self):
        return '{}: {}'.format(self.category, self.features)

class Complex(models.Model):

    name = models.CharField(max_length=150, unique=True)
    region = models.ForeignKey(Region, related_name='regions', on_delete=models.CASCADE)
    age = models.PositiveIntegerField(default=0)
    completion_date = models.DateTimeField(blank=True, null=True)
    features = models.ManyToManyField(ComplexFeatures, blank=True, null=True)
    build_area = models.PositiveIntegerField(default=0)
    description = RichTextUploadingField(null=True, blank=True)
    # address = map_fields.AddressField(max_length=200)
    # geolocation = map_fields.GeoLocationField(max_length=100)

    def __str__(self):
        return self.name

    class Meta():
        verbose_name_plural = "Complexes"

class AssetFeatures(models.Model):
    features = models.CharField(max_length=150, unique=True)

    class Meta():
        verbose_name_plural = "Asset Features"

    def __str__(self):
        return self.features

class Bedroom(models.Model):
    number = models.PositiveIntegerField(unique=True)
    description = models.CharField(max_length=150, unique=True)

    def __str__(self):
        return self.description


class Asset(models.Model):
    complex = models.ForeignKey(Complex, related_name='complexes', on_delete=models.CASCADE)
    description = RichTextUploadingField(help_text='Full images can be 730px wide', null=True, blank=True)
    type = models.CharField(max_length=150, choices=ASSET_TYPES, default='FL')
    installment = models.BooleanField(choices=YES_NO_CHOICES, default=False)
    price = models.DecimalField(max_digits=15, decimal_places=0, default=0.0)
    furnished = models.BooleanField(choices=YES_NO_CHOICES, default=False)
    bedroom = models.ForeignKey(Bedroom, related_name='bedrooms', on_delete=models.CASCADE)
    bathroom = models.PositiveIntegerField(default=1)
    garage = models.PositiveIntegerField(default=1)
    floors = models.PositiveIntegerField()
    build_area = models.PositiveIntegerField(default=0)
    features = models.ManyToManyField(AssetFeatures, blank=True, null=True)
    featured = models.BooleanField(choices=YES_NO_CHOICES, default=False)
    active = models.BooleanField(choices=YES_NO_CHOICES, default=True)
    tag = models.CharField(max_length=50, choices=TAG_CHOICES, default='FS')
    image = models.ImageField(upload_to='baseApp/property/', null=True,
                                help_text='Thumbnail Image 1600x1200')
    title = models.CharField(max_length=150, default='Comfortable Apartment')
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    def __str__(self):
        return 'Reference: {}'.format(self.id)

    class Meta():
        ordering  = ['-created']

    def get_absolute_url(self):
        return reverse_lazy('baseApp:propertyView', args=(self.id,))

class AssetImages(models.Model):
    asset = models.ForeignKey(Asset, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='baseApp/property/', null=True,
                                help_text='Slide Image 1600x1100')
    display_order = models.PositiveIntegerField(null=True, blank=True)

    class Meta():
        verbose_name_plural = "Asset Images"
        ordering = ['display_order']


class Slide(models.Model):
    image = models.ImageField(upload_to='baseApp/slider/', blank=True, null=True,
                                help_text='Slider Image 1920x1280')
    title = models.CharField(max_length=110, default='Find Your Home')
    useFor = models.CharField(max_length=50, choices=PAGE_CHOICES, default='HOME')
    active = models.BooleanField(choices=YES_NO_CHOICES, default=False)

    def __str__(self):
            return self.title
