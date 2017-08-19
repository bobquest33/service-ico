import json
import uuid

from rest_framework import serializers, exceptions
from rest_framework.serializers import ModelSerializer
from django.db import transaction

from ico.models import *
from ico.enums import WebhookEvent
from ico.authentication import HeaderAuthentication
from rehive import Rehive, APIException

from logging import getLogger

logger = getLogger('django')


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


class AdminWebhookSerializer(serializers.Serializer):
    """
    Validate and serialize the webhook data. The secret key and company are
    used to identify a specific company.
    """

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

    currency = serializers.CharField()
    fiat_currency = serializers.CharField()

    class Meta:
        model = Ico
        fields = ('currency', 'number', 'exchange_provider', 'fiat_currency', 
            'fiat_goal_amount', 'enabled')
        
    def validate_currency(self, currency):
        company = self.context['request'].user.company

        try:
            return Currency.objects.get(code__iexact=currency, company=company, 
                enabled=True)  
        except Currency.DoesNotExist:
            raise serializers.ValidationError("Invalid currency.")

    def validate_fiat_currency(self, currency):
        company = self.context['request'].user.company

        try:
            return Currency.objects.get(code__iexact=currency, company=company, 
                enabled=True)  
        except Currency.DoesNotExist:
            raise serializers.ValidationError("Invalid currency.")

    def create(self, validated_data):
        validated_data['company'] = self.context['request'].user.company
        return Ico.objects.create(**validated_data)


class AdminIcoSerializer(serializers.ModelSerializer):
    """
    Serialize ico, update and delete.
    """

    currency = serializers.CharField(read_only=True)
    fiat_currency = serializers.CharField(read_only=True)
    
    class Meta:
        model = Ico
        fields = ('id', 'currency', 'number', 'exchange_provider', 'fiat_currency', 
            'fiat_goal_amount', 'enabled')
        read_only_field = ('id', 'currency', 'number', 'fiat_currency', 
            'fiat_goal_amount',)

    def update(self, instance, validated_data):
        for key, value in validated_data.items():
            setattr(instance, key, value)

        instance.save()
        return instance

    def delete(self):
        instance = self.instance
        instance.delete()


class AdminPhaseSerializer(serializers.ModelSerializer):

    class Meta:
        model = Phase
        fields = ('id', 'level', 'percentage', 'fiat_rate',)

    def create(self, validated_data):
        company = self.context.get('request').user.company
        ico_id = self.context.get('view').kwargs.get('ico_id')

        try:
            validated_data['ico'] = Ico.objects.get(company=company, id=ico_id)
        except Ico.DoesNotExist:
            raise exceptions.NotFound()

        return super(AdminPhaseSerializer, self).create(validated_data)


class AdminRateSerializer(serializers.ModelSerializer):
    currency = serializers.CharField()

    class Meta:
        model = Rate
        fields = ('currency', 'rate')


class AdminQuoteSerializer(serializers.ModelSerializer):
    user = serializers.CharField()
    deposit_currency = serializers.CharField()

    class Meta:
        model = Quote
        fields = ('user', 'phase', 'deposit_amount', 'deposit_currency',
            'token_amount', 'rate',)


class AdminPurchaseSerializer(serializers.ModelSerializer):
    quote = serializers.IntegerField(source='quote.id')

    class Meta:
        model = Purchase
        fields = ('quote', 'phase', 'depost_tx', 'token_tx', 'status')


class UserIcoSerializer(serializers.ModelSerializer):
    """
    Serialize ico, update and delete.
    """

    currency = serializers.CharField(read_only=True)
    fiat_currency = serializers.CharField(read_only=True)
    
    class Meta:
        model = Ico
        fields = ('id', 'currency', 'number', 'exchange_provider', 'fiat_currency', 
            'fiat_goal_amount', 'enabled')


class UserCreateQuoteSerializer(serializers.ModelSerializer):
    deposit_amount = serializers.DecimalField(max_digits=28, decimal_places=18, 
        required=False)
    deposit_currency = serializers.CharField()
    token_amount = serializers.DecimalField(max_digits=28, decimal_places=18, 
        required=False)

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

        return validated_data       

    def create(self, validated_data):
        company = self.context.get('request').user.company
        ico_id = self.context.get('view').kwargs.get('ico_id')

        try:
            validated_data['ico'] = Ico.objects.get(company=company, id=ico_id)
        except Ico.DoesNotExist:
            raise exceptions.NotFound()

        # ----------------------------------------------------------------------
        # Do complex quote creation logic HERE
        # ----------------------------------------------------------------------

        return super(AdminPhaseSerializer, self).create(validated_data)


class UserQuoteSerializer(serializers.ModelSerializer):
    user = serializers.CharField()
    deposit_currency = serializers.CharField()

    class Meta:
        model = Quote
        fields = ('user', 'phase', 'deposit_amount', 'deposit_currency', 
            'token_amount', 'rate',)


class UserPurchaseSerializer(serializers.ModelSerializer):
    quote = serializers.IntegerField(source='quote.id')

    class Meta:
        model = Purchase
        fields = ('quote', 'phase', 'depost_tx', 'token_tx', 'status')
