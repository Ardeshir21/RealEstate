from django import forms
from . import models

# Not using this form, because the Admin page form is enough for property entry
class createAssetForm(forms.ModelForm):
    class Meta():
        model= models.Asset
        fields = '__all__'
        widgets = {
                'tag': forms.RadioSelect,
        }
