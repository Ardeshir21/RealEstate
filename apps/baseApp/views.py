from django.shortcuts import render
from django.views import generic
from . import models
from apps.blogApp import models as blogAppModel
from django.db.models import Max, Min, Q
from django.urls import reverse_lazy, reverse


# Here is the Extra Context ditionary which is used in get_context_data of Views classes
def get_extra_context():
    extraContext = {
        'regions': models.Region.objects.all(),
        'propertyTypeNames': set([obj.get_type_display() for obj in models.Asset.objects.all()]),
        'tagType': set([obj.get_tag_display() for obj in models.Asset.objects.all()]),
        'bedroomNumbers': models.Bedroom.objects.order_by('number'),
        'spaceRange': models.Asset.objects.aggregate(Min('build_area'), Max('build_area')),
        # ********for later expansion*********
        # context['priceRangeRent'] = models.Asset.objects.filter(tag__exact='FR').aggregate(Min('price'), Max('price'))
        'priceRange': models.Asset.objects.aggregate(Min('price'), Max('price')),
        # Featured part of the page
        'featuredProperties': models.Asset.objects.filter(featured=True),
        # Blog models
        'blogPosts': blogAppModel.Post.objects.filter(status=True, featured=True),
        # Apartments Unqiue names
        'apartments': models.Complex.objects.all()
        }
    return extraContext



# Index View
class IndexView(generic.ListView):
    context_object_name = 'assets_all'
    template_name = 'baseApp/index.html'
    model = models.Asset

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        # Append extraContext
        context.update(get_extra_context())
        context['slideContent'] = models.Slide.objects.filter(useFor__exact='HOME', active__exact=True)
        return context

# Search Box - searchResult.html
class AssetFilterView(generic.ListView):
    context_object_name = 'assets_filtered'
    model = models.Asset
    template_name = 'baseApp/searchResult.html'
    paginate_by = 9

    def get_queryset(self):
        result = super(AssetFilterView, self).get_queryset()

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

        # Convert the Tag Type into model Format ('FS', 'For Sale')
        # in queries you will use short formats i.e. 'FS'
        for t in models.TAG_CHOICES:
            if tag_query == t[1]:
                tag_query = t[0]
                break

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
            if orderby_query == 'price-oldest':
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
        context['pageTitle'] = 'SEARCH'

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

class AssetSingleView(generic.DetailView):
    # Because this is a DetailView, it will use get() method on the model and return only the property with requested pk
    context_object_name = 'property'
    template_name = 'baseApp/propertyDetails.html'
    model = models.Asset

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        # Append extraContext
        context.update(get_extra_context())
        context['slideContent'] = models.Slide.objects.filter(useFor__exact='PROPERTY_PAGE', active__exact=True)
        return context


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
