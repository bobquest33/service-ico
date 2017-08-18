import datetime
import uuid
from enumfields import EnumField
from decimal import Decimal

from django.db import models
from django.utils.timezone import utc
from django.template import Template
from django.template import Context

from ico.enums import PurchaseStatus

from logging import getLogger

logger = getLogger('django')


class MoneyField(models.DecimalField):
    """
    Decimal Field with hardcoded precision of 28 and a scale of 18.
    """

    def __init__(self, verbose_name=None, name=None, max_digits=28,
                 decimal_places=18, **kwargs):
        super(MoneyField, self).__init__(verbose_name, name, max_digits,
            decimal_places, **kwargs)


class DateModel(models.Model):
    created = models.DateTimeField()
    updated = models.DateTimeField()

    class Meta:
        abstract = True

    def __str__(self):
        return str(self.created)

    def save(self, *args, **kwargs):
        if not self.id:  # On create
            self.created = datetime.datetime.now(tz=utc)

        self.updated = datetime.datetime.now(tz=utc)
        return super(DateModel, self).save(*args, **kwargs)


class Company(DateModel):
    identifier = models.CharField(max_length=100, unique=True, db_index=True)
    admin = models.OneToOneField('ico.User', related_name='admin_company')
    secret = models.UUIDField()
    name = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return self.identifier

    def natural_key(self):
        return (self.identifier,)

    def save(self, *args, **kwargs):
        if not self.id:
            self.secret = uuid.uuid4()

        return super(Company, self).save(*args, **kwargs)


class User(DateModel):
    identifier = models.UUIDField()
    token = models.CharField(max_length=200, null=True)
    company = models.ForeignKey('ico.Company', null=True)

    def __str__(self):
        return str(self.identifier)


class Currency(DateModel):
    company = models.ForeignKey('ico.Company')
    code = models.CharField(max_length=12, db_index=True)
    description = models.CharField(max_length=50, null=True, blank=True)
    symbol = models.CharField(max_length=30, null=True, blank=True)
    unit = models.CharField(max_length=30, null=True, blank=True)
    divisibility = models.IntegerField(default=2)
    enabled = models.BooleanField(default=True)

    def __str__(self):
        return str(self.code)


class Ico(DateModel):
    company = models.ForeignKey('ico.Company')
    number = models.IntegerField()
    currency = models.ForeignKey('ico.Currency', related_name='ico')
    exchange_provider = models.CharField(max_length=200, null=True)
    fiat_currency = models.ForeignKey('ico.Currency', related_name='ico_fiat') # Base fiat currency for conversion rates, should be unchangable
    fiat_goal_amount = MoneyField(default=Decimal(0)) # Goal in base fiat currency, should be unchangable
    enabled = models.BooleanField(default=False)    

    def __str__(self):
        return str(self.currency) + "_" + str(self.company)


class Phase(DateModel):
    ico = models.ForeignKey('ico.Ico')
    level = models.IntegerField()
    percentage = models.IntegerField(default=100)
    fiat_rate = MoneyField(default=Decimal(0))

    def __str__(self):
        return str(self.level)


class Rate(DateModel):
    phase = models.ForeignKey('ico.Phase')
    currency = models.ForeignKey('ico.Currency')
    rate = MoneyField(default=Decimal(0))


class Quote(DateModel):
    phase = models.ForeignKey('ico.Phase')
    user = models.ForeignKey('ico.User')
    deposit_amount = MoneyField(default=Decimal(0))
    token_amount = MoneyField(default=Decimal(0))
    rate = MoneyField(default=Decimal(0)) # Rate of conversion between deposit currency and 1 token at time of quote.


class Purchase(DateModel):
    quote = models.ForeignKey('ico.Quote')
    desposit_tx = models.CharField(max_length=200, null=True)
    token_tx = models.CharField(max_length=200, null=True)
    status = EnumField(PurchaseStatus, max_length=50)