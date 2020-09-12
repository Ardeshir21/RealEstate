from django import forms
from phonenumber_field.formfields import PhoneNumberField
from django.core.mail import send_mail


class ContactForm(forms.Form):
    name = forms.CharField(max_length=100,
                            widget=forms.TextInput(attrs={'placeholder': 'نام شما',
                                                            'class': 'form-control'})
                            )
    message = forms.CharField(widget=forms.Textarea(attrs={'placeholder': 'متن پیام',
                                                            'class': 'form-control'}))
    client_email = forms.EmailField(
                                widget=forms.EmailInput(attrs={'placeholder': 'ایمیل',
                                                                'class': 'form-control'})
                                )
    client_phone = PhoneNumberField(required=False,
                                    widget=forms.TextInput(attrs={'placeholder': 'تلفن همراه',
                                                                    'class': 'form-control',
                                                                    'style': 'direction: ltr;'})
                                    )

    def send_email(self, current_url):
        name = self.cleaned_data['name']
        message = self.cleaned_data['message']
        client_email = self.cleaned_data['client_email']
        client_phone = self.cleaned_data['client_phone']
        recipients = ['contact@gammaturkey.com', client_email]
        mail_subject = 'Gamma Turkey Received Your Message - {}'.format(name)

        message_edited = '''{} عزیز،

از تماس شما با ما سپاس گذاریم.
پیام زیر با موفقیت به دست ما رسید. تیم گاما بزودی به شما تماس خواهند گرفت.

___________________________________________
آدرس فرم تماس با ما: {}
{} - شماره تلفن: {} - آدرس ایمیل {}

{}

___________________________________________
با تشکر
تیم مشاورین گاما
https://www.gammaturkey.com
'''
        message_edited = message_edited.format(name, current_url, name, client_phone, client_email, message)
        send_mail(mail_subject, message_edited, 'contact@gammaturkey.com', recipients)
        pass
