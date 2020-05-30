from django.contrib import admin
from django import forms
from django.db import models
from django_google_maps import widgets as map_widgets
from django_google_maps import fields as map_fields
from .models import (Country, City, Region,
                    Complex, ComplexFeatures,
                    Bedroom,
                    Asset, AssetImages, AssetFeatures,
                    Slide)


class AssetImagesInline(admin.TabularInline):
    model = AssetImages

    # Read more https://docs.djangoproject.com/en/3.0/ref/contrib/admin/#modeladmin-methods
    # You may upload multiple images with one upload process and save the seperatly in the backend.
    # formfield_overrides = {
    #     models.ImageField: {'widget': forms.ClearableFileInput(attrs={'multiple': True})},
    # }


class AssetAdmin(admin.ModelAdmin):

    # search_fields = ['complex']
    list_filter = ['complex']
    list_display = ['id', 'created', 'bedroom', 'active', 'build_area', 'tag', 'featured', 'type', 'complex', 'price',]
    list_editable = ['active', 'bedroom', 'featured', 'build_area', 'tag', 'price']

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

class ComplexAdmin(admin.ModelAdmin):
    formfield_overrides = {
        map_fields.AddressField: {'widget': map_widgets.GoogleMapsAddressWidget},
        models.ManyToManyField: {'widget': forms.CheckboxSelectMultiple(attrs={'multiple': True})},
    }

admin.site.register(Country)
admin.site.register(AssetFeatures)
admin.site.register(City)
admin.site.register(Region, RegionAdmin)
admin.site.register(Complex, ComplexAdmin)
admin.site.register(ComplexFeatures)
admin.site.register(Bedroom)
admin.site.register(Asset, AssetAdmin)
admin.site.register(Slide, SlideAdmin)
admin.site.register(AssetImages, AssetImagesAdmin)
