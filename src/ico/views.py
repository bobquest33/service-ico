from collections import OrderedDict

from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView
from rest_framework import exceptions

from ico.models import *
from ico.serializers import *
from ico.authentication import *

from logging import getLogger

logger = getLogger('django')


# API root
@api_view(['GET'])
@permission_classes([AllowAny,])
def root(request, format=None):
    """
    ### API documentation for the ICO service.
    ---
    """
    return Response(
        [
            {'Admins': OrderedDict(
                [('Activate', reverse('ico:activate',
                    request=request,
                    format=format)),
                 ('Deactivate', reverse('ico:deactivate',
                    request=request,
                    format=format)),
                 ('Webhook', reverse('ico:webhook',
                    request=request,
                    format=format)),
                 ('Company', reverse('ico:company',
                    request=request,
                    format=format))
                 ]
            )}
    ])


class ActivateView(GenericAPIView):
    """
    Activate a company in the ICO service. A secret key is created on
    activation.
    """

    allowed_methods = ('POST',)
    permission_classes = (AllowAny, )
    serializer_class = ActivateSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response({'status': 'success', 'data': serializer.data})


class DeactivateView(GenericAPIView):
    """
    Dectivate a company in the ICO service.
    """

    allowed_methods = ('POST',)
    permission_classes = (AllowAny, )
    serializer_class = DeactivateSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.delete()
        return Response({'status': 'success'})


class WebhookView(GenericAPIView):
    """
    Receive a webhook event. Authenticates requests using a secret in the 
    Authorization header.
    """

    allowed_methods = ('POST',)
    permission_classes = (AllowAny, )
    serializer_class = WebhookSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response({'status': 'success'})


class CompanyView(GenericAPIView):
    """
    View and update company. Authenticates requests using a token in the 
    Authorization header.
    """

    allowed_methods = ('GET', 'PATCH',)
    serializer_class = CompanySerializer
    authentication_classes = (AdminAuthentication,)

    def get(self, request, *args, **kwargs):
        company = request.user.company
        serializer = self.get_serializer(company)
        return Response({'status': 'success', 'data': serializer.data})

    def patch(self, request, *args, **kwargs):
        company = request.user.company
        serializer = self.get_serializer(company, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response({'status': 'success', 'data': serializer.data})
