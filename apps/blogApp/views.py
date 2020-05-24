from django.shortcuts import render
from django.views import generic
from . import models
from apps.baseApp import models as baseAppModel
from django.db.models import Q


class PostList(generic.ListView):
    context_object_name = 'allPosts'
    queryset = models.Post.objects.filter(status=True).order_by('-created_on')
    template_name = 'blogApp/blog.html'
    paginate_by = 3

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)

        # Add other data  ** This part also need to be changed in PostDetail **
        context['slideContent'] = baseAppModel.Slide.objects.get(id=2)
        context['featuredProperties'] = baseAppModel.Asset.objects.filter(featured=True)
        context['categories'] = models.PostCategories.objects.all()
        # This title is different with Categories Page view
        context['PageTitle'] = 'BLOG'

        return context


class CategoryListView(generic.ListView):
        context_object_name = 'allPosts'
        model = models.Post
        template_name = 'blogApp/searchResult.html'
        paginate_by = 8

        def get_queryset(self, **kwargs):
            result = super(CategoryListView, self).get_queryset()

            # Categories -- For filtering based on the categories
            result= result.filter(categories__slug=self.kwargs['category'], status=True).order_by('-created_on')
            return result


        def get_context_data(self, **kwargs):
            # Call the base implementation first to get a context
            context = super().get_context_data(**kwargs)

            # Add other data  ** This part also need to be changed in PostDetail **
            context['slideContent'] = baseAppModel.Slide.objects.get(id=2)
            context['featuredProperties'] = baseAppModel.Asset.objects.filter(featured=True)
            context['categories'] = models.PostCategories.objects.all()
            # This title is different with BLOG Page view
            context['PageTitle'] = models.PostCategories.objects.get(slug=self.kwargs['category']).category
            return context



class PostDetail(generic.DetailView):
    context_object_name = 'the_post'
    model = models.Post
    template_name = 'blogApp/single_post.html'

    def get_object(self, **kwargs):
        singleResult = self.model.objects.get(slug=self.kwargs['slug'], status=True)
        # To implement save method on the model which adds view count
        singleResult.save()
        return singleResult

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)

        # Add other data  ** This part also need to be changed in PostDetail **
        context['slideContent'] = baseAppModel.Slide.objects.get(id=3)
        context['featuredProperties'] = baseAppModel.Asset.objects.filter(featured=True)
        context['categories'] = models.PostCategories.objects.all()

        return context

class PostSearch(generic.ListView):
    context_object_name = 'allPosts'
    template_name = 'blogApp/searchResult.html'
    queryset = models.Post.objects.filter(status=True).order_by('-created_on')
    paginate_by = 8

    def get_queryset(self, **kwargs):
        result = super(PostSearch, self).get_queryset()

        # Get the GET content >>> name='s'
        keyword = self.request.GET.get('s')
        if not(keyword==None or keyword==''):
            # Content Search -- For filtering based on the Text Search
            result= result.filter(Q(title__icontains=keyword) | Q(content__icontains=keyword), status=True).order_by('-created_on')
        return result

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)

        # Add other data  ** This part also need to be changed in PostDetail **
        context['slideContent'] = baseAppModel.Slide.objects.get(id=2)
        context['featuredProperties'] = baseAppModel.Asset.objects.filter(featured=True)
        context['categories'] = models.PostCategories.objects.all()
        # This title is different with BLOG Page view
        context['PageTitle'] = 'SEARCH'
        return context
