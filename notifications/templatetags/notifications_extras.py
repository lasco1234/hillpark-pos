from django import template

register = template.Library()

@register.filter
def get_field(obj, attr):
    """Template filter to get an attribute dynamically."""
    return getattr(obj, attr, None)