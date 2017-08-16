import datetime
from decimal import Decimal

from django import template

register = template.Library()

@register.filter("money")
def money(value, divisibility):
    """
    Format money to have a decimal value based on a divisibility.
    """
    return abs(Decimal(value) / Decimal('10')**divisibility)

@register.filter("timestamp")
def timestamp(value):
    """
    Convert timestamp to a date.
    """

    try:
        return datetime.datetime.fromtimestamp(value / 1000)
    except AttributeError as e:
        return datetime.datetime.now()