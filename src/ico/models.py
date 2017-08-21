import datetime
import uuid
from enumfields import EnumField
from decimal import Decimal

from django.db import models
from django.utils.timezone import utc
from django.db.models.functions import Coalesce

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
    base_currency = models.ForeignKey('ico.Currency', related_name='ico_base')  # Base fiat currency for conversion rates, should be unchangable
    base_goal_amount = MoneyField(default=Decimal(0))  # Goal in base fiat currency, should be unchangable
    enabled = models.BooleanField(default=False)

    def __str__(self):
        return str(self.currency) + "_" + str(self.company)

    def get_phase(self):
        percent = (self.get_token_amount_sold() / self.number) * 100

        for phase in Phase.objects.filter(ico=self).order_by('level'):
            if percent < phase.percentage:
                return phase
            else:
                percent = percent - phase.percentage

        raise Phase.DoesNotExist

    def get_token_amount_sold(self):
        statuses = (PurchaseStatus.PENDING, PurchaseStatus.COMPLETE,)

        purchases = Purchase.objects.filter(quote__phase__ico=self, 
            status__in=statuses).aggregate(
                total_tokens=Coalesce(models.Sum('quote__token_amount'), 0))

        return purchases['total_tokens']


class Phase(DateModel):
    ico = models.ForeignKey('ico.Ico')
    level = models.IntegerField()
    percentage = models.IntegerField(default=100)
    base_rate = MoneyField(default=Decimal(0))

    def __str__(self):
        return str(self.level)


class RateManager(models.Manager):

    def get(self, *args, **kwargs):
        obj = super(RateManager, self).get(*args, **kwargs)
        obj.refresh_rate()
        return obj

    def filter(self, *args, **kwargs):
        queryset = super(RateManager, self).filter(*args, **kwargs)
        for rate in queryset:
            rate.refresh_rate()
        return queryset


class Rate(DateModel):
    phase = models.ForeignKey('ico.Phase')
    currency = models.ForeignKey('ico.Currency')
    rate = MoneyField(default=Decimal(0))

    objects = RateManager()

    def _calculate_crypto_rate(self, fiat_rates):
        currency_code = self.currency.code
        ico_base_currency_code = self.phase.ico.base_currency.code
        ico_exchange_rate = Decimal(fiat_rates[ico_base_currency_code]['rate'])

        # Get the updated rates from the exchange or caches
        crypto_rates = get_crypto_rates()

        # For crypto currencies the rates are listed in
        # currency pairs (symbols), in which case we would need to
        # check them both ways because they are only listed
        # in one "direction"
        symbol = ico_base_currency_code + currency_code
        reverse_symbol = currency_code + ico_base_currency_code
        check_reverse = False

        try:
            # "Forward" checking of the rates symbol. If it
            # matches do the normal rate calculation
            if not symbol.startswith('BTC'):
                # Bitcoin is treated as a fiat currency by the exchange
                crypto_rate = Decimal(crypto_rates[symbol]['last'])
                return crypto_rate * self.phase.base_rate
        except KeyError:
            check_reverse = True

        if check_reverse:
            try:
                # "Backwards" checking on the rates symbol. If it
                # matches do the inverse rate calculation
                crypto_rate = Decimal(crypto_rates[reverse_symbol]['last'])
                return (crypto_rate / ico_exchange_rate) * self.phase.base_rate
            except KeyError:
                # TODO: Call CONVERT api endpoint
                pass

    def _calculate_rate(self):
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

        # The ICO currency is worth one of itself
        if self.currency == self.phase.ico.currency:
            return 1

        # This is the rate set in the phase so already has the proper rate
        if self.currency == self.phase.ico.base_currency:
            return self.phase.base_rate

        # Get the updated rates from the exchange or caches
        fiat_rates = get_fiat_rates()
        currency_code = self.currency.code
        ico_base_currency_code = self.phase.ico.base_currency.code

        # The exchange lists bitcoin as BTC not XBT
        if self.currency.code == 'XBT':
            currency_code = 'BTC'

        try:
            ico_exchange_rate = Decimal(fiat_rates[ico_base_currency_code]['rate'])
            exchange_rate = Decimal(fiat_rates[currency_code]['rate'])
        except KeyError as exc:
            return self._calculate_crypto_rate(fiat_rates)
        else:
            if self.phase.ico.base_currency.code == 'USD':
                # "Forward" checking of the rates symbol since they
                # are USD based. Do the normal rate calculation.
                return exchange_rate * self.phase.base_rate
            else:
                # Inverse calculation to get the rate with
                # relation to USD.
                return (exchange_rate * ico_exchange_rate) * self.phase.base_rate

    def refresh_rate(self):
        self.rate = self._calculate_rate()
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
    deposit_tx = models.CharField(unique=True, max_length=200, null=True)
    token_tx = models.CharField(unique=True, max_length=200, null=True)
    status = EnumField(PurchaseStatus, max_length=50)