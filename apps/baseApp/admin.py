from django.contrib import admin
from django import forms
from django.db import models
from .models import (Country, City, Region,
                    Complex, Location, Distance,
                    ComplexFeatures,
                    Bedroom,
                    Asset, AssetImages, AssetFeatures,
                    FAQ, FAQCategories,
                    Slide)


class AssetImagesInline(admin.TabularInline):
    model = AssetImages
    list_display = ['asset', 'image', 'display_order']
    list_editable = ['display_order']
    # Read more https://docs.djangoproject.com/en/3.0/ref/contrib/admin/#modeladmin-methods
    # You may upload multiple images with one upload process and save the seperatly in the backend.
    # formfield_overrides = {
    #     models.ImageField: {'widget': forms.ClearableFileInput(attrs={'multiple': True})},
    # }

class AssetAdmin(admin.ModelAdmin):

    # search_fields = ['complex']
    list_filter = ['complex']
    list_display = ['id', 'created', 'type', 'active', 'featured', 'tag', 'complex', 'build_area', 'bedroom', 'price',]
    list_editable = ['active', 'featured']

    # other Inlines
    inlines = [
        AssetImagesInline,
    ]

    # Using Widgets
    formfield_overrides = {
        models.ManyToManyField: {'widget': forms.CheckboxSelectMultiple(attrs={'multiple': True})},
    }

class SlideAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'useFor', 'active']
    list_editable = ['title', 'useFor', 'active']

class RegionAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'city']

class AssetImagesAdmin(admin.ModelAdmin):
    list_display = ['asset', 'image']
    list_editable = ['image']

class DistanceInline(admin.TabularInline):
    model = Distance

class ComplexAdmin(admin.ModelAdmin):
    formfield_overrides = {
        models.ManyToManyField: {'widget': forms.CheckboxSelectMultiple(attrs={'multiple': True})},
        models.DateField: {'widget': forms.SelectDateWidget()},
    }
    # other Inlines
    inlines = [
        DistanceInline,
    ]


class FAQAdmin(admin.ModelAdmin):
    list_display = ['id', 'question', 'active']
    list_editable = ['active']
    search_fields = ['question']

    # Using Widgets
    formfield_overrides = {
        models.ManyToManyField: {'widget': forms.CheckboxSelectMultiple(attrs={'multiple': True})},
    }

class FAQCategoriesAdmin(admin.ModelAdmin):
    list_display = ['id', 'category', 'slug']
    prepopulated_fields = {"slug": ("category",)}



admin.site.register(AssetFeatures)
admin.site.register(City)
admin.site.register(Region, RegionAdmin)
admin.site.register(Complex, ComplexAdmin)
admin.site.register(ComplexFeatures)
admin.site.register(Location)
admin.site.register(Asset, AssetAdmin)
admin.site.register(FAQ, FAQAdmin)
admin.site.register(Slide, SlideAdmin)
admin.site.register(FAQCategories, FAQCategoriesAdmin)
# admin.site.register(AssetImages, AssetImagesAdmin)
# admin.site.register(Distance)
# admin.site.register(Bedroom)
# admin.site.register(Country)
