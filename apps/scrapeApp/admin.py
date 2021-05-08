from django.contrib import admin
from django import forms
from django.db import models
from django.contrib.admin.widgets import AdminDateWidget
from .models import (RequestedLinks, CurrencyRate, SalesParameter,
                        Store, Product, ProductImagesUrls, ProductSizeVariants, ProductBrand)



class RequestedLinksAdmin(admin.ModelAdmin):
    list_display = ['url', 'client_ip']

class CurrencyRateAdmin(admin.ModelAdmin):
    list_display = ['date', 'rate_TurkishLira']

class SalesParameterAdmin(admin.ModelAdmin):
    list_display = ['date', 'pricePerKilo', 'margin_percent']

class StoreAdmin(admin.ModelAdmin):
    list_display = ['name', 'website_url']
    prepopulated_fields = {'slug': ('name',)}

class ProductBrandAdmin(admin.ModelAdmin):
    list_display = ['name']

class ProductImagesUrlsInline(admin.TabularInline):
    model = ProductImagesUrls
    list_display = ['product', 'image_tag', 'active', 'display_order']
    list_editable = ['display_order']
    readonly_fields = ['image_tag']

class ProductSizeVariantsInline(admin.TabularInline):
    model = ProductSizeVariants
    list_display = ['product', 'size', 'active']

class ProductAdmin(admin.ModelAdmin):
    list_display = ['id', 'store', 'image_tag', 'weight_category', 'main_url', 'updated_on']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['image_tag']
    search_fields = ['id', 'store__name']
    # other Inlines
    inlines = [
        ProductSizeVariantsInline,
        ProductImagesUrlsInline,
    ]

admin.site.register(RequestedLinks, RequestedLinksAdmin)
admin.site.register(CurrencyRate, CurrencyRateAdmin)
admin.site.register(SalesParameter, SalesParameterAdmin)
admin.site.register(Store, StoreAdmin)
admin.site.register(ProductBrand, ProductBrandAdmin)
admin.site.register(Product, ProductAdmin)
