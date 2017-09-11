from rest_framework import status
from django.utils.encoding import force_text
from rest_framework.exceptions import APIException


class SilentException(APIException):
    status_code = 200
    default_detail = 'Silent error.'
    default_error_slug = 'silent_error'


class PurchaseException(APIException):
    status_code = 500
    default_detail = 'Purchase error.'
    default_error_slug = 'purchase_error'