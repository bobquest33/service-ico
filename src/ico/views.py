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
                 ('Webhook', reverse('ico:admin-webhook',
                    request=request,
                    format=format)),
                 ('Company', reverse('ico:admin-company',
                    request=request,
                    format=format)),
                 ('Currencies', reverse('ico:admin-currencies',
                    request=request,
                    format=format)),
                 ('Ico', reverse('ico:admin-icos',
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


class AdminWebhookView(GenericAPIView):
    """
    Receive a webhook event. Authenticates requests using a secret in the 
    Authorization header.
    """

    allowed_methods = ('POST',)
    permission_classes = (AllowAny, )
    serializer_class = AdminWebhookSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response({'status': 'success'})


class AdminCompanyView(GenericAPIView):
    """
    View and update company. Authenticates requests using a token in the 
    Authorization header.
    """

    allowed_methods = ('GET', 'PATCH',)
    serializer_class = AdminCompanySerializer
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


class AdminCurrencyList(GenericAPIView):
    """
    List and create ICOs.
    """

    allowed_methods = ('GET',)
    serializer_class = AdminCurrencySerializer
    authentication_classes = (AdminAuthentication,)

    def get(self, request, *args, **kwargs):
        company = request.user.company
        queryset = Currency.objects.filter(company=company)
        serializer = self.get_serializer(queryset, many=True)
        return Response({'status': 'success', 'data': serializer.data})

    # Need to be able to refresh enabled currencies.
    # This should disable currencies that are no longer enabled.
    # Perhaps a function to POST nothing will run refresh, or instead a
    # refresh URL?


class AdminCurrencyView(GenericAPIView):
    """
    View currency.
    """

    allowed_methods = ('GET',)
    serializer_class = AdminCurrencySerializer
    authentication_classes = (AdminAuthentication,)

    def get(self, request, *args, **kwargs):
        company = request.user.company
        code = kwargs['code']

        try:
            currency = Currency.objects.get(company=company, code__iexact=code)
        except Currency.DoesNotExist:
            raise exceptions.NotFound()

        serializer = self.get_serializer(currency)
        return Response({'status': 'success', 'data': serializer.data})


class AdminIcoList(GenericAPIView):
    """
    List and create ICOs.
    """

    allowed_methods = ('GET', 'POST',)
    serializer_class = AdminIcoSerializer
    authentication_classes = (AdminAuthentication,)

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return AdminCreateIcoSerializer
        return super(AdminIcoList, self).get_serializer_class()

    def get(self, request, *args, **kwargs):
        company = request.user.company
        queryset = Ico.objects.filter(company=company)
        serializer = self.get_serializer(queryset, many=True)
        return Response({'status': 'success', 'data': serializer.data})

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ico = serializer.save()
        data = AdminIcoSerializer(serializer.instance, 
            context={'request': request}).data
        return Response({'status': 'success', 'data': data})


class AdminIcoView(GenericAPIView):
    """
    View, update and delete ICOs.
    """

    allowed_methods = ('GET', 'PATCH', 'DELETE',)
    serializer_class = AdminIcoSerializer
    authentication_classes = (AdminAuthentication,)

    def get(self, request, *args, **kwargs):
        company = request.user.company
        ico_id = kwargs['ico_id']

        try:
            ico = Ico.objects.get(company=company, id=ico_id)
        except Ico.DoesNotExist:
            raise exceptions.NotFound()

        serializer = self.get_serializer(ico)
        return Response({'status': 'success', 'data': serializer.data})

    def patch(self, request, *args, **kwargs):
        company = request.user.company
        ico_id = kwargs['ico_id']

        try:
            ico = Ico.objects.get(company=company, id=ico_id)
        except Ico.DoesNotExist:
            raise exceptions.NotFound()

        serializer = self.get_serializer(ico, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response({'status': 'success', 'data': serializer.data})

    def delete(self, request, *args, **kwargs):
        company = request.user.company
        ico_id = kwargs['ico_id']

        try:
            ico = Ico.objects.get(company=company, id=ico_id)
        except Ico.DoesNotExist:
            raise exceptions.NotFound()

        serializer = self.get_serializer(ico)
        instance = serializer.delete()
        return Response({'status': 'success'})


class AdminPhasesList(GenericAPIView):
    """
    List and create phases.
    """

    allowed_methods = ('GET', 'POST',)
    serializer_class = AdminPhasesSerializer
    authentication_classes = (AdminAuthentication,)

    def get(self, request, *args, **kwargs):
        company = request.user.company
        ico_id = kwargs['ico_id']

        try:
            ico = Ico.objects.get(company=company, id=ico_id)
        except Ico.DoesNotExist:
            raise exceptions.NotFound()

        queryset = Phase.objects.filter(ico=ico)
        serializer = self.get_serializer(queryset, many=True)
        return Response({'status': 'success', 'data': serializer.data})

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response({'status': 'success', 'data': serializer.data})        


class AdminPhasesView(GenericAPIView):
    """
    View and delete phases.
    """

    allowed_methods = ('GET', 'DELETE',)
    serializer_class = AdminPhasesSerializer
    authentication_classes = (AdminAuthentication,)

    def get(self, request, *args, **kwargs):
        company = request.user.company
        ico_id = kwargs['ico_id']
        phase_id = kwargs['phase_id']

        try:
            phase = Phase.objects.get(id=phase_id, ico_id=ico_id,
                ico__company=company)
        except Phase.DoesNotExist:
            raise exceptions.NotFound()

        serializer = self.get_serializer(phase)
        return Response({'status': 'success', 'data': serializer.data})

    def delete(self, request, *args, **kwargs):
        company = request.user.company
        ico_id = kwargs['ico_id']
        phase_id = kwargs['phase_id']

        try:
            phase = Phase.objects.get(id=phase_id, ico_id=ico_id,
                ico__company=company)
        except Phase.DoesNotExist:
            raise exceptions.NotFound()

        serializer = self.get_serializer(phase)
        instance = serializer.delete()
        return Response({'status': 'success'})


class AdminRatesList(GenericAPIView):
    """
    List and create rates.
    """

    allowed_methods = ('GET',)
    serializer_class = AdminRatesSerializer
    authentication_classes = (AdminAuthentication,)

    def get(self, request, *args, **kwargs):
        company = request.user.company
        ico_id = kwargs['ico_id']
        phase_id = kwargs['phase_id']

        try:
            phase = Phase.objects.get(id=phase_id, ico_id=ico_id,
                ico__company=company)
        except Phase.DoesNotExist:
            raise exceptions.NotFound()

        queryset = Rate.objects.filter(phase=phase)
        serializer = self.get_serializer(queryset, many=True)
        return Response({'status': 'success', 'data': serializer.data})


class AdminRatesView(GenericAPIView):
    """
    View, update and delete rates.
    """

    allowed_methods = ('GET',)
    serializer_class = AdminRatesSerializer
    authentication_classes = (AdminAuthentication,)

    def get(self, request, *args, **kwargs):
        company = request.user.company
        ico_id = kwargs['ico_id']
        phase_id = kwargs['phase_id']
        rate_id = kwargs['rate_id']

        try:
            rate = Rate.objects.get(id=rate_id, phase_id=phase_id, 
                phase__ico_id=ico_id, phase__ico__company=company)
        except Rate.DoesNotExist:
            raise exceptions.NotFound()

        serializer = self.get_serializer(rate)
        return Response({'status': 'success', 'data': serializer.data})


class AdminQuotesList(GenericAPIView):
    """
    List and create quotes.
    """

    allowed_methods = ('GET',)
    serializer_class = AdminQuotesSerializer
    authentication_classes = (AdminAuthentication,)

    def get(self, request, *args, **kwargs):
        company = request.user.company
        ico_id = kwargs['ico_id']

        try:
            ico = Ico.objects.get(company=company, id=ico_id)
        except Ico.DoesNotExist:
            raise exceptions.NotFound()

        queryset = Quote.objects.filter(phase__ico=ico)
        serializer = self.get_serializer(queryset, many=True)
        return Response({'status': 'success', 'data': serializer.data})


class AdminQuotesView(GenericAPIView):
    """
    View, update and delete quotes.
    """

    allowed_methods = ('GET',)
    serializer_class = AdminQuotesSerializer
    authentication_classes = (AdminAuthentication,)

    def get(self, request, *args, **kwargs):
        company = request.user.company
        ico_id = kwargs['ico_id']
        quote_id = kwargs['quote_id']

        try:
            quote = Quote.objects.get(id=quote_id, phase__ico_id=ico_id, 
                phase__ico__company=company)
        except Quote.DoesNotExist:
            raise exceptions.NotFound()

        serializer = self.get_serializer(quote)
        return Response({'status': 'success', 'data': serializer.data})


class AdminPurchasesList(GenericAPIView):
    """
    List and create purchases.
    """

    allowed_methods = ('GET',)
    serializer_class = AdminPurchasesSerializer
    authentication_classes = (AdminAuthentication,)

    def get(self, request, *args, **kwargs):
        company = request.user.company
        ico_id = kwargs['ico_id']

        try:
            ico = Ico.objects.get(company=company, id=ico_id)
        except Ico.DoesNotExist:
            raise exceptions.NotFound()

        queryset = Purchase.objects.filter(quote__phase__ico=ico)
        serializer = self.get_serializer(queryset, many=True)
        return Response({'status': 'success', 'data': serializer.data})


class AdminPurchasesView(GenericAPIView):
    """
    View, update and delete purchases.
    """

    allowed_methods = ('GET',)
    serializer_class = AdminPurchasesSerializer
    authentication_classes = (AdminAuthentication,)

    def get(self, request, *args, **kwargs):
        company = request.user.company
        ico_id = kwargs['ico_id']
        purchase_id = kwargs['purchase_id']

        try:
            purchase = Purchase.objects.get(id=purchase_id, 
                quote__phase__ico_id=ico_id, quote__phase__ico__company=company)
        except Purchase.DoesNotExist:
            raise exceptions.NotFound()

        serializer = self.get_serializer(purchase)
        return Response({'status': 'success', 'data': serializer.data})