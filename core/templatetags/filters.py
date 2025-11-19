from django import template
from django.utils import timezone

register = template.Library()

@register.filter
def exists_and_is_in_past(value):
    return value != None and value.timestamp() <= timezone.now().timestamp()

