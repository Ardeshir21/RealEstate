from django.db import models
from django.urls import reverse_lazy, reverse
from ckeditor_uploader.fields import RichTextUploadingField
from django.utils import timezone

# Customer field
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
    created_on = models.DateField(editable=False)

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
    created_on = models.DateField(editable=False)

    def save(self, *args, **kwargs):
        if not self.id:
            self.created_on = timezone.now()
        return super(SalesParameter, self).save(*args, **kwargs)

    class Meta():
        verbose_name_plural = "Sales Parameters"
        ordering = ['-date']
