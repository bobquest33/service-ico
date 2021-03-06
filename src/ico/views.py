from collections import OrderedDict

from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView
from rest_framework import exceptions, status, filters
from rest_framework.pagination import PageNumberPagination

from ico.models import *
from ico.serializers import *
from ico.authentication import *
from ico.enums import IcoStatus

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
            {'Public': OrderedDict(
                [('Activate', reverse('ico:activate',
                    request=request,
                    format=format)),
                 ('Deactivate', reverse('ico:deactivate',
                    request=request,
                    format=format)),
                 ('Icos', reverse('ico:icos',
                    request=request,
                    format=format))
                ]
            )},     
            {'Admins': OrderedDict(
                [('Initiate Webhook', reverse('ico:admin-webhooks-initiate',
                    request=request,
                    format=format)),
                 ('Execute Webhook', reverse('ico:admin-webhooks-execute',
                    request=request,
                    format=format)),
                 ('Company', reverse('ico:admin-company',
                    request=request,
                    format=format)),
                 ('Currencies', reverse('ico:admin-currencies',
                    request=request,
                    format=format)),
                 ('Icos', reverse('ico:admin-icos',
                    request=request,
                    format=format))
                ]
            )},
            {'Users': OrderedDict(
                [('Icos', reverse('ico:user-icos',
                    request=request,
                    format=format))
                ]
            )},
    ])


class ResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 250

    def get_paginated_response(self, data):
        response = OrderedDict([
            ('count', self.page.paginator.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data)
        ])

        return Response(OrderedDict([('status', 'success'), ('data', response)]))


class ListModelMixin(object):
    """
    List a queryset.
    """

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response({'status': 'success', 'data': serializer.data})


class ListAPIView(ListModelMixin,
                  GenericAPIView):
    """
    Concrete view for listing a queryset.
    """

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


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
        return Response({'status': 'success',
                         'data': serializer.data},
                         status=status.HTTP_201_CREATED)


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


class IcoList(ListAPIView):
    """
    List public ICOs
    """

    allowed_methods = ('GET',)
    permission_classes = (AllowAny, )
    pagination_class = ResultsSetPagination
    serializer_class = IcoSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filter_fields = ('id', 'status', 'company__identifier', 'currency__code',)

    def get_queryset(self):
        return Ico.objects.exclude(status=IcoStatus.HIDDEN).filter(public=True)


class IcoView(GenericAPIView):
    """
    View public ICOs.
    """

    allowed_methods = ('GET',)
    permission_classes = (AllowAny, )
    serializer_class = IcoSerializer

    def get(self, request, *args, **kwargs):
        ico_id = kwargs['ico_id']

        try:
            ico = Ico.objects.exclude(status=IcoStatus.HIDDEN).get(
                public=True, id=ico_id)
        except Ico.DoesNotExist:
            raise exceptions.NotFound()

        serializer = self.get_serializer(ico)
        return Response({'status': 'success', 'data': serializer.data})


class AdminTransactionInitiateWebhookView(GenericAPIView):
    """
    Receive a initiate webhook event. Authenticates requests using a secret in 
    the Authorization header.
    """

    allowed_methods = ('POST',)
    permission_classes = (AllowAny, )
    serializer_class = AdminTransactionInitiateWebhookSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response({'status': 'success'})


class AdminTransactionExecuteWebhookView(GenericAPIView):
    """
    Receive a execute webhook event. Authenticates requests using a secret in 
    the Authorization header.
    """

    allowed_methods = ('POST',)
    permission_classes = (AllowAny, )
    serializer_class = AdminTransactionExecuteWebhookSerializer

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


class AdminCurrencyList(ListAPIView):
    """
    List and create ICOs.
    """

    allowed_methods = ('GET',)
    pagination_class = ResultsSetPagination
    serializer_class = CurrencySerializer
    authentication_classes = (AdminAuthentication,)
    filter_backends = (filters.DjangoFilterBackend,)
    filter_fields = ('code',)

    def get_queryset(self):
        company = self.request.user.company
        return Currency.objects.filter(company=company)

    # Need to be able to refresh enabled currencies.
    # This should disable currencies that are no longer enabled.
    # Perhaps a function to POST nothing will run refresh, or instead a
    # refresh URL?


class AdminCurrencyView(GenericAPIView):
    """
    View currency.
    """

    allowed_methods = ('GET',)
    serializer_class = CurrencySerializer
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


class AdminIcoList(ListAPIView):
    """
    List and create ICOs.
    """

    allowed_methods = ('GET', 'POST',)
    pagination_class = ResultsSetPagination
    serializer_class = AdminIcoSerializer
    authentication_classes = (AdminAuthentication,)
    filter_backends = (filters.DjangoFilterBackend,)
    filter_fields = ('id', 'status', 'currency__code',)

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return AdminCreateIcoSerializer
        return super(AdminIcoList, self).get_serializer_class()

    def get_queryset(self):
        company = self.request.user.company
        return Ico.objects.filter(company=company).order_by('-created')

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ico = serializer.save()
        data = AdminIcoSerializer(serializer.instance, 
            context={'request': request}).data
        return Response({'status': 'success',
                         'data': data},
                         status=status.HTTP_201_CREATED)


class AdminIcoView(GenericAPIView):
    """
    View, update and delete ICOs.
    """

    allowed_methods = ('GET', 'PATCH', 'DELETE',)
    serializer_class = AdminIcoSerializer
    authentication_classes = (AdminAuthentication,)

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return AdminUpdateIcoSerializer
        return super(AdminIcoView, self).get_serializer_class()

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

        data = AdminIcoSerializer(instance, context={'request': request}).data  
        return Response({'status': 'success', 'data': data})

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


class AdminPhaseList(ListAPIView):
    """
    List and create phases.
    """

    allowed_methods = ('GET', 'POST',)
    pagination_class = ResultsSetPagination
    serializer_class = AdminPhaseSerializer
    authentication_classes = (AdminAuthentication,)
    filter_backends = (filters.DjangoFilterBackend,)
    filter_fields = ('id', 'level',)

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return AdminCreatePhaseSerializer
        return super(AdminPhaseList, self).get_serializer_class()

    def get_queryset(self):
        company = self.request.user.company
        ico_id = self.kwargs['ico_id']

        try:
            ico = Ico.objects.get(company=company, id=ico_id)
        except Ico.DoesNotExist:
            raise exceptions.NotFound()

        return Phase.objects.filter(ico=ico).order_by('level')

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response({'status': 'success',
                         'data': AdminPhaseSerializer(instance).data},
                         status=status.HTTP_201_CREATED)


class AdminPhaseView(GenericAPIView):
    """
    View and delete phases.
    """

    allowed_methods = ('GET', 'DELETE',)
    serializer_class = AdminPhaseSerializer
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


class AdminRateList(ListAPIView):
    """
    List and create rates.
    """

    allowed_methods = ('GET',)
    pagination_class = ResultsSetPagination
    serializer_class = AdminRateSerializer
    authentication_classes = (AdminAuthentication,)
    filter_backends = (filters.DjangoFilterBackend,)
    filter_fields = ('currency__code',)

    def get_queryset(self):
        company = self.request.user.company
        ico_id = self.kwargs['ico_id']
        phase_id = self.kwargs['phase_id']

        try:
            phase = Phase.objects.get(id=phase_id, ico_id=ico_id,
                ico__company=company)
        except Phase.DoesNotExist:
            raise exceptions.NotFound()

        return Rate.objects.filter(phase=phase)


class AdminRateView(GenericAPIView):
    """
    View, update and delete rates.
    """

    allowed_methods = ('GET',)
    serializer_class = AdminRateSerializer
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


class AdminQuoteList(ListAPIView):
    """
    List and create quotes.
    """

    allowed_methods = ('GET',)
    pagination_class = ResultsSetPagination
    serializer_class = AdminQuoteSerializer
    authentication_classes = (AdminAuthentication,)
    filter_backends = (filters.DjangoFilterBackend,)
    filter_fields = ('id', 'deposit_currency__code',)

    def get_queryset(self):
        company = self.request.user.company
        ico_id = self.kwargs['ico_id']

        try:
            ico = Ico.objects.get(company=company, id=ico_id)
        except Ico.DoesNotExist:
            raise exceptions.NotFound()

        return Quote.objects.filter(phase__ico=ico).order_by('-created')


class AdminQuoteView(GenericAPIView):
    """
    View, update and delete quotes.
    """

    allowed_methods = ('GET',)
    serializer_class = AdminQuoteSerializer
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


class AdminPurchaseList(ListAPIView):
    """
    List and create purchases.
    """

    allowed_methods = ('GET',)
    pagination_class = ResultsSetPagination
    serializer_class = AdminPurchaseSerializer
    authentication_classes = (AdminAuthentication,)
    filter_backends = (filters.DjangoFilterBackend,)
    filter_fields = ('id', 'quote__id', 'quote__deposit_currency__code',)

    def get_queryset(self):
        company = self.request.user.company
        ico_id = self.kwargs['ico_id']

        try:
            ico = Ico.objects.get(company=company, id=ico_id)
        except Ico.DoesNotExist:
            raise exceptions.NotFound()

        return Purchase.objects.filter(quote__phase__ico=ico).order_by(
                '-created')


class AdminPurchaseView(GenericAPIView):
    """
    View, update and delete purchases.
    """

    allowed_methods = ('GET',)
    serializer_class = AdminPurchaseSerializer
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


class UserIcoList(ListAPIView):
    """
    List and create ICOs.
    """

    allowed_methods = ('GET',)
    pagination_class = ResultsSetPagination
    serializer_class = UserIcoSerializer
    authentication_classes = (UserAuthentication,)
    filter_backends = (filters.DjangoFilterBackend,)
    filter_fields = ('id', 'status', 'currency__code',)

    def get_queryset(self):
        company = self.request.user.company
        return Ico.objects.exclude(status=IcoStatus.HIDDEN).filter(
            company=company)


class UserIcoView(GenericAPIView):
    """
    View, update and delete ICOs.
    """

    allowed_methods = ('GET',)
    serializer_class = UserIcoSerializer
    authentication_classes = (UserAuthentication,)

    def get(self, request, *args, **kwargs):
        company = request.user.company
        ico_id = kwargs['ico_id']

        try:
            ico = Ico.objects.exclude(status=IcoStatus.HIDDEN).get(
                company=company, id=ico_id)
        except Ico.DoesNotExist:
            raise exceptions.NotFound()

        serializer = self.get_serializer(ico)
        return Response({'status': 'success', 'data': serializer.data})


class UserRateList(ListAPIView):
    """
    List rates.
    """

    allowed_methods = ('GET',)
    pagination_class = ResultsSetPagination
    serializer_class = UserRateSerializer
    authentication_classes = (UserAuthentication,)
    filter_backends = (filters.DjangoFilterBackend,)
    filter_fields = ('id', 'currency__code',)

    def get_queryset(self):
        company = self.request.user.company
        ico_id = self.kwargs['ico_id']

        try:
            ico = Ico.objects.exclude(status=IcoStatus.HIDDEN).get(
                id=ico_id, company=company)
            phase = ico.get_phase()
        except (Ico.DoesNotExist, Phase.DoesNotExist):
            raise exceptions.NotFound()

        return Rate.objects.filter(phase=phase)


class UserRateView(GenericAPIView):
    """
    View rates.
    """

    allowed_methods = ('GET',)
    serializer_class = UserRateSerializer
    authentication_classes = (UserAuthentication,)

    def get(self, request, *args, **kwargs):
        company = request.user.company
        ico_id = kwargs['ico_id']
        rate_id = kwargs['rate_id']

        try:
            ico = Ico.objects.exclude(status=IcoStatus.HIDDEN).get(
                id=ico_id, company=company)
            phase = ico.get_phase()
        except (Ico.DoesNotExist, Phase.DoesNotExist):
            raise exceptions.NotFound()

        try:
            rate = Rate.objects.get(phase=phase, id=rate_id)
        except Rate.DoesNotExist:
            raise exceptions.NotFound()

        serializer = self.get_serializer(rate)
        return Response({'status': 'success', 'data': serializer.data})


class UserQuoteList(ListAPIView):
    """
    List and create quotes.
    """

    allowed_methods = ('GET', 'POST',)
    pagination_class = ResultsSetPagination
    serializer_class = UserQuoteSerializer
    authentication_classes = (UserAuthentication,)
    filter_backends = (filters.DjangoFilterBackend,)
    filter_fields = ('id', 'deposit_currency__code',)

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return UserCreateQuoteSerializer
        return super(UserQuoteList, self).get_serializer_class()

    def get_queryset(self):
        user = self.request.user
        ico_id = self.kwargs['ico_id']

        try:
            ico = Ico.objects.exclude(status=IcoStatus.HIDDEN).get(
                company=user.company, id=ico_id)
        except Ico.DoesNotExist:
            raise exceptions.NotFound()

        return Quote.objects.filter(user=user, phase__ico=ico).order_by(
            '-created')

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ico = serializer.save()
        data = UserQuoteSerializer(serializer.instance, 
            context={'request': request}).data
        return Response({'status': 'success',
                         'data': data},
                         status=status.HTTP_201_CREATED)


class UserQuoteView(GenericAPIView):
    """
    View, update and delete quotes.
    """

    allowed_methods = ('GET',)
    serializer_class = UserQuoteSerializer
    authentication_classes = (UserAuthentication,)

    def get(self, request, *args, **kwargs):
        ico_id = kwargs['ico_id']
        quote_id = kwargs['quote_id']

        try:
            quote = Quote.objects.get(id=quote_id, phase__ico_id=ico_id, 
                user=request.user)
        except Quote.DoesNotExist:
            raise exceptions.NotFound()

        serializer = self.get_serializer(quote)
        return Response({'status': 'success', 'data': serializer.data})


class UserPurchaseList(ListAPIView):
    """
    List and create purchases.
    """

    allowed_methods = ('GET',)
    pagination_class = ResultsSetPagination
    serializer_class = UserPurchaseSerializer
    authentication_classes = (UserAuthentication,)
    filter_backends = (filters.DjangoFilterBackend,)
    filter_fields = ('id', 'quote__id', 'quote__deposit_currency__code',)

    def get_queryset(self):
        user = self.request.user
        ico_id = self.kwargs['ico_id']

        try:
            ico = Ico.objects.exclude(status=IcoStatus.HIDDEN).get(
                company=user.company, id=ico_id)
        except Ico.DoesNotExist:
            raise exceptions.NotFound()

        return Purchase.objects.filter(quote__user=user, quote__phase__ico=ico
            ).order_by('-created')


class UserPurchaseView(GenericAPIView):
    """
    View, update and delete purchases.
    """

    allowed_methods = ('GET',)
    serializer_class = UserPurchaseSerializer
    authentication_classes = (UserAuthentication,)

    def get(self, request, *args, **kwargs):
        user = request.user
        ico_id = kwargs['ico_id']
        purchase_id = kwargs['purchase_id']

        try:
            purchase = Purchase.objects.get(id=purchase_id, 
                quote__phase__ico_id=ico_id, quote__phase__user=user)
        except Purchase.DoesNotExist:
            raise exceptions.NotFound()

        serializer = self.get_serializer(purchase)
        return Response({'status': 'success', 'data': serializer.data})
