from django import forms
from phonenumber_field.formfields import PhoneNumberField
from django.core.mail import send_mail


class ContactForm(forms.Form):
    name = forms.CharField(max_length=100,
                            widget=forms.TextInput(attrs={'placeholder': 'Your Name',
                                                            'class': 'form-control'})
                            )
    message = forms.CharField(widget=forms.Textarea(attrs={'placeholder': 'Your Message',
                                                            'class': 'form-control'}))
    client_email = forms.EmailField(
                                widget=forms.EmailInput(attrs={'placeholder': 'someone@example.com',
                                                                'class': 'form-control'})
                                )
    client_phone = PhoneNumberField(required=False,
                                    widget=forms.TextInput(attrs={'placeholder': '+905356832320',
                                                                    'class': 'form-control'})
                                    )

    def send_email(self, current_url):
        name = self.cleaned_data['name']
        message = self.cleaned_data['message']
        client_email = self.cleaned_data['client_email']
        client_phone = self.cleaned_data['client_phone']
        recipients = ['contact@gammaturkey.com', client_email]
        mail_subject = 'Gamma Turkey Received Your Message - {}'.format(name)

        message_edited = '''Dear {},

Many thanks for contacting us.
We have successfully received your below message. Our team will contact you shortly.

___________________________________________
The URL address of the form: {}
{} - Phone Number: {} - eMail Address: {}

{}

___________________________________________
Kind Regards,
Gamma Turkey team
https://www.gammaturkey.com
'''
        message_edited = message_edited.format(name, current_url, name,client_phone, client_email, message)
        send_mail(mail_subject, message_edited, 'contact@gammaturkey.com', recipients)
        pass
