## This views.py is excatly the same as blogApp/views.py
## The differences are in import modules part and the Template html files.
## The queryset are filtered on FA language posts.
## The extraContent part is also has some customized changes for FA language

from django.shortcuts import render
from django.views import generic
# imported form blogApp models.py
from apps.blogApp import models
# This is for showing properties on blog pages
from apps.baseApp import models as baseAppModel
from django.db.models import Q



# Here is the Extra Context ditionary which is used in get_context_data of Views classes
def get_extra_context():
    extraContext = {
        'featuredProperties': baseAppModel.Asset.objects.filter(featured=True),
        'blogCategories': models.PostCategories.objects.filter(category_lang='FA'),
        # Default page for FAQ section.
        'navbar_FAQ': 'all'
        }
    return extraContext


class PostList(generic.ListView):
    context_object_name = 'allPosts'
    queryset = models.Post.objects.filter(language='FA', status=True).order_by('-created_on')
    template_name = 'FAblogApp/blog.html'
    paginate_by = 3

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        # Append shared extraContext
        context.update(get_extra_context())

        # This title is different for this view
        context['slideContent'] = baseAppModel.Slide.objects.get(useFor__exact='BLOG_HOME', active__exact=True)

        return context


class CategoryListView(generic.ListView):
        context_object_name = 'allPosts'
        model = models.Post
        template_name = 'FAblogApp/search_result.html'
        paginate_by = 8

        def get_queryset(self, **kwargs):
            result = super(CategoryListView, self).get_queryset()

            # Categories -- For filtering based on the categories
            result= result.filter(language='FA', categories__slug=self.kwargs['category'], status=True).order_by('-created_on')
            return result


        def get_context_data(self, **kwargs):
            # Call the base implementation first to get a context
            context = super().get_context_data(**kwargs)
            # Append shared extraContext
            context.update(get_extra_context())

            # This title is different for this view
            context['pageTitle'] = models.PostCategories.objects.get(slug=self.kwargs['category']).category
            context['slideContent'] = baseAppModel.Slide.objects.get(useFor__exact='BLOG_CATEGORY', active__exact=True)
            # result counte
            context['resultCount'] = len(self.get_queryset())
            return context


class PostDetail(generic.DetailView):
    context_object_name = 'the_post'
    model = models.Post
    template_name = 'FAblogApp/single_post.html'

    def get_object(self, **kwargs):
        singleResult = self.model.objects.get(slug=self.kwargs['slug'], status=True)
        # To implement save method on the model which adds view count
        singleResult.save()
        return singleResult

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        # Append shared extraContext
        context.update(get_extra_context())

        # This title is different for this view
        context['slideContent'] = baseAppModel.Slide.objects.get(useFor__exact='BLOG_POST', active__exact=True)
        return context


class PostSearch(generic.ListView):
    context_object_name = 'allPosts'
    template_name = 'FAblogApp/search_result.html'
    model = models.Post
    paginate_by = 8

    def get_queryset(self, **kwargs):
        result = super(PostSearch, self).get_queryset()

        # Get the GET content >>> name='s'
        keyword = self.request.GET.get('s')
        if not(keyword==None or keyword==''):
            # Content Search -- For filtering based on the Text Search
            result= result.filter(Q(title__icontains=keyword) | Q(content__icontains=keyword), language='FA', status=True).order_by('-created_on')

        return result

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        # Append shared extraContext
        context.update(get_extra_context())

        # This title is different for this view
        context['pageTitle'] = 'جستجوی مطالب'
        context['slideContent'] = baseAppModel.Slide.objects.get(useFor__exact='BLOG_SEARCH', active__exact=True)
        # result counte
        context['resultCount'] = len(self.get_queryset())
        return context
