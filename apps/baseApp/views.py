from django.shortcuts import render
from django.utils import timezone
from django.views import generic
from django.conf import settings
from . import models, forms
from apps.blogApp import models as blogAppModel
from django.db.models import Max, Min, Q
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.http import HttpResponse, JsonResponse
from django.core import serializers
import json
import io
import xlsxwriter
import openai
import asyncio
import telegram
from django.utils.decorators import method_decorator
import requests
from django.views.decorators.csrf import csrf_exempt



# Here is the Extra Context ditionary which is used in get_context_data of Views classes
def get_extra_context():
    extraContext = {
        'DEBUG_VALUE': settings.DEBUG,
        'regions': models.Region.objects.filter(regions__complexes__active=True).distinct(),
        'propertyTypeNames': set([obj.get_type_display() for obj in models.Asset.objects.all()]),
        'tagType': set([obj.get_tag_display() for obj in models.Asset.objects.all()]),
        'bedroomNumbers': models.Bedroom.objects.order_by('number'),
        'spaceRange': models.Asset.objects.filter(active=True).aggregate(Min('build_area'), Max('build_area')),
        # ********for later expansion*********
        # context['priceRangeRent'] = models.Asset.objects.filter(tag__exact='FR').aggregate(Min('price'), Max('price'))
        'priceRange': models.Asset.objects.filter(active=True).aggregate(Min('price'), Max('price')),
        # Featured part of the page
        'featuredProperties': models.Asset.objects.filter(active=True, featured=True),
        # Blog models with EN language and being Featured filter
        'blogPosts': blogAppModel.Post.objects.filter(status=True, language='EN', featured=True),
        # Blog Categories with EN language filter
        'blogCategories': blogAppModel.PostCategories.objects.filter(category_lang='EN').exclude(pk__in=[14, 28, 29]),
        # Item for Navbar from Blog CategoryListView
        'blogCategoriesNav': blogAppModel.PostCategories.objects.filter(category_lang='EN', pk__in=[14, 28, 29]),
        # Apartments Unqiue names
        'apartments': models.Complex.objects.filter(hide_name=False),
        # Default page for FAQ section.
        'navbar_FAQ': 'all'
        }
    return extraContext

# Index View
class IndexView(generic.ListView):
    context_object_name = 'assets_all'
    template_name = 'baseApp/index.html'
    model = models.Asset

    def get_queryset(self):
        result = super(IndexView, self).get_queryset()

        # Filter all inactive assets at the beginning.
        result = result.filter(active=True)
        return result

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        # Append shared extraContext
        context.update(get_extra_context())
        context['slideContent'] = models.Slide.objects.filter(useFor__exact='HOME', active__exact=True)
        return context

# Search Box - searchResult.html
class AssetFilterView(generic.ListView):
    context_object_name = 'assets_filtered'
    model = models.Asset
    template_name = 'baseApp/property_list.html'
    paginate_by = 9

    def get_queryset(self):
        result = super(AssetFilterView, self).get_queryset()

        # Filter all inactive assets at the beginning.
        result = result.filter(active=True)

        # Get Requests
        region_query = self.request.GET.getlist('region_select') # value=[list of marked regions]
        propertyType_query = self.request.GET.getlist('propertyType_select')
        bedroom_query = self.request.GET.getlist('bedroom_select') # value=[0, 1, 3]
        tag_query = self.request.GET.get('tag_select') # value='sale'
        price_query = self.request.GET.getlist('price_select') # value=[minValue, MaxValue]
        space_query = self.request.GET.getlist('space_select') # value=[minValue, MaxValue]
        orderby_query = self.request.GET.get('sort')
        reference_query = self.request.GET.getlist('ref_select')
        apartment_query = self.request.GET.getlist('apartment_select')
        installment_query = self.request.GET.get('installment_select')

        # CONVERT some Queries
        # Convert the property type into model Format ('FL', 'Flat')
        # in queries you will use short formats i.e. 'FL'
        edited_propertyType = []
        for type in propertyType_query:
            for t in models.ASSET_TYPES:
                if type == t[1]:
                    edited_propertyType.append(t[0])
                    break
        propertyType_query = edited_propertyType

        # Process the Reference Codes to match with database pk
        edited_reference = []
        for r in reference_query:
            edited_reference.append(r[6:])
        reference_query = edited_reference

        # FILTERs based on queries
        # Regions
        if not(region_query==None or region_query=='' or region_query==[]):
            # First build the list of all OR queries
            ### another method is:
            ### from functools import reduce
            ### from operator import or_
            ### query = reduce(or_, (Q(type__type=t) for t in types))
            ### projects.filter(query)
            # You need to build a Q with the first item and add other Qs to the tempQuery
            tempQuery = Q(complex__region__pk=int(region_query[0]))
            for regionId in region_query[1:]:
                tempQuery |= Q(complex__region__pk=int(regionId))
            result = result.filter(tempQuery)

        # Property Types
        if not(propertyType_query==[] or propertyType_query=='' or propertyType_query==None):
            tempQuery = Q(type=propertyType_query[0])
            for propertytype in propertyType_query[1:]:
                tempQuery |= Q(type=propertytype)
            result = result.filter(tempQuery)

        # Apartment Names
        if not(apartment_query==[] or apartment_query=='' or apartment_query==None):
            tempQuery = Q(complex__id=int(apartment_query[0]))
            for apartment in apartment_query[1:]:
                tempQuery |= Q(complex__id=int(apartment))
            result = result.filter(tempQuery)

        # Reference Code
        if not(reference_query==[] or reference_query=='' or reference_query==None):
            tempQuery = Q(pk=int(reference_query[0]))
            for ref in reference_query[1:]:
                tempQuery |= Q(pk=int(ref))
            # print(tempQuery)
            result = result.filter(tempQuery)

        # Installment
        if not(installment_query=='' or installment_query==None):
            if (installment_query=='1'):
                result = result.filter(installment__exact=True)

        # Bedrooms
        if not(bedroom_query=='' or bedroom_query==None or bedroom_query==[]):
            # You need to build a Q with the first item and add other Qs to the tempQuery
            tempQuery = Q(bedroom__number=int(bedroom_query[0]))
            for bedroomNo in bedroom_query[1:]:
                tempQuery |= Q(bedroom__number=int(bedroomNo))
            result = result.filter(tempQuery)

        # Tag Deal
        # Using "Ordering" on the Properties Page will cause this filter to be implemented by Sale or Rent values.
        # First check if the Queryset is less than 3 items. (only "sort" and "page" request are generated by OrderBy button )
        if not(tag_query=='' or tag_query==None):
            if (tag_query=='sale'):
                result = result.filter(tag__exact='FS')
            elif (tag_query=='rent'):
                result = result.filter(tag__exact='FR')
            else: pass

        # Price
        if not(price_query=='' or price_query==None or price_query==[]):
            if not(price_query[0]==''):
                result = result.filter(price__gte=float(price_query[0]), price__lte=float(price_query[1]))

        # Space Area
        if not(space_query=='' or space_query==None or space_query==[]):
            if not(space_query[0]==''):
                result = result.filter(build_area__gte=float(space_query[0]), build_area__lte=float(space_query[1]))

        # Order By (it should be the last thing in query section of this code)
        if not(orderby_query=='' or orderby_query==None):
            if orderby_query == 'price-ascending':
                result =  result.order_by('price')
            if orderby_query == 'price-descending':
                result =  result.order_by('-price')
            if orderby_query == 'date-newest':
                result =  result.order_by('-created')
            if orderby_query == 'date-oldest':
                result =  result.order_by('created')
        return result


    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        # Append extraContext
        context.update(get_extra_context())

        # result count
        context['resultCount'] = len(self.get_queryset())
        # An slide picture for Search Result page. This need just one slide >> id= ?
        context['slideContent'] = models.Slide.objects.get(useFor__exact='PROPERTY_SEARCH', active__exact=True)
        context['pageTitle'] = 'PROPERTIES'
        context['assets_all'] = models.Asset.objects.filter(active=True)

        # Building a dictionary of GET request with nice words in order to present them in the search result page.
        # The reason for this line of code is to convert the [1,2,3,4,...] region_select to its real region names from Model
        if not(self.request.GET.getlist('region_select')==[] or self.request.GET.getlist('region_select')==None):
            regions_pks = self.request.GET.getlist('region_select')
            regionRequest = []
            for pk in regions_pks:
                regionRequest.append(models.Region.objects.get(pk=pk).name)
        else: regionRequest = 'no filter'

        # The reason for this line of code is to convert the [0,1,2,3,4,...] room_select to its descrptions from Model
        if not(self.request.GET.getlist('bedroom_select')==[] or self.request.GET.getlist('bedroom_select')==None):
            bedroom_codes = self.request.GET.getlist('bedroom_select')
            bedroomRequest = []
            for num in bedroom_codes:
                bedroomRequest.append(models.Bedroom.objects.get(number=num).description)
        else: bedroomRequest = 'no filter'

        # check if the Price slider is empty
        if not(self.request.GET.getlist('price_select')==[] or self.request.GET.getlist('price_select')==None):
            priceRequest = {'min': self.request.GET.getlist('price_select')[0],
                            'max': self.request.GET.getlist('price_select')[1]}
        else: priceRequest = 'no filter'

        # check if the Space slider is empty
        if not(self.request.GET.getlist('space_select')==[] or self.request.GET.getlist('space_select')==None):
            spaceRequest = {'min': self.request.GET.getlist('space_select')[0],
                            'max': self.request.GET.getlist('space_select')[1]}
        else: spaceRequest = 'no filter'

        # Just to check if the request is empty, returns 'no filter'
        if not(self.request.GET.get('tag_select')==[] or self.request.GET.get('tag_select')==None):
            dealRequest = self.request.GET.get('tag_select')
        else: dealRequest = 'no filter'

        # Just to check if the request is empty, returns 'no filter'
        if not(self.request.GET.getlist('propertyType_select')==[] or self.request.GET.getlist('propertyType_select')==None):
            typeRequest = set(self.request.GET.getlist('propertyType_select'))
        else: typeRequest = 'no filter'

        # Put all the above cleaned Requested items into one dictionary to use in Template context
        Qdetail_dict = {
                        'QdealType': dealRequest,
                        'Qregions': regionRequest,
                        'QpropertyTypes': typeRequest,
                        'Qprices': priceRequest,
                        'Qspace': spaceRequest,
                        'Qroom': bedroomRequest,
                        }

        context['Qdetail'] = Qdetail_dict

        # context['test'] = models.Asset.objects.values_list('bedroom', flat=True).distinct().order_by('bedroom')

        return context

# The Single Property View, it is used with FormMixin to render a form inside this DetailView
class AssetSingleView(generic.edit.FormMixin, generic.DetailView):
    # Because this is a DetailView, it will use get() method on the model and return only the property with requested pk
    context_object_name = 'property'
    template_name = 'baseApp/property_detail.html'
    model = models.Asset

    # This is for Form
    form_class = forms.ContactForm
    def get_success_url(self):
            return reverse('baseApp:propertyView', kwargs={'pk': self.object.pk})


    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        # Append extraContext
        context.update(get_extra_context())
        # Using the same image as the Asset has for its thumbnail
        context['slideContent'] = self.get_object()
        # context['slideContent'] = models.Slide.objects.get(useFor__exact='PROPERTY_PAGE', active__exact=True)
        context['assets_all'] = models.Asset.objects.all()
        context['form'] = self.get_form()
        # Categorize the features to be used in template
        # create a dictionary of Categories with a list of related features
        complex_features = {}
        categories = [i['category'] for i in self.object.complex.features.values('category')]
        for category in categories:
            complex_features[category] = [i['features'] for i in self.object.complex.features.values('features').filter(category=category)]
        # this value is a dictionary itself >>> {'GENERAL': ['Elevator'], 'SPORT': ['Gym', 'Pool'], 'TOP': ['Supermarket']}
        context['apartment_features'] = complex_features
        return context

    # Form POST
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        # This for success message. See Django Documentation
        messages.add_message(self.request, messages.SUCCESS, 'Your message has been successfully sent.')
        # This is a custom function in forms.py
        # It may also work:      current_url = resolve(request.path_info).url_name
        form.send_email(current_url=self.request.build_absolute_uri())
        return super(AssetSingleView, self).form_valid(form)

# About Us
class ContactView(generic.edit.FormView):
    template_name = 'baseApp/about_us.html'
    form_class = forms.ContactForm
    success_url = reverse_lazy('baseApp:about_us')

    def form_valid(self, form):
        # This for success message. See Django Documentation
        messages.add_message(self.request, messages.SUCCESS, 'Your message has been successfully sent.')
        # This method is called when valid form data has been POSTed.
        # current_url = resolve(request.path_info).url_name
        form.send_email(current_url=self.request.build_absolute_uri())
        return super().form_valid(form)

    # Calls get_form() and adds the result to the context data with the name ‘form’.
    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        # Append extraContext
        context.update(get_extra_context())
        context['slideContent'] = models.Slide.objects.get(useFor__exact='ABOUT_US', active__exact=True)
        context['pageTitle'] = 'ABOUT US'
        return context

# FAQ - faq-category.html
# The FAQ part has only a List of questions per category.
class FAQCategoryView(generic.ListView):

    context_object_name = 'questions'
    model = models.FAQ
    template_name = 'baseApp/faq-category.html'

    def get_queryset(self, **kwargs):
        result = super(FAQCategoryView, self).get_queryset()

        # Categories -- For filtering based on the categories
        # Related_name used for order_by
        result= result.filter(language='EN', categories__slug=self.kwargs['category'], active=True).order_by('priorities')
        return result

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        # Append extraContext
        context.update(get_extra_context())

        # Get current category Model Object
        context['slideContent'] = models.Slide.objects.get(useFor__exact='FAQ_PAGE', active__exact=True)
        context['pageTitle'] = ''
        # All category objects filtered by Language
        context['all_categories'] = models.FAQCategories.objects.filter(category_lang='EN')
        # Structred Questions - This for making structured data in templates
        # The problem is to use the last Item of queryset without comma
        currentQueryset = self.get_queryset()
        currentQuerysetCount = len(currentQueryset)
        if currentQuerysetCount > 0:
            context['excludedLastQuestion'] = currentQueryset[:currentQuerysetCount-1]
            context['lastQuestion'] = currentQueryset[currentQuerysetCount-1]
        # This is for Title Tag in the head section of the html
        if self.kwargs['category'] == 'all':
            context['titleTag'] = models.FAQCategories.objects.get(id=1)
        else:
            context['titleTag'] = models.FAQCategories.objects.get(slug=self.kwargs['category'])
        return context

    # This is for AJAX call -- We ignore using AJAX because of Google Crawling and SEO
    def post(self, request, *args, **kwargs):
        questions_query = self.get_queryset()
        return render(request, 'baseApp/includes/questions.html', {'questions': questions_query})

class FAQSearch(generic.ListView):
    context_object_name = 'questions'
    template_name = 'baseApp/faq-category.html'
    model = models.FAQ
    paginate_by = 15

    def get_queryset(self, **kwargs):
        result = super(FAQSearch, self).get_queryset()

        # Get the GET content >>> name='s'
        keyword = self.request.GET.get('s')
        if not(keyword==None or keyword==''):
            # Content Search -- For filtering based on the Text Search
            result= result.filter(Q(question__icontains=keyword) | Q(answer__icontains=keyword), language='EN', active=True).order_by('-created')

        return result

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        # Append extraContext
        context.update(get_extra_context())

        # Get current category Model Object
        context['slideContent'] = models.Slide.objects.get(useFor__exact='FAQ_SEARCH', active__exact=True)
        context['pageTitle'] = 'SEARCH FAQ'
        context['FAQCategory'] = 'Search Result for: "{}"'.format(self.request.GET.get('s'))
        # All category objects filtered by Language
        context['all_categories'] = models.FAQCategories.objects.filter(category_lang='EN')
        return context


class ExcelOutputAssets(generic.View):

    def get(self, request):

        # Create an in-memory output file for the new workbook.
        output = io.BytesIO()

        # Even though the final file will be in memory the module uses temp
        # files during assembly for efficiency. To avoid this on servers that
        # don't allow temp files, for example the Google APP Engine, set the
        # 'in_memory' Workbook() constructor option as shown in the docs.
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet()

        # Get some data to write to the spreadsheet.
        column_names = ['ID', 'Created Date', 'Region', 'Complex', 'Bedroom',
          'Price', 'Base Price',
          'Build Area']

        data = models.Asset.objects.all().values_list('id', 'created', 'complex__region__name',
          'complex__name', 'bedroom__description',
          'price', 'base_price',
          'build_area')

        # Write the titles
        for col in range(0, len(column_names)):
            worksheet.write(0, col, column_names[col])
        # Write some test data.
        for row_num, columns in enumerate(data, start=1):
            for col_num, cell_data in enumerate(columns):
                worksheet.write(row_num, col_num, cell_data)

        # Close the workbook before sending the data.
        workbook.close()

        # Rewind the buffer.
        output.seek(0)

        # Set up the Http response.
        filename = 'assets-{}.xlsx'.format(timezone.now().date())
        response = HttpResponse(
            output,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename=%s' % filename

        return response




############################################################
# AJAX TEST
class AJAX_TEST(generic.TemplateView):
    template_name = 'baseApp/test-AJAX.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        ss = {'name': 'My Cake',
                'type': 'Recipe',
                'author_type': 'Person',
                'author_name': 'Parisa',
                'description': 'This is a description for Cake!!!'
        }

        context['structredData'] = ss
        return context


# Error Pages
def error_404(request, exception):
        data = {}
        # The html file should be in templates folder not the subfolders
        return render(request,'baseApp/404.html', data)

def error_500(request):
        data = {}
        # The html file should be in templates folder not the subfolders
        return render(request,'baseApp/500.html', data)

# FORMS are here
# from . import forms

# Not using this form, because the Admin page form is enough for property entry
# class AssetCreateForm(generic.edit.CreateView):
#     template_name = 'baseApp/createAsset.html'
#     form_class = forms.createAssetForm
#     # success_url = reverse_lazy('baseApp:index')
#
#     def form_valid(self, form):
#         # This method is called when valid form data has been POSTed.
#         # It should return an HttpResponse.
#         form.save()
#         return super().form_valid(form)

# for handling multiple files
    # def post(self, request, *args, **kwargs):
    #     form_class = self.get_form_class()
    #     form = self.get_form(form_class)
    #     files = request.FILES.getlist('file_field')
    #     if form.is_valid():
    #         for f in files:
    #             ...  # Do something with each file.
    #         return self.form_valid(form)
    #     else:
    #         return self.form_invalid(form)



# Chatbot
class ChatbotView(generic.TemplateView):
    template_name = 'baseApp/chat_gpt.html'

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        # Append extraContext
        context.update(get_extra_context())
        context['slideContent'] = models.Slide.objects.get(useFor__exact='ABOUT_US', active__exact=True)
        context['pageTitle'] = 'ASK ME'
        return context

    def post(self, request):

        # Get the user's message from the query string
        message = request.POST.get('message', '')

        # Get the current chat log from the cookie
        chat_log = request.COOKIES.get('chat_log')
        if chat_log:
            chat_log = json.loads(chat_log)
        else:
            chat_log = [{"role": "system", "content": "You are a helpful assistant."}]

        # Initialize the OpenAI API client
        client = openai.OpenAI(api_key=settings.CHATGPT_API,)

        # Create a new chat completion if there is no previous chat log
        if not chat_log:
            bot_response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                # prompt=message,
                temperature=0.8,
                max_tokens=3000,
                messages=chat_log,
            )
            chat_log.append({"role": "user", "content": message})
            chat_log.append({"role": "system", "content": bot_response.choices[0].message.content})
        else:
            chat_log[-1]["role"] = "user"
            chat_log[-1]["content"] = message
            bot_response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                # prompt=chat_log[-1]["content"],
                temperature=0.8,
                max_tokens=3000,
                messages=chat_log,
            )
            chat_log.append({"role": "system", "content": bot_response.choices[0].message.content})

        # Store the updated chat log in a cookie
        chat_log_json = json.dumps(chat_log)
        response = JsonResponse({'question': message,
                                 'message': bot_response.choices[0].message.content})
        response.set_cookie('chat_log', chat_log_json)

        # Return the chatbot's response as a JSON object
        return response
    



# Dictionary Bot
class DictionaryBotView(generic.TemplateView):
    template_name = 'baseApp/dictionary_bot.html'

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        # Append extraContext
        context.update(get_extra_context())
        context['slideContent'] = models.Slide.objects.get(useFor__exact='ABOUT_US', active__exact=True)
        context['pageTitle'] = 'Dictionary'
        return context

    def post(self, request):

        # Get the user's message from the query string
        word = request.POST.get('message', '')


        # Initialize the OpenAI API client
        client = openai.OpenAI(api_key=settings.CHATGPT_API,)

        # Construct dictionary-specific prompt
        prompt = f"Define the word {word}"

        # Create a new chat completion if there is no previous chat log
        bot_response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages = [
                {"role": "user", "content": f'{prompt}'},
                {"role": "system", "content": f'Provide a comprehensive dictionary entry for the word {prompt} like Longman Contemporary style, including:  \n- Part of speech \
                 \n- Definition  \n- Phonetics (how to pronounce the word) \n- Two examples of how to use the word in a sentence \
                 \n- Can it be used in informal dialog? Give two examples of that. \n-What other alternative words that I can use instead of {prompt}? \
                 \n- Give some of the common collocation for this word. \n Do we have any phrasal verb which contains {prompt}, give me an example of them.'}
            ],
            temperature=0.8,
            max_tokens=3000,
        )
       
        # Extract definition from response
        definition = bot_response.choices[0].message.content

        # Return structured response
        return JsonResponse({'word': word, 'definition': definition})


# Telegram Bot
# Token and webhook URL
# bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
WEBHOOK_URL = 'https://www.gammaturkey.com/telegram-dictionary-bot/'


def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    response = requests.post(url, json=data)
    return response.json()   

# Handle incoming messages
def handle_update(request):
    # Extract relevant information from the Update (JSONized)
    # read the structure from here
    # https://core.telegram.org/bots/api#update

    try:
        # Get the raw JSON data from the request
        received_data = json.loads(request.body.decode('utf-8'))
        message_text = received_data.get('message', {})
        chat_id = received_data.get('message', {}).get('chat', {}).get('id')
        
        # Handle the extracted information
        if message_text == '/start':
            send_message(chat_id=chat_id, text="Hello, I'm your dictionary bot! Send me a word to get its definition.")
        else:
            # OpenAI API client
            openai_client = openai.OpenAI(api_key=settings.CHATGPT_API)

            # Construct prompt and get definition from OpenAI
            prompt = f"{message_text}"

            try:
                bot_response = openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages = [
                        {"role": "user", "content": f'{prompt}'},
                        {"role": "system", "content": f'Provide a comprehensive dictionary entry for the word {prompt} like Longman Contemporary style, including:  \n- Part of speech \
                        \n- Definition  \n- Phonetics (how to pronounce the word) \n- Two examples of how to use the word in a sentence \
                        \n- Can it be used in informal dialog? Give two examples of that. \n-What other alternative words that I can use instead of {prompt}? \
                        \n- Give some of the common collocation for this word. \n Do we have any phrasal verb which contains {prompt}, give me an example of them.'}
                    ],
                    temperature=0.8,
                    max_tokens=3000,
                )

                definition = bot_response.choices[0].message.content
                # send the ai reply to telegram chat
                send_message(chat_id=chat_id, text=definition)

            except Exception as e:
                send_message(chat_id=chat_id, text=f"An error occurred: {e}")
    
    except Exception as e:
        # Handle JSON decoding errors
        send_message(chat_id=chat_id, text=f"Error decoding JSON: {e}")


# View to handle webhook
class TelegramDictionaryBotView(generic.View):
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):       
        # if not bot.get_webhook_info().url:
        #     bot.set_webhook(url=WEBHOOK_URL)
        return super().dispatch(request, *args, **kwargs)


    def post(self, request, *args, **kwargs):
        handle_update(request)
        return HttpResponse('Success', status=200)
