import uuid

from django.utils.translation import ugettext_lazy as _
from django.utils.encoding import smart_text
from rest_framework import authentication, exceptions
from rehive import Rehive, APIException

from .models import Company, User

from logging import getLogger

logger = getLogger('django')


class HeaderAuthentication(authentication.BaseAuthentication):
    """
    Authentication utility class.
    """  

    @staticmethod
    def get_auth_header(request, name="token"):
        try:
            auth = request.META['HTTP_AUTHORIZATION'].split()
        except KeyError:
            return None

        if not auth or smart_text(auth[0].lower()) != name:
            return None

        if not auth[1]:
            return None

        return auth[1]


class AdminAuthentication(HeaderAuthentication):
    """
    Authentication for admin users.
    """

    def authenticate(self, request):
        token = self.get_auth_header(request)
        token = "9b13fb2b0fb1c4fdb7c3f4ae93146d77ba5caf5ce0be07424522abb1b296afe2" #Overide token for testing

        rehive = Rehive(token)

        try:
            user = rehive.user.get()
            if user['permission_group'] != "admin":
                raise exceptions.AuthenticationFailed(_('Invalid admin user'))          
        except APIException:
            raise exceptions.AuthenticationFailed(_('Invalid user'))

        try:
            company = Company.objects.get(identifier=user['company'])
        except Company.DoesNotExist:
            raise exceptions.AuthenticationFailed(
                _("Inactive company. Please activate the company first."))

        user, created = User.objects.get_or_create(
            identifier=uuid.UUID(user['identifier']).hex,
            company=company)

        # Return the permanent token for (not the request token) the company.
        return user, company.admin.token


class UserAuthentication(HeaderAuthentication):
    """
    Authentication for users.
    """

    def authenticate(self, request):
        token = self.get_auth_header(request)
        token = "9b13fb2b0fb1c4fdb7c3f4ae93146d77ba5caf5ce0be07424522abb1b296afe2" #Overide token for testing
 
        rehive = Rehive(token)

        try:
            user = rehive.user.get()        
        except APIException:
            raise exceptions.AuthenticationFailed(_('Invalid user'))

        try:
            company = Company.objects.get(identifier=user['company'])
        except Company.DoesNotExist:
            raise exceptions.AuthenticationFailed(_("Inactive company."))

        user, created = User.objects.get_or_create(
            identifier=uuid.UUID(user['identifier']).hex,
            company=company)

        return user, token
