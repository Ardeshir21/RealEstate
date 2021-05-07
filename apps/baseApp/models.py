from django.db import models
from django.urls import reverse_lazy, reverse
from ckeditor_uploader.fields import RichTextUploadingField
from django.utils import timezone

# Variables
YES_NO_CHOICES = [(True, 'Yes'), (False, 'No')]

LANGUAGE_LIST = [
    ('EN',"English"),
    ('FA',"Farsi")
]

ASSET_TYPES = [('FL', 'Flat'),
                ('DF', 'Dublex Flat'),
                ('VI', 'Villa'),
                ('OF', 'Office'),
                ('ST', 'Store')]

TAG_CHOICES = [('FS', 'For Sale'),
                ('FR', 'For Rent')]

HEATING_TYPES = [('CE', 'Central'),
                ('CO', 'Combi')]

COMPLEX_FEATURES_CATEGORY = [('TOP', 'Top'),
                            ('GENERAL', 'General'),
                            ('TECHNICAL', 'Technical'),
                            ('SPORT', 'Sport')
                            ]

MEASURE_TYPES = [('K', 'KM'),
                ('ME', 'METER'),
                ('S', 'STEP'),
                ('M', 'MIN')]

MEASURE_TYPES_FA = {'K': 'کیلومتر',
                    'ME': 'متر',
                    'S': 'قدم',
                    'M': 'دقیقه'}

PAGE_CHOICES = [('HOME', 'Homepage'),
                ('PROPERTY_SEARCH', 'Property Search'),
                ('BLOG_HOME', 'Blog Homepage'),
                ('BLOG_SEARCH', 'Blog Search'),
                ('BLOG_CATEGORY', 'Blog Categories'),
                ('BLOG_POST', 'Blog Post'),
                ('STORE_HOME', 'Store Home'),
                ('FAQ_PAGE', 'FAQ Page'),
                ('FAQ_SEARCH', 'FAQ Search')]
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
    name = models.CharField(max_length=150, unique=True)
    name_FA = models.CharField(max_length=150, unique=True, null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta():
        verbose_name_plural = "Cities"

class Region(models.Model):

    city = models.ForeignKey(City, related_name='cities', on_delete=models.CASCADE)
    name = models.CharField(max_length=150, unique=True)
    description = RichTextUploadingField(null=True, blank=True)
    description_FA = RichTextUploadingField(null=True, blank=True)

    def __str__(self):
        return self.name

class Location(models.Model):
    name = models.CharField(max_length=150, unique=True)
    name_FA = models.CharField(max_length=150, unique=True, blank=True, null=True)
    icon_code = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.name

class ComplexFeatures(models.Model):
    category = models.CharField(max_length=150, choices=COMPLEX_FEATURES_CATEGORY, default='GENERAL')
    features = models.CharField(max_length=150, unique=True)
    features_FA = models.CharField(max_length=150, unique=True, null=True, blank=True)

    class Meta():
        verbose_name_plural = "Complex Features"
        ordering = ['category', 'features']

    def __str__(self):
        return '{}: {}'.format(self.category, self.features)

class Complex(models.Model):

    name = models.CharField(max_length=150, unique=True)
    hide_name = models.BooleanField(choices=YES_NO_CHOICES, default=False)
    region = models.ForeignKey(Region, related_name='regions', on_delete=models.CASCADE)
    age = models.PositiveIntegerField(default=0)
    completion_date = models.DateField(blank=True, null=True)
    features = models.ManyToManyField(ComplexFeatures, blank=True, null=True)
    build_area = models.PositiveIntegerField(default=0)
    location_id = models.CharField(max_length=150, default='ChIJawhoAASnyhQR0LABvJj-zOE',
                                help_text="https://developers.google.com/places/place-id")

    description = RichTextUploadingField(null=True, blank=True)
    description_FA = RichTextUploadingField(null=True, blank=True)
    near_locations = models.ManyToManyField(Location, through='Distance', blank=True, null=True)


    def __str__(self):
        return self.name

    class Meta():
        verbose_name_plural = "Complexes"
        ordering  = ['name']

class Distance(models.Model):
    location = models.ForeignKey(Location, on_delete=models.CASCADE)
    complex = models.ForeignKey(Complex, related_name='distances', on_delete=models.CASCADE)
    distance = models.DecimalField(max_digits=6, decimal_places=0, default=1.0)
    measure = models.CharField(max_length=10, choices=MEASURE_TYPES, default='K')
    measure_FA = models.CharField(max_length=10, blank=True, null=True)

    def __str__(self):
        return '{} to {}: {} {}'.format(self.complex,self.location, self.distance, self.measure)

    def save(self, *args, **kwargs):
            self.measure_FA = MEASURE_TYPES_FA[self.measure]
            super(Distance, self).save(*args, **kwargs)

    class Meta():
        verbose_name_plural = "Distances"

class AssetFeatures(models.Model):
    features = models.CharField(max_length=150, unique=True)
    features_FA = models.CharField(max_length=150, unique=True, null=True, blank=True)

    class Meta():
        verbose_name_plural = "Asset Features"

    def __str__(self):
        return self.features

class Bedroom(models.Model):
    number = models.PositiveIntegerField(unique=True)
    description = models.CharField(max_length=150, unique=True)
    description_FA = models.CharField(max_length=150, unique=True, null=True, blank=True)

    def __str__(self):
        return self.description

class Asset(models.Model):
    complex = models.ForeignKey(Complex, related_name='complexes', on_delete=models.CASCADE)
    description = RichTextUploadingField(help_text='Full images can be 730px wide', null=True, blank=True)
    description_FA = RichTextUploadingField(help_text='Full images can be 730px wide', null=True, blank=True)
    type = models.CharField(max_length=15, choices=ASSET_TYPES, default='FL')
    installment = models.BooleanField(choices=YES_NO_CHOICES, default=False)
    base_price = models.DecimalField(max_digits=15, decimal_places=0, default=0.0)
    price = models.DecimalField(max_digits=15, decimal_places=0, default=0.0)
    rental_income = models.PositiveIntegerField(default=0,
                                                help_text="(For Sale): Rental Income or (For Rent): Deposit")
    dues = models.DecimalField(max_digits=5, decimal_places=0, default=0.0)
    furnished = models.BooleanField(choices=YES_NO_CHOICES, default=False)
    bedroom = models.ForeignKey(Bedroom, related_name='bedrooms', on_delete=models.CASCADE)
    bathroom = models.PositiveIntegerField(default=1)
    heating_type = models.CharField(max_length=10, choices=HEATING_TYPES, default='CE')
    garage = models.PositiveIntegerField(default=1)
    floor = models.PositiveIntegerField()
    build_area = models.PositiveIntegerField(default=0)
    build_area_gross = models.PositiveIntegerField(default=0)
    features = models.ManyToManyField(AssetFeatures, blank=True, null=True)
    featured = models.BooleanField(choices=YES_NO_CHOICES, default=False)
    active = models.BooleanField(choices=YES_NO_CHOICES, default=True)
    tag = models.CharField(max_length=50, choices=TAG_CHOICES, default='FS')
    image = models.ImageField(upload_to='baseApp/property/', null=True,
                                help_text='Thumbnail Image 1600x1200')
    title = models.CharField(max_length=150, default='Comfortable Apartment')
    title_FA = models.CharField(max_length=150, default='آپارتمانی راحت', blank=True, null=True)
    created = models.DateField(editable=False)
    updated = models.DateField(editable=False, null=True)

    def __str__(self):
        return 'Reference: {}'.format(self.id)

    class Meta():
        ordering  = ['-created']

    def save(self, *args, **kwargs):
        ''' On save, update timestamps '''
        if not self.id:
            self.created = timezone.now()
        self.updated = timezone.now()
        return super(Asset, self).save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('baseApp:propertyView', args=(self.id,))

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
    title_FA = models.CharField(max_length=110, default='خانه خود را پیدا کن', null=True, blank=True)
    useFor = models.CharField(max_length=50, choices=PAGE_CHOICES, default='HOME')
    active = models.BooleanField(choices=YES_NO_CHOICES, default=False)

    def __str__(self):
            return self.title

class FAQCategories(models.Model):
    category = models.CharField(max_length=100, unique=True)
    category_lang = models.CharField(max_length=10, choices=LANGUAGE_LIST, default='EN')
    icon_code = models.CharField(max_length=100, blank=True, null=True)
    slug = models.SlugField(max_length=150, unique=True, blank=True, null=True, allow_unicode=True,
                                help_text="The name of the page as it will appear in URLs e.g http://domain.com/FAQ/[category-slug]/")
    class Meta():
        verbose_name_plural = "FAQ Categories"
        ordering = ['category']

    def __str__(self):
        return self.category

    def save(self, *args, **kwargs):
        ##### Because of FA language I use the blogApp/Admin.py to make slug.
        # self.slug = slugify(self.category)
        return super(FAQCategories, self).save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('baseApp:faq', args=[self.slug])

class FAQ(models.Model):
    language = models.CharField(max_length=20, choices=LANGUAGE_LIST, default='EN')
    categories = models.ManyToManyField(FAQCategories, through='FAQPriority', related_name='categories', null=True)
    question = models.CharField(max_length=300, unique=True)
    answer = RichTextUploadingField(help_text='Full images can be 730px wide', null=True, blank=True)
    active = models.BooleanField(choices=YES_NO_CHOICES, default=True)
    created = models.DateField(editable=False)
    updated = models.DateField(editable=False)

    def __str__(self):
            return self.question

    class Meta():
        verbose_name_plural = "FAQs"


    def save(self, *args, **kwargs):
        ''' On save, update timestamps '''
        if not self.id:
            self.created = timezone.now()
        self.updated = timezone.now()
        return super(FAQ, self).save(*args, **kwargs)

# This class is for "through" relation model in FAQ model
class FAQPriority(models.Model):
    category = models.ForeignKey(FAQCategories, on_delete=models.CASCADE)
    question = models.ForeignKey(FAQ, related_name='priorities', on_delete=models.CASCADE)
    priority = models.PositiveSmallIntegerField(default=100)

    def __str__(self):
        return 'Question Place is: {}'.format(self.priority)

    class Meta():
        verbose_name_plural = "FAQ Priorities"
        db_table = "baseApp_faq_categories"
        ordering = ['priority']
