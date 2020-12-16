from django.contrib import admin
from django import forms
from django.db import models
from django.contrib.admin.widgets import AdminDateWidget
from .models import (RequestedLinks, CurrencyRate, SalesParameter)



class RequestedLinksAdmin(admin.ModelAdmin):
    list_display = ['url', 'client_ip']

class CurrencyRateAdmin(admin.ModelAdmin):
    list_display = ['date', 'rate_TurkishLira']

class SalesParameterAdmin(admin.ModelAdmin):
    list_display = ['date', 'pricePerKilo', 'margin_percent']



admin.site.register(RequestedLinks, RequestedLinksAdmin)
admin.site.register(CurrencyRate, CurrencyRateAdmin)
admin.site.register(SalesParameter, SalesParameterAdmin)
