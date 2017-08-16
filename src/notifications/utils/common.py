import os
import sys
import contextlib
import phonenumbers

from asteval import Interpreter
from twilio import TwilioRestException
from twilio.rest import TwilioRestClient
from django.core.mail import send_mail
from django.template import Template
from django.template import Context
from django.core.exceptions import ValidationError
from django.core.validators import validate_email as django_validate_email

from config import settings

from logging import getLogger

logger = getLogger('django')


@contextlib.contextmanager
def limited_recursion(recursion_limit):
    """
    Prevent unlimited recursion.
    """

    old_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(recursion_limit)

    try:
        yield
    finally:
        sys.setrecursionlimit(old_limit)


def evaluate(expression, data):
    try:
        formula = Template(expression).render(Context(data))

        with limited_recursion(250):
            aeval = Interpreter()
            return aeval(formula)

    except Exception as exc:
        logger.exception(exc)
        return None


def send_email(subject, message, to_email, from_email=None, html_message=None):
    logger.info('Sending email to: ' + to_email)

    if not from_email:
        from_email = settings.DEFAULT_FROM_EMAIL

    send_mail(subject, message, from_email, (to_email,), html_message=html_message)


def send_sms(message, number):
    logger.info('Sending sms to: ' + number)

    details = dict(
        to=str(number),
        from_=settings.TWILIO_FROM_NUMBER,
        body=str(message),
    )

    if os.environ.get('DEBUG', True) not in ('True', 'true', True,):
        client = TwilioRestClient(settings.TWILIO_SID, 
            settings.TWILIO_TOKEN)
        client.messages.create(**details)
    else:
        logger.info(details)


def validate_email(email):
    try:
        django_validate_email(email)
    except ValidationError:
        return False
    else:
        return True


def validate_mobile(phone):
    try:
        number = phonenumbers.parse(phone)
        # Return 0, 2 or 1. 1 represents MOBILE 
        number_type = phonenumbers.number_type(number)
        
        if not phonenumbers.is_valid_number(number) or number_type != 1:
            raise ValueError
    except (phonenumbers.NumberParseException, ValueError):
        return False
    else:
        return True

