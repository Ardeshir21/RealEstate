from django import forms
from phonenumber_field.formfields import PhoneNumberField
from django.core.mail import send_mail


class ContactForm(forms.Form):
    name = forms.CharField(max_length=100,
                            widget=forms.TextInput(attrs={'placeholder': 'نام شما',
                                                            'class': 'form-control'})
                            )
    message = forms.CharField(widget=forms.Textarea(attrs={'placeholder': 'پیغام شما',
                                                            'class': 'form-control'}))
    sender_email = forms.EmailField(
                                widget=forms.EmailInput(attrs={'placeholder': 'someone@example.com',
                                                                'class': 'form-control',
                                                                'style': 'direction: ltr;'})
                                )
    sender_phone = PhoneNumberField(required=False,
                                    widget=forms.TextInput(attrs={'placeholder': '+989123456789',
                                                                    'class': 'form-control',
                                                                    'style': 'direction: ltr;'})
                                    )

    cc_myself = forms.BooleanField(required=False)

    def send_email(self):
        name = self.cleaned_data['name']
        message = self.cleaned_data['message']
        sender_email = self.cleaned_data['sender_email']
        sender_phone = self.cleaned_data['sender_phone']
        cc_myself = self.cleaned_data['cc_myself']
        recipients = ['examples21@gmail.com']
        if cc_myself:
            recipients.append(sender_email)

        # send_mail('HELLO', message, sender_email, recipients)
        pass
