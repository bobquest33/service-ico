import json
import uuid
import datetime

from rest_framework import serializers, exceptions
from rest_framework.serializers import ModelSerializer
from django.db import transaction
from django.db.models import Q

from ico.models import *
from ico.enums import WebhookEvent, PurchaseStatus
from ico.authentication import HeaderAuthentication
from rehive import Rehive, APIException
from ico.utils.common import (
    to_cents, from_cents, quantize
)

from logging import getLogger

logger = getLogger('django')


class DatesMixin(serializers.Serializer):
    """
    Adds created and updated timestamps to the serializer output.
    Just add 'created' and 'updated' to Meta.fields if it is defined
    """
    created = serializers.SerializerMethodField(read_only=True)
    updated = serializers.SerializerMethodField(read_only=True)

    @staticmethod
    def get_created(transaction):
        return int(transaction.created.timestamp() * 1000)

    @staticmethod
    def get_updated(transaction):
        return int(transaction.updated.timestamp() * 1000)


class ActivateSerializer(serializers.Serializer):
    """
    Serialize the activation data, should be a token that represents an admin
    user.
    """

    token = serializers.CharField(write_only=True)
    identifier = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)
    secret = serializers.UUIDField(read_only=True)

    def validate(self, validated_data):
        rehive = Rehive(validated_data.get('token'))

        try:
            user = rehive.user.get()
            if user['permission_group'] != "admin":
                raise serializers.ValidationError(
                    {"token": ["Invalid admin user."]})
        except APIException:
            raise serializers.ValidationError({"token": ["Invalid user."]})

        try:
            company = rehive.admin.company.get()
        except APIException:
            raise serializers.ValidationError({"token": ["Invalid company."]})

        if Company.objects.filter(identifier=company['identifier']).exists():
            raise serializers.ValidationError(
                {"token": ["Company already activated."]})

        try:
            currencies = rehive.company.currencies.get()
        except APIException:
            raise serializers.ValidationError({"non_field_errors": 
                ["Unkown error."]})

        validated_data['user'] = user
        validated_data['company'] = company
        validated_data['currencies'] = currencies

        return validated_data

    def create(self, validated_data):
        token = validated_data.get('token')
        rehive_user = validated_data.get('user')
        rehive_company = validated_data.get('company')
        currencies = validated_data.get('currencies')

        with transaction.atomic():
            user = User.objects.create(token=token,
                identifier=uuid.UUID(rehive_user['identifier']).hex)

            company = Company.objects.create(admin=user, 
                identifier=rehive_company.get('identifier'),
                name=rehive_company.get('name'))

            user.company = company
            user.save()

            # Add currencies to company automatically.
            for kwargs in currencies:
                kwargs['company'] = company
                currency = Currency.objects.create(**kwargs)

            return company


class DeactivateSerializer(serializers.Serializer):
    """
    Serialize the deactivation data, should be a token that represents an admin
    user.
    """

    token = serializers.CharField(write_only=True)

    def validate(self, validated_data):
        rehive = Rehive(validated_data.get('token'))

        try:
            user = rehive.user.get()
            if user['permission_group'] != "admin":
                raise serializers.ValidationError(
                    {"token": ["Invalid admin user."]})
        except APIException:
            raise serializers.ValidationError({"token": ["Invalid user."]})

        try:
            validated_data['company'] = Company.objects.get(
                identifier=user['company'])
        except Company.DoesNotExist:
            raise serializers.ValidationError(
                {"token": ["Company has not been activated yet."]})

        return validated_data

    def delete(self):
        # Deleting the owner will cascade delete the company and all other
        # children objects.
        self.validated_data['company'].admin.delete()

        # TODO: Also delete Rehive webhooks using SDK.
        # Need to update Rehive to allow filtering of webhooks by secret.


class AdminWebhookSerializer(serializers.Serializer):
    event = serializers.ChoiceField(choices=WebhookEvent.choices(), 
        required=True, source='event.value')
    company = serializers.CharField(required=True)
    data = serializers.JSONField(required=True)

    def validate_company(self, company):
        request = self.context['request']

        try:
            secret = HeaderAuthentication.get_auth_header(request, 
                name="secret")
            company = Company.objects.get(identifier=company, secret=secret)
        except (Company.DoesNotExist, ValueError):
            raise serializers.ValidationError("Invalid company.")

        return company

    def create(self, validated_data):
        data = validated_data.get('data')
        event = validated_data['event']['value']
        company = validated_data.get('company')

        return validated_data


class AdminTransactionInitiateWebhookSerializer(AdminWebhookSerializer):
    """
    Serialize initiate transaction webhook data.
    """

    def validate_event(self, event):
        if event != WebhookEvent.TRANSACTION_INITIATE.value:
            raise serializers.ValidationError("Invalid event.")
        return event

    def validate_data(self, data):
        if data['status'] != PurchaseStatus.PENDING.value:
            raise serializers.ValidationError("Invalid transaction status.")

        if data['tx_type'] != "credit":
            raise serializers.ValidationError("Invalid transaction type.")

        return data

    def create(self, validated_data):
        company = validated_data.get('company')
        data = validated_data.get('data')
        tx_id = data.get('id')
        status =  data.get('status')
        currency =  data.get('currency')

        # Instantiate Rehive SDK
        rehive = Rehive(company.admin.token) 
 
        # Check if the transaction is already associated to any purchases.
        try:
            Purchase.objects.get(Q(Q(deposit_tx=tx_id) | Q(token_tx=tx_id)),
                quote__user__company=company)
            # Simply return immediately, this transaction has been initiated
            # already or is a token credit. Don't raise an error because 
            # Rehive webhook will keep retrying.
            return validated_data
        except Purchase.DoesNotExist:
            pass

        # Check if there is an enabled ICO and the ICO has at least one phase.
        # Exclude ICOs that have the same currency code as the transaction.
        try:
            ico = Ico.objects.exclude(currency__code=currency['code']).get(
                company=company, enabled=True)
            phase = ico.get_phase()
        except (Ico.DoesNotExist, Phase.DoesNotExist):
            return validated_data

        # Get a currency.
        try:
            deposit_currency = Currency.objects.get(
                code__iexact=currency['code'], company=company, 
                enabled=True)  
        except Currency.DoesNotExist:
            raise serializers.ValidationError("Invalid currency.")   

        # Get the decimal amount for deposit.
        deposit_cent_amount = Decimal(str(data['amount']))
        deposit_divisibility = Decimal(str(deposit_currency.divisibility))
        deposit_amount = from_cents(deposit_cent_amount, deposit_divisibility)  
 
        # Get or create a user object. Always create a user just in case someone 
        # sent currency without requesting a quote.
        user, created = User.objects.get_or_create(
            identifier=uuid.UUID(data['user']['identifier']).hex,
            company=company)

        # Check for matching quotes, if none exist, create one.
        try:
            date_from = datetime.datetime.now() - datetime.timedelta(minutes=10)
            quote = Quote.objects.filter(user=user, 
                deposit_amount=deposit_amount, 
                deposit_currency=deposit_currency, 
                phase=phase, 
                created__lt=date_from).latest('created')

        except Quote.DoesNotExist:
            rate = Rate.objects.get(phase=phase, currency=deposit_currency)
            token_amount = Decimal(deposit_amount * rate.rate)
            quote = Quote.objects.create(user=user, 
                                         phase=phase,
                                         deposit_amount=deposit_amount, 
                                         deposit_currency=deposit_currency,
                                         token_amount=token_amount,
                                         rate=rate.rate)    

        # If error occurs, rollback changes and raise error so that Rehive
        # retries (most likeley an APIException).
        with transaction.atomic():
            # Create ICO purchase
            purchase = Purchase.objects.create(quote=quote, deposit_tx=tx_id,
                status=status)

            # Get token amount in cents for Rehive
            token_divisibility = Decimal(
                str(quote.phase.ico.currency.divisibility))
            token_cent_amount = to_cents(quote.token_amount, token_divisibility) 

            # Create asscociated token credit transaction
            token_tx = rehive.admin.transactions.create_credit(
                user=str(user.identifier),
                amount=token_cent_amount, 
                currency=quote.phase.ico.currency.code, 
                confirm_on_create=False)

            purchase.token_tx = token_tx['id']
            purchase.save()    

        return validated_data


class AdminTransactionExecuteWebhookSerializer(AdminWebhookSerializer):
    """
    Serialize execute transaction webhook data.
    """    

    def validate_event(self, event):
        if event != WebhookEvent.TRANSACTION_EXECUTE.value:
            raise serializers.ValidationError("Invalid event.")
        return event

    def validate_data(self, data):
        statuses = (PurchaseStatus.FAILED.value, 
            PurchaseStatus.COMPLETE.value)

        if data['status'] not in statuses:
            raise serializers.ValidationError("Invalid transaction status.")

        if data['tx_type'] != "credit":
            raise serializers.ValidationError("Invalid transaction type.")

        return data

    def create(self, validated_data):
        company = validated_data.get('company')
        data = validated_data.get('data')
        tx_id = data.get('id')
        status =  data.get('status')

        # Instantiate Rehive SDK
        rehive = Rehive(company.admin.token) 

        # Check if the transaction is associated to any pending purchases.
        # Ensure it is associated by only the deposit_tx.
        try:
            purchase = Purchase.objects.exclude(token_tx__isnull=True).get(
                deposit_tx=tx_id,
                status=PurchaseStatus.PENDING,
                quote__user__company=company)
        except Purchase.DoesNotExist:
            # Simply return immediately, this isn't a relevant transaction.
            # Don't raise an error otherwise Rehive webhook will keep retrying.
            return validated_data

        # If error occurs, rollback changes and raise error so that Rehive
        # retries (most likeley an APIException).
        with transaction.atomic():
            # Update ICO purchase status.
            purchase.status = status
            purchase.save()

            # Update associated Rehive transaction.
            rehive.admin.transactions.patch(purchase.token_tx, status)

        return validated_data


class AdminCurrencySerializer(serializers.ModelSerializer):
    """
    Serialize currency.
    """

    class Meta:
        model = Currency
        fields = ('code', 'description', 'symbol', 'unit', 'divisibility', 
            'enabled')


class AdminCompanySerializer(serializers.ModelSerializer):
    """
    Serialize company, update and delete.
    """

    identifier = serializers.CharField(read_only=True)
    secret = serializers.UUIDField(read_only=True)
    token = serializers.CharField(read_only=True, source='admin.token')
    name = serializers.CharField()

    class Meta:
        model = Company
        fields = ('identifier', 'secret', 'token', 'name',)

    def update(self, instance, validated_data):
        for key, value in validated_data.items():
            setattr(instance, key, value)

        instance.save()
        return instance


class AdminCreateIcoSerializer(serializers.ModelSerializer):
    """
    Serialize ico, create
    """

    amount = serializers.IntegerField()
    currency = serializers.CharField()
    base_goal_amount = serializers.IntegerField()
    base_currency = serializers.CharField()

    class Meta:
        model = Ico
        fields = ('currency', 'amount', 'exchange_provider', 'base_currency', 
            'base_goal_amount', 'enabled')

    def validate_currency(self, currency):
        company = self.context['request'].user.company

        try:
            return Currency.objects.get(code__iexact=currency, company=company, 
                enabled=True)  
        except Currency.DoesNotExist:
            raise serializers.ValidationError("Invalid currency.")

    def validate_base_currency(self, currency):
        company = self.context['request'].user.company

        try:
            return Currency.objects.get(code__iexact=currency, company=company, 
                enabled=True)  
        except Currency.DoesNotExist:
            raise serializers.ValidationError("Invalid currency.")

    def create(self, validated_data):
        validated_data['company'] = self.context['request'].user.company

        validated_data['amount'] = from_cents(
            amount=validated_data['amount'],
            divisibility=validated_data['currency'].divisibility)

        validated_data['base_goal_amount'] = from_cents(
            amount=validated_data['base_goal_amount'],
            divisibility=validated_data['base_currency'].divisibility)

        # TODO: Also create transaction webhooks. 
        # Use rehive sdk to create a initiate and execute webhook. 
        #    1) event: transaction.execute
        #       url: http://localhost:8000/api/admin/webhooks/execute/
        #       tx_type: credit
        #       secret: company.secret
        #    2) event: transaction.initiate
        #       url: http://localhost:8000/api/admin/webhooks/initiate/
        #       tx_type: credit
        #       secret: company.secret

        return Ico.objects.create(**validated_data)


class AdminIcoSerializer(serializers.ModelSerializer, DatesMixin):
    """
    Serialize ico, update and delete.
    """

    currency = AdminCurrencySerializer(read_only=True)
    base_currency = AdminCurrencySerializer(read_only=True)
    amount = serializers.SerializerMethodField()
    base_goal_amount = serializers.SerializerMethodField()

    class Meta:
        model = Ico
        fields = ('id', 'currency', 'amount', 'exchange_provider', 'base_currency',
            'base_goal_amount', 'enabled', 'created', 'updated')
        read_only_fields = ('id', 'currency', 'amount', 'base_currency',
            'base_goal_amount', 'created', 'updated')

    def get_amount(self, obj):
        return to_cents(obj.amount, obj.currency.divisibility)

    def get_base_goal_amount(self, obj):
        return to_cents(obj.base_goal_amount, obj.base_currency.divisibility)

    def update(self, instance, validated_data):
        for key, value in validated_data.items():
            setattr(instance, key, value)

        instance.save()
        return instance

    def delete(self):
        instance = self.instance
        instance.delete()


class AdminPhaseSerializer(serializers.ModelSerializer):
    base_rate = serializers.SerializerMethodField()

    class Meta:
        model = Phase
        fields = ('id', 'level', 'percentage', 'base_rate',)

    def get_base_rate(self, obj):
        return to_cents(obj.base_rate, obj.ico.base_currency.divisibility)

    def update(self, instance, validated_data):
        for key, value in validated_data.items():
            setattr(instance, key, value)

        instance.save()
        return instance

    def delete(self):
        instance = self.instance
        instance.delete()


class AdminCreatePhaseSerializer(serializers.ModelSerializer):
    level = serializers.IntegerField(min_value=1, max_value=7)
    percentage = serializers.IntegerField(min_value=1, max_value=100)

    class Meta:
        model = Phase
        fields = ('level', 'percentage', 'base_rate',)

    def validate(self, validated_data):
        company = self.context['request'].user.company
        ico_id = self.context.get('view').kwargs.get('ico_id')

        try:
            ico = Ico.objects.get(company=company, id=ico_id)
        except Ico.DoesNotExist:
            raise exceptions.NotFound()

        if (Phase.objects.filter(ico=ico).aggregate(
                total=Coalesce(models.Sum('percentage'), 0))['total'] 
                >= 100):
            raise serializers.ValidationError(
                {"non_field_errors": 
                    ["Cannoy have a higher total phase percentage than 100."]})

        validated_data['ico'] = ico

        return validated_data

    def create(self, validated_data):
        validated_data['base_rate'] = from_cents(
            amount=validated_data['base_rate'],
            divisibility=validated_data['ico'].base_currency.divisibility)

        return super(AdminCreatePhaseSerializer, self).create(validated_data)


class AdminRateSerializer(serializers.ModelSerializer, DatesMixin):
    currency = AdminCurrencySerializer(read_only=True)
    rate = serializers.SerializerMethodField()

    class Meta:
        model = Rate
        fields = ('id', 'currency', 'rate', 'created', 'updated')

    def get_rate(self, obj):
        return to_cents(obj.rate, obj.currency.divisibility)


class AdminQuoteSerializer(serializers.ModelSerializer, DatesMixin):
    user = serializers.CharField()
    deposit_currency = AdminCurrencySerializer(read_only=True)
    deposit_amount = serializers.SerializerMethodField()
    token_amount = serializers.SerializerMethodField()
    rate = serializers.SerializerMethodField()

    class Meta:
        model = Quote
        fields = ('id', 'user', 'phase', 'deposit_amount', 'deposit_currency',
            'token_amount', 'rate', 'created', 'updated')

    def get_deposit_amount(self, obj):
        return to_cents(obj.deposit_amount, obj.deposit_currency.divisibility)

    def get_token_amount(self, obj):
        return to_cents(obj.token_amount, obj.deposit_currency.divisibility)

    def get_rate(self, obj):
        return to_cents(obj.rate, obj.deposit_currency.divisibility)


class AdminPurchaseSerializer(serializers.ModelSerializer, DatesMixin):
    quote = AdminQuoteSerializer(read_only=True)
    phase = serializers.IntegerField(source='quote.phase.level')
    status = serializers.ChoiceField(choices=PurchaseStatus.choices(),
        source='status.value')

    class Meta:
        model = Purchase
        fields = ('quote', 'phase', 'deposit_tx', 'token_tx', 'status',
                  'created', 'updated')


class UserIcoSerializer(serializers.ModelSerializer):
    """
    Serialize ico, update and delete.
    """

    currency = AdminCurrencySerializer(read_only=True)
    base_currency = AdminCurrencySerializer(read_only=True)

    class Meta:
        model = Ico
        fields = ('id', 'currency', 'amount', 'base_currency', 'enabled')

    def get_base_goal_amount(self, obj):
        return to_cents(obj.base_goal_amount, obj.base_currency.divisibility)


class UserRateSerializer(serializers.ModelSerializer, DatesMixin):
    currency = AdminCurrencySerializer(read_only=True)
    rate = serializers.SerializerMethodField()

    class Meta:
        model = Rate
        fields = ('id', 'currency', 'rate', 'created', 'updated')

    def get_rate(self, obj):
        return to_cents(obj.rate, obj.currency.divisibility)


class UserCreateQuoteSerializer(serializers.ModelSerializer):
    deposit_amount = serializers.IntegerField(required=False)
    deposit_currency = serializers.CharField()
    token_amount = serializers.IntegerField(required=False)

    class Meta:
        model = Quote
        fields = ('deposit_amount', 'deposit_currency', 'token_amount',)

    def validate_deposit_currency(self, currency):
        company = self.context['request'].user.company

        try:
            return Currency.objects.get(code__iexact=currency, company=company, 
                enabled=True)  
        except Currency.DoesNotExist:
            raise serializers.ValidationError("Invalid currency.")

    def validate(self, validated_data):
        user = self.context['request'].user
        ico_id = self.context.get('view').kwargs.get('ico_id')

        # Check that only one amount exists.
        deposit_amount = validated_data.get('deposit_amount')
        token_amount = validated_data.get('token_amount')

        if not deposit_amount and not token_amount:
            raise serializers.ValidationError(
                {"non_field_errors": 
                    ["A deposit amount or token amount must be inserted."]})            

        if deposit_amount and token_amount:
            raise serializers.ValidationError(
                {"non_field_errors": 
                    ["only deposit amount or token amount must be inserted."]})

        # Find a live ICO.
        try:
            ico = Ico.objects.get(company=user.company, id=ico_id, enabled=True)

            if not ico.enabled:
                raise serializers.ValidationError(
                    {"non_field_errors": ["The ICO is disabled."]})                

        except Ico.DoesNotExist:
            raise exceptions.NotFound()

        # Find a phase if one exists for the ICO, otherwise throw an error.
        try:
            phase = ico.get_phase()
        except Phase.DoesNotExist:
            raise serializers.ValidationError(
                {"non_field_errors": ["The ICO has no active phases."]})

        validated_data['phase'] = phase

        return validated_data       

    def create(self, validated_data):
        user = self.context['request'].user

        deposit_amount = validated_data.get('deposit_amount')
        token_amount = validated_data.get('token_amount')
        deposit_currency = validated_data.get('deposit_currency')
        phase = validated_data.get('phase')

        # Deposit rate
        rate = Rate.objects.get(phase=phase, currency=deposit_currency)

        # If a deposit amount is submitted than a ICO token amount needs to be 
        # calculated.
        if deposit_amount and not token_amount:
            deposit_amount = from_cents(deposit_amount, 
                deposit_currency.divisibility)

            token_amount = Decimal(deposit_amount / rate.rate)

        # If an ICO token amount is submitted than a deposit amount needs to be 
        # calculated instead.
        elif token_amount and not deposit_amount:
            token_amount = from_cents(token_amount, 
                phase.ico.currency.divisibility)
            deposit_amount = Decimal(token_amount * rate.rate)

        create_data = {
            "user": user,
            "phase": phase,
            "deposit_amount": deposit_amount,
            "deposit_currency": deposit_currency,
            "token_amount": token_amount,
            "rate": rate.rate,
        }

        return super(UserCreateQuoteSerializer, self).create(create_data)


class UserQuoteSerializer(serializers.ModelSerializer, DatesMixin):
    deposit_currency = AdminCurrencySerializer(read_only=True)
    deposit_amount = serializers.SerializerMethodField()
    token_amount = serializers.SerializerMethodField()
    token_currency = AdminCurrencySerializer(read_only=True, 
        source='phase.ico.currency')
    rate = serializers.SerializerMethodField()

    class Meta:
        model = Quote
        fields = ('id', 'phase', 'deposit_amount', 'deposit_currency', 
            'token_amount', 'token_currency', 'rate', 'created', 'updated')

    def get_deposit_amount(self, obj):
        return to_cents(obj.deposit_amount, obj.deposit_currency.divisibility)

    def get_token_amount(self, obj):
        return to_cents(obj.token_amount, obj.phase.ico.currency.divisibility)

    def get_rate(self, obj):
        return to_cents(obj.rate, obj.deposit_currency.divisibility)


class UserPurchaseSerializer(serializers.ModelSerializer, DatesMixin):
    quote = UserQuoteSerializer(read_only=True)
    status = serializers.ChoiceField(choices=PurchaseStatus.choices(),
        source='status.value')

    class Meta:
        model = Purchase
        fields = ('id', 'quote', 'deposit_tx', 'token_tx', 'status',
                  'created', 'updated')
