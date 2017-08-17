import json
import uuid

from rest_framework import serializers
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
    email = serializers.CharField(read_only=True)
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
            currencies = rehive.currencies.get()
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

        try:
            with transaction.atomic():
                user = User.objects.create(token=token,
                    identifier=uuid.UUID(rehive_user['identifier']).hex)

                company = Company.objects.create(owner=user, 
                    identifier=rehive_company.get('identifier'),
                    email=rehive_company.get('company_email'),
                    name=rehive_company.get('name'))

                user.company = company
                user.save()

                # Add currencies to company automatically.
                for kwargs in currencies:
                    kwargs['company'] = company
                    currency = Currency.objects.create(**kwargs)

                return company

        except Exception as exc:
            raise serializers.ValidationError(exc)


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
        fields = ('code', 'description', 'symbol', 'unit', 'divisibility',)


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

    company = serializers.CharField()

    class Meta:
        model = Ico
        fields = ('currency', 'exchange_provider', 'fiat_currency', 
            'fiat_goal_amount', 'enabled')
        
    def validate_currency(self, currency):
        company = self.context['request'].user.company

        try:
            return Currency.objects.get(code__iexact=currency, company=company, 
                enabled=True)  
        except Currency.DoesNotExist:
            raise serializers.ValidationError("Invalid currency.")

    def validate_fiat_currency(seld, currency):
        company = self.context['request'].user.company

        try:
            return Currency.objects.get(code__iexact=currency, company=company, 
                enabled=True)  
        except Currency.DoesNotExist:
            raise serializers.ValidationError("Invalid currency.")

    def create(self, validated_data):
        validated_data['company'] = self.context['request'].user.company
        return Notification.objects.create(**validated_data)


class AdminIcoSerializer(serializers.ModelSerializer):
    """
    Serialize ico, update and delete.
    """
    
    class Meta:
        model = Ico
        fields = ('id', 'currency', 'exchange_provider', 'fiat_currency', 
            'fiat_goal_amount', 'enabled')
        read_only_field = ('id', 'currency', 'fiat_currency', 
            'fiat_goal_amount',)

    def update(self, instance, validated_data):
        for key, value in validated_data.items():
            setattr(instance, key, value)

        instance.save()
        return instance

    def delete(self):
        instance = self.instance
        instance.delete()