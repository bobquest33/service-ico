import json
import uuid
import datetime
import decimal
from decimal import Decimal

from rest_framework import serializers, exceptions
from rest_framework.serializers import ModelSerializer
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist

from ico.models import *
from ico.exceptions import SilentException
from ico.enums import WebhookEvent, PurchaseStatus, IcoStatus
from ico.authentication import HeaderAuthentication
from rehive import Rehive, APIException
from ico.utils.common import (
    to_cents, from_cents
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
            if "admin" not in [p['name']for p in user['permission_groups']]:
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
            if "admin" not in [p['name']for p in user['permission_groups']]:
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

        try:
            Purchase.objects.initiate_purchase(company, data)            
        except SilentException:
            return validated_data
        except ObjectDoesNotExist as exc:
            raise serializers.ValidationError({"non_field_errors": str(exc)})

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

        try:
            Purchase.objects.execute_purchase(company, data)            
        except SilentException:
            return validated_data
        except ObjectDoesNotExist as exc:
            raise serializers.ValidationError({"non_field_errors": str(exc)})

        return validated_data


class CurrencySerializer(serializers.ModelSerializer):
    """
    Serialize currency.
    """

    class Meta:
        model = Currency
        fields = ('code', 'description', 'symbol', 'unit', 'divisibility', 
            'enabled')


class IcoSerializer(serializers.ModelSerializer, DatesMixin):
    """
    Serialize public ico information.
    """

    currency = CurrencySerializer()
    base_currency = CurrencySerializer()
    amount = serializers.SerializerMethodField()
    company = serializers.CharField(source='company.identifier')
    amount_remaining = serializers.SerializerMethodField()
    base_goal_amount = serializers.SerializerMethodField()
    min_purchase_amount = serializers.SerializerMethodField()
    max_purchase_amount = serializers.SerializerMethodField()
    active_phase = serializers.SerializerMethodField()
    status = serializers.ChoiceField(choices=IcoStatus.choices(), 
        required=False, source='status.value')

    class Meta:
        model = Ico
        fields = ('id', 'currency', 'amount', 'amount_remaining', 
            'base_currency', 'base_goal_amount',
            'min_purchase_amount', 'max_purchase_amount', 'company',
            'max_purchases', 'active_phase', 'status', 'public', 'created', 
            'updated',)

    def get_amount(self, obj):
        return to_cents(obj.amount, obj.currency.divisibility)

    def get_amount_remaining(self, obj):
        return to_cents(obj.amount_remaining, obj.currency.divisibility)

    def get_base_goal_amount(self, obj):
        return to_cents(obj.base_goal_amount, obj.base_currency.divisibility)

    def get_min_purchase_amount(self, obj):
        return to_cents(obj.min_purchase_amount, obj.currency.divisibility)

    def get_max_purchase_amount(self, obj):
        return to_cents(obj.max_purchase_amount, obj.currency.divisibility)

    def get_active_phase(self, obj):
        try:
            phase = obj.get_phase()
            return AdminPhaseSerializer(phase, context=self.context).data

        except Phase.DoesNotExist:
            return None


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


class AdminCreateIcoSerializer(IcoSerializer):
    """
    Serialize ico, create
    """

    amount = serializers.IntegerField()
    currency = serializers.CharField()
    base_goal_amount = serializers.IntegerField()
    base_currency = serializers.CharField()
    min_purchase_amount = serializers.IntegerField(required=False)
    max_purchase_amount = serializers.IntegerField(required=False)
    max_purchases = serializers.IntegerField(required=False)

    class Meta:
        model = Ico
        fields = ('currency', 'amount', 'exchange_provider', 'base_currency', 
            'base_goal_amount', 'min_purchase_amount', 'max_purchase_amount',
            'max_purchases', 'status', 'public')

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

        if validated_data.get('status'):
            validated_data['status'] = IcoStatus(
                validated_data['status']['value'])

        try:
            validated_data['amount'] = from_cents(
                amount=validated_data['amount'],
                divisibility=validated_data['currency'].divisibility)            
            Decimal(validated_data['amount']).quantize(Decimal(".1") ** 18)
        except decimal.InvalidOperation:
            raise serializers.ValidationError(
                {"amount": ["Unsupported number size."]})   

        try:
            validated_data['base_goal_amount'] = from_cents(
                amount=validated_data['base_goal_amount'],
                divisibility=validated_data['base_currency'].divisibility)
            Decimal(validated_data['base_goal_amount']).quantize(Decimal(".1") ** 18)
        except decimal.InvalidOperation:
            raise serializers.ValidationError(
                {"base_goal_amount": ["Unsupported number size."]})   

        if validated_data.get('min_purchase_amount'):
            try:
                validated_data['min_purchase_amount'] = from_cents(
                    amount=validated_data['min_purchase_amount'],
                    divisibility=validated_data['currency'].divisibility)     
                Decimal(validated_data['min_purchase_amount']).quantize(Decimal(".1") ** 18)
            except decimal.InvalidOperation:
                raise serializers.ValidationError(
                    {"min_purchase_amount": ["Unsupported number size."]})   

        if validated_data.get('max_purchase_amount'):
            try:
                validated_data['max_purchase_amount'] = from_cents(
                    amount=validated_data['max_purchase_amount'],
                    divisibility=validated_data['currency'].divisibility)     
                Decimal(validated_data['max_purchase_amount']).quantize(Decimal(".1") ** 18)
            except decimal.InvalidOperation:
                raise serializers.ValidationError(
                    {"max_purchase_amount": ["Unsupported number size."]})   

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

    currency = CurrencySerializer(read_only=True)
    base_currency = CurrencySerializer(read_only=True)
    amount = serializers.SerializerMethodField()
    amount_remaining = serializers.SerializerMethodField()
    base_goal_amount = serializers.SerializerMethodField()
    min_purchase_amount = serializers.SerializerMethodField()
    max_purchase_amount = serializers.SerializerMethodField()
    active_phase = serializers.SerializerMethodField()
    status = serializers.ChoiceField(choices=IcoStatus.choices(), 
        required=False, source='status.value')

    class Meta:
        model = Ico
        fields = ('id', 'currency', 'amount', 'amount_remaining', 
            'exchange_provider', 'base_currency', 'base_goal_amount',
            'min_purchase_amount', 'max_purchase_amount',
            'max_purchases', 'active_phase', 'status', 'public', 'created', 
            'updated')
        read_only_fields = ('id', 'currency', 'amount', 'amount_remaining', 
            'base_currency', 'base_goal_amount', 'active_phase', 'created', 
            'updated')

    def get_amount(self, obj):
        return to_cents(obj.amount, obj.currency.divisibility)

    def get_amount_remaining(self, obj):
        return to_cents(obj.amount_remaining, obj.currency.divisibility)

    def get_base_goal_amount(self, obj):
        return to_cents(obj.base_goal_amount, obj.base_currency.divisibility)

    def get_min_purchase_amount(self, obj):
        return to_cents(obj.min_purchase_amount, obj.currency.divisibility)

    def get_max_purchase_amount(self, obj):
        return to_cents(obj.max_purchase_amount, obj.currency.divisibility)

    def get_active_phase(self, obj):
        try:
            phase = obj.get_phase()
            return AdminPhaseSerializer(phase, context=self.context).data

        except Phase.DoesNotExist:
            return None

    def delete(self):
        instance = self.instance
        instance.deleted = True
        instance.save()


class AdminUpdateIcoSerializer(AdminIcoSerializer):
    min_purchase_amount = serializers.IntegerField()
    max_purchase_amount = serializers.IntegerField()

    def update(self, instance, validated_data):
        if validated_data.get('status'):
            validated_data['status'] = IcoStatus(
                validated_data['status']['value'])
        
        if validated_data.get('min_purchase_amount'):
            try:
                validated_data['min_purchase_amount'] = from_cents(
                    amount=validated_data['min_purchase_amount'],
                    divisibility=instance.currency.divisibility)     
                Decimal(validated_data['min_purchase_amount']).quantize(Decimal(".1") ** 18)
            except decimal.InvalidOperation:
                raise serializers.ValidationError(
                    {"min_purchase_amount": ["Unsupported number size."]})   

        if validated_data.get('max_purchase_amount'):
            try:
                validated_data['max_purchase_amount'] = from_cents(
                    amount=validated_data['max_purchase_amount'],
                    divisibility=instance.currency.divisibility)     
                Decimal(validated_data['max_purchase_amount']).quantize(Decimal(".1") ** 18)
            except decimal.InvalidOperation:
                raise serializers.ValidationError(
                    {"max_purchase_amount": ["Unsupported number size."]})   

        for key, value in validated_data.items():
            setattr(instance, key, value)

        instance.save()
        return instance


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
        instance.deleted = True
        instance.save()


class AdminCreatePhaseSerializer(serializers.ModelSerializer):
    level = serializers.IntegerField(min_value=1, max_value=7)
    percentage = serializers.IntegerField(min_value=1, max_value=100)
    base_rate = serializers.IntegerField()

    class Meta:
        model = Phase
        fields = ('level', 'percentage', 'base_rate',)

    def validate(self, validated_data):
        company = self.context['request'].user.company
        ico_id = self.context.get('view').kwargs.get('ico_id')
        percentage = validated_data.get('percentage')

        try:
            ico = Ico.objects.get(company=company, id=ico_id)
        except Ico.DoesNotExist:
            raise exceptions.NotFound()

        existing_percentage = Phase.objects.filter(ico=ico).aggregate(
            total=Coalesce(models.Sum('percentage'), 0))['total'] 

        if ((existing_percentage + percentage) > 100):
            raise serializers.ValidationError(
                {"non_field_errors": 
                    ["Cannot have a higher total phase percentage than 100."]})

        validated_data['ico'] = ico

        return validated_data

    def create(self, validated_data):
        base_rate = from_cents(
            amount=validated_data['base_rate'],
            divisibility=validated_data['ico'].base_currency.divisibility)

        try:
            Decimal(base_rate).quantize(Decimal(".1") ** 18)
        except decimal.InvalidOperation:
            raise serializers.ValidationError(
                {"base_rate": ["Unsupported number size."]})  

        validated_data['base_rate'] = base_rate

        return super(AdminCreatePhaseSerializer, self).create(validated_data)


class AdminRateSerializer(serializers.ModelSerializer, DatesMixin):
    currency = CurrencySerializer(read_only=True)
    rate = serializers.SerializerMethodField()

    class Meta:
        model = Rate
        fields = ('id', 'currency', 'rate', 'created', 'updated')

    def get_rate(self, obj):
        return to_cents(obj.rate, obj.currency.divisibility)


class AdminQuoteSerializer(serializers.ModelSerializer, DatesMixin):
    user = serializers.CharField()
    deposit_currency = CurrencySerializer(read_only=True)
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


class PurchaseMessageSerializer(serializers.ModelSerializer, DatesMixin):
    message = serializers.CharField(read_only=True)

    class Meta:
        model = PurchaseMessage
        fields = ('message', 'created',)


class AdminPurchaseSerializer(serializers.ModelSerializer, DatesMixin):
    quote = AdminQuoteSerializer(read_only=True)
    phase = serializers.IntegerField(source='quote.phase.level')
    status = serializers.ChoiceField(choices=PurchaseStatus.choices(),
        source='status.value')
    metadata = serializers.JSONField(read_only=True)
    messages = PurchaseMessageSerializer(many=True, read_only=True)

    class Meta:
        model = Purchase
        fields = ('id', 'quote', 'phase', 'deposit_tx', 'token_tx', 'status',
                  'metadata', 'messages', 'created', 'updated')


class UserIcoSerializer(IcoSerializer):
    """
    Serialize ico, update and delete.
    """

    class Meta:
        model = Ico
        fields = ('id', 'currency', 'amount', 'amount_remaining', 
            'base_currency', 'base_goal_amount',
            'min_purchase_amount', 'max_purchase_amount',
            'max_purchases', 'active_phase', 'status', 'public', 'created', 
            'updated',)


class UserRateSerializer(serializers.ModelSerializer, DatesMixin):
    currency = CurrencySerializer(read_only=True)
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
            ico = Ico.objects.get(company=user.company, id=ico_id)

            if ico.status != IcoStatus.OPEN:
                raise serializers.ValidationError(
                    {"non_field_errors": ["The ICO is closed."]})                

        except Ico.DoesNotExist:
            raise exceptions.NotFound()

        # Find a phase if one exists for the ICO, otherwise throw an error.
        try:
            phase = ico.get_phase()
        except Phase.DoesNotExist:
            raise serializers.ValidationError(
                {"non_field_errors": ["The ICO has no active phases."]})

        validated_data['phase'] = phase

        # Stop quotes if max_purchases is exceeded.
        total_purchases = user.quote_set.exclude(purchase=None).filter(
            phase__ico=ico).count()

        if total_purchases >= ico.max_purchases: 
            raise serializers.ValidationError(
                {"non_field_errors": 
                    ["You have reached the max purchases allowed."]})   

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

        # Final validation on amounts.
        if (phase.ico.max_purchase_amount > 0
                and token_amount > phase.ico.max_purchase_amount):
            raise serializers.ValidationError(
                {"token_amount": ["Amount exceeds the max purchase amount."]})

        if (phase.ico.min_purchase_amount > 0
                and token_amount < phase.ico.min_purchase_amount):
            raise serializers.ValidationError(
                {"token_amount": ["Amount is below the min purchase amount."]})

        if deposit_amount < from_cents(1, deposit_currency.divisibility):
            raise serializers.ValidationError(
                {'deposit_amount': [
                    'Deposit amount is below the min amount '
                    'of {currency} {deposit_amount}.'
                    .format(
                        deposit_amount=from_cents(1, deposit_currency.divisibility),
                        currency=deposit_currency
                    )]})

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
    deposit_currency = CurrencySerializer(read_only=True)
    deposit_amount = serializers.SerializerMethodField()
    token_amount = serializers.SerializerMethodField()
    token_currency = CurrencySerializer(read_only=True, 
        source='phase.ico.currency')
    rate = serializers.SerializerMethodField()

    class Meta:
        model = Quote
        fields = ('id', 'phase', 'deposit_amount', 'deposit_currency', 
            'token_amount', 'token_currency', 'rate', 'created', 'updated',)

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
    metadata = serializers.JSONField(read_only=True)
    messages = PurchaseMessageSerializer(many=True, read_only=True)

    class Meta:
        model = Purchase
        fields = ('id', 'quote', 'deposit_tx', 'token_tx', 'status', 'metadata',
            'messages', 'created', 'updated',)
