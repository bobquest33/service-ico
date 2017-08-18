import datetime
import uuid
from enumfields import EnumField
from decimal import Decimal

from django.db import models
from django.utils.timezone import utc

from ico.enums import PurchaseStatus
from ico.rates import get_crypto_rates, get_fiat_rates

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

    def calculate_rate(self):
        """
        Calculate the rate based on the most recent rates data
        from the exchange. Calculations are done with relation to the
        ICO currency itself, or USD.

        All exchange fiat rates are USD based which, going forward, will be
        referred to as "forward" rates and the inverse as the "backwards" rate.
        Eg.
            Forward: USD -> EUR
            Backward: EUR -> USD

        The same is done with crypto currency pairs (symbols), which are only
        listed in one direction.
        Eg.
            Forward: ETHBTC
            Backward: BTCETH
        """

        # Get the updated rates from the exchange or caches
        crypto_rates = get_crypto_rates()
        fiat_rates = get_fiat_rates()

        # The ICO currency is worth one of itself
        if self.currency == self.phase.ico.currency:
            self.rate = 1

        # This is the rate set in the phase so already has the proper rate
        elif self.currency == self.phase.ico.fiat_currency:
            self.rate = self.phase.fiat_rate

        else:
            currency_code = self.currency.code

            # The exchange lists bitcoin as BTC not XBT
            if self.currency.code == 'XBT':
                currency_code = 'BTC'

            if currency_code in fiat_rates.keys():
                fiat_rate = Decimal(fiat_rates[currency_code]['rate'])

                if self.phase.ico.currency.code == 'USD':
                    # "Forward" checking of the rates symbol since they
                    # are USD based. Do the normal rate calculation.
                    self.rate = fiat_rate * self.phase.fiat_rate
                else:
                    # Inverse calculation to get the rate with
                    # relation to USD.
                    self.rate = (1 / fiat_rate) * self.phase.fiat_rate

            else:
                ico_fiat_currency_code = self.phase.ico.fiat_currency.code

                # The exchange lists bitcoin as BTC not XBT
                if self.phase.ico.fiat_currency.code == 'XBT':
                    ico_fiat_currency_code = 'BTC'

                # For crypto currencies the rates are listed in
                # currency pairs (symbols), in which case we would need to
                # check them both ways because they are only listed
                # in one "direction"
                symbol = currency_code + ico_fiat_currency_code
                reverse_symbol = ico_fiat_currency_code + currency_code

                if symbol in crypto_rates.keys():
                    # "Forward" checking of the rates symbol. If it
                    # matches do the normal rate calculation
                    crypto_rate = crypto_rates[symbol]['last']
                    self.rate = crypto_rate * self.phase.fiat_rate

                elif reverse_symbol in crypto_rates.keys():
                    # "Backwards" checking on the rates symbol. If it
                    # matches do the inverse rate calculation
                    crypto_rate = crypto_rates[reverse_symbol]['last']
                    self.rate = (1 / crypto_rate) * self.phase.fiat_rate

        self.save()


class Quote(DateModel):
    phase = models.ForeignKey('ico.Phase')
    user = models.ForeignKey('ico.User')
    deposit_amount = MoneyField(default=Decimal(0))
    deposit_currency = models.ForeignKey('ico.Currency')
    token_amount = MoneyField(default=Decimal(0))
    rate = MoneyField(default=Decimal(0)) # Rate of conversion between deposit currency and 1 token at time of quote.


class Purchase(DateModel):
    quote = models.ForeignKey('ico.Quote')
    desposit_tx = models.CharField(max_length=200, null=True)
    token_tx = models.CharField(max_length=200, null=True)
    status = EnumField(PurchaseStatus, max_length=50)