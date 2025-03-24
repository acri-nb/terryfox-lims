from django import template
from django.template.defaultfilters import stringfilter
import json

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Get an item from a dictionary by key.
    Usage: {{ mydict|get_item:item_key }}
    """
    if not dictionary:
        return 0
        
    # Try to get the value, default to 0 if not found
    try:
        key = str(key)  # Ensure key is a string for JSON serialization
        if isinstance(dictionary, dict):
            return dictionary.get(key, 0)
        elif hasattr(dictionary, 'get'):
            return dictionary.get(key, 0)
        else:
            return 0
    except:
        return 0

@register.filter
def to_json(value):
    """
    Convert a Python object to JSON for use in JavaScript.
    Usage: {{ mydict|to_json }}
    """
    return json.dumps(value) 