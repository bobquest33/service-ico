from collections import OrderedDict

from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView
from rest_framework import exceptions

from notifications.models import *
from notifications.serializers import *
from notifications.authentication import *

from logging import getLogger

logger = getLogger('django')


# API root
@api_view(['GET'])
@permission_classes([AllowAny,])
def root(request, format=None):
    """
    ### API documentation for the Notifications service.
    ---
    """
    return Response(
        [
            {'Admins': OrderedDict(
                [('Activate', reverse('notifications:activate',
                    request=request,
                    format=format)),
                 ('Deactivate', reverse('notifications:deactivate',
                    request=request,
                    format=format)),
                 ('Webhook', reverse('notifications:webhook',
                    request=request,
                    format=format)),
                 ('Company', reverse('notifications:company',
                    request=request,
                    format=format)),
                 ('Notifications', reverse('notifications:notifications',
                    request=request,
                    format=format)),
                 ('Logs', reverse('notifications:logs',
                    request=request,
                    format=format))
                 ]
            )}
    ])


class ActivateView(GenericAPIView):
    """
    Activate a company in the notification service. A secret key is created on
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
    Dectivate a company in the notification service.
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


class ListCreateNotificationsView(GenericAPIView):
    """
    List and create notifications. Authenticates requests using a token in the 
    Authorization header.
    """

    allowed_methods = ('GET', 'POST',)
    serializer_class = NotificationSerializer
    authentication_classes = (AdminAuthentication,)

    def get(self, request, *args, **kwargs):
        company = request.user.company
        queryset = Notification.objects.filter(company=company)

        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response({'status': 'success', 'data': serializer.data})

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        note = serializer.save()
        return Response({'status': 'success', 'data': serializer.data})


class NotificationsView(GenericAPIView):
    """
    View and update notifications. Authenticates requests using a token in the 
    Authorization header.
    """

    allowed_methods = ('GET', 'PATCH', 'DELETE',)
    serializer_class = NotificationSerializer
    authentication_classes = (AdminAuthentication,)

    def get(self, request, *args, **kwargs):
        company = request.user.company
        notification_id = kwargs['notification_id']

        try:
            note = Notification.objects.get(company=company, id=notification_id)
        except Notification.DoesNotExist:
            raise exceptions.NotFound()

        serializer = self.get_serializer(note)
        return Response({'status': 'success', 'data': serializer.data})

    def patch(self, request, *args, **kwargs):
        company = request.user.company
        notification_id = kwargs['notification_id']

        try:
            note = Notification.objects.get(company=company, id=notification_id)
        except Notification.DoesNotExist:
            raise exceptions.NotFound()

        serializer = self.get_serializer(note, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response({'status': 'success', 'data': serializer.data})

    def delete(self, request, *args, **kwargs):
        company = request.user.company
        notification_id = kwargs['notification_id']

        try:
            note = Notification.objects.get(company=company, id=notification_id)
        except Notification.DoesNotExist:
            raise exceptions.NotFound()

        serializer = self.get_serializer(note)
        instance = serializer.delete()
        return Response({'status': 'success'})



class ListLogsView(GenericAPIView):
    """
    List logs for notifications. Authenticates requests using a token in the 
    Authorization header.
    """

    allowed_methods = ('GET',)
    serializer_class = LogSerializer
    authentication_classes = (AdminAuthentication,)

    def get(self, request, *args, **kwargs):
        company = request.user.company
        queryset = NotificationLog.objects.filter(notification__company=company)

        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response({'status': 'success', 'data': serializer.data})


class LogsView(GenericAPIView):
    """
    View logs. Authenticates requests using a token in the 
    Authorization header.
    """

    allowed_methods = ('GET',)
    serializer_class = LogSerializer
    authentication_classes = (AdminAuthentication,)

    def get(self, request, *args, **kwargs):
        company = request.user.company
        log_id = kwargs['log_id']

        try:
            note = NotificationLog.objects.get(notification__company=company, 
                id=log_id)
        except NotificationLog.DoesNotExist:
            raise exceptions.NotFound()

        serializer = self.get_serializer(note)
        return Response({'status': 'success', 'data': serializer.data})