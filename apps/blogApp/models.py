from django.db import models
from django.contrib.auth.models import User
from django.template.defaultfilters import slugify
from ckeditor_uploader.fields import RichTextUploadingField


POST_STATUS = (
    (False,"Draft"),
    (True,"Publish")
)

FEATURED_STATUS = (
    (False,"Regular"),
    (True,"Featured")
)

class PostCategories(models.Model):
    category = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=150, unique=True, blank=True, null=True,
                                help_text="The name of the page as it will appear in URLs e.g http://domain.com/blog/category/[my-slug]/")
    class Meta():
        verbose_name_plural = "Categories"
        ordering = ['category']

    def __str__(self):
        return self.category

    def save(self, *args, **kwargs):
        self.slug = slugify(self.category)
        return super(PostCategories, self).save(*args, **kwargs)

class Post(models.Model):
    author = models.ForeignKey(User, on_delete= models.CASCADE, related_name='blog_posts')
    categories = models.ManyToManyField(PostCategories, related_name='categories', null=True)
    title = models.CharField(max_length=110, unique=True)
    content = RichTextUploadingField(help_text='Full images can be 730px wide')
    shortContent = models.TextField(max_length=370, blank=True, help_text='Max Characters = 370')
    image = models.ImageField(upload_to='blogApp/post/', blank=True, null=True,
                                help_text="Thumbnail Image  1600x1200")
    slug = models.SlugField(max_length=150, unique=True, blank=True, null=True,
                                help_text="The name of the page as it will appear in URLs e.g http://domain.com/blog/[my-slug]/")
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now= True)
    status = models.BooleanField(choices=POST_STATUS, default=False)
    featured = models.BooleanField(choices=FEATURED_STATUS, default=False)
    view = models.PositiveIntegerField(default=0)


    class Meta:
        ordering = ['-created_on']

    def __str__(self):
        return self.title


    def save(self, *args, **kwargs):
        # This "if" is restrict the model to write slug only for the first time.
        # Not everytime you call the "save" method
        if not self.id:
            self.slug = slugify(self.title)
        # Add one view to the Post
        self.view += 1

        return super(Post, self).save(*args, **kwargs)
