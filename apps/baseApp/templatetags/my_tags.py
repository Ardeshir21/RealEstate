
# https://www.caktusgroup.com/blog/2018/10/18/filtering-and-pagination-django/

from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def param_replace(context, **kwargs):
    """
    Return encoded URL parameters that are the same as the current
    request's parameters, only with the specified GET parameters added or changed.

    It also removes any empty parameters to keep things neat,
    so you can remove a parm by setting it to ``""``.

    For example, if you're on the page ``/things/?with_frosting=true&page=5``,
    then

    <a href="/things/?{% param_replace page=3 %}">Page 3</a>

    would expand to

    <a href="/things/?with_frosting=true&page=3">Page 3</a>

    Based on
    https://stackoverflow.com/questions/22734695/next-and-before-links-for-a-django-paginated-query/22735278#22735278
    """

        # request Object is a dictionary
        # QueryDict: {'region_select': ['All Regions'],
        # 'propertyType_select': ['All Types'],
        # 'bedroom_select': ['Any'],
        # 'page': ['3']}

        # d = self.request.GET.copy()
        # urlencode() function. This is a convenience function which takes
        # a dictionary of key value pairs or a sequence of two-element tuples
        # and uses the quote_plus() function to encode every value.
        # The resulting string is a series of key=value pairs separated by & character.



    d = context['request'].GET.copy()
    for k, v in kwargs.items():
        d[k] = v
    for k in [k for k, v in d.items() if not v]:
        del d[k]
    return d.urlencode()
