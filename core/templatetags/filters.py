from datetime import datetime
from django import template

register = template.Library()

@register.filter
def exists_and_is_in_past(value):
    return value != None and value.timestamp() <= datetime.now().timestamp()

