import datetime
import uuid
from enumfields import EnumField
from decimal import Decimal

from django.db import models
from django.db.models import Q
from django.utils.timezone import utc
from django.db.models.functions import Coalesce
from django.db import transaction
from django.contrib.postgres.fields import JSONField
from rest_framework.exceptions import ValidationError
from rehive import Rehive

from ico.exceptions import SilentException, PurchaseException
from ico.enums import PurchaseStatus
from ico.rates import get_crypto_rates, get_fiat_rates
from ico.utils.common import (
    to_cents, from_cents
)

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


class IcoManager(models.Manager):
    def get_queryset(self):
        return super(IcoManager, self)\
            .get_queryset()\
            .filter(deleted=False)


class Ico(DateModel):
    company = models.ForeignKey('ico.Company')
    amount = MoneyField(default=Decimal(0))
    amount_remaining = MoneyField(default=Decimal(0))
    currency = models.ForeignKey('ico.Currency', related_name='ico')
    exchange_provider = models.CharField(max_length=200, null=True, blank=True)
    base_currency = models.ForeignKey('ico.Currency', null=True, related_name='ico_base')  # Base fiat currency for conversion rates, should be unchangable
    base_goal_amount = MoneyField(default=Decimal(0))  # Goal in base fiat currency, should be unchangable
    min_purchase_amount = MoneyField(default=Decimal(0))
    max_purchase_amount = MoneyField(default=Decimal(0))
    max_purchases = models.IntegerField(default=10)
    enabled = models.BooleanField(default=False)
    public = models.BooleanField(default=False)
    deleted = models.BooleanField(default=False)

    objects = IcoManager()
    all_objects = models.Manager()

    def save(self, *args, **kwargs):
        # Set initial balance for the ICO.
        if not self.id:
            self.amount_remaining = self.amount

        if self.enabled:
            Ico.objects.filter(company=self.company, enabled=True).update(
                enabled=False)

        return super(Ico, self).save(*args, **kwargs)

    def __str__(self):
        return str(self.currency) + "_" + str(self.company)

    def get_phase(self):
        if self.amount_remaining > 0:
            # Percent already sold.
            perc = ((self.amount - self.amount_remaining) / self.amount) * 100

            for phase in Phase.objects.filter(ico=self).order_by('level'):
                if perc < phase.percentage:
                    return phase
                else:
                    perc = perc - phase.percentage

        raise Phase.DoesNotExist

    def deduct_amount(self, amount):
        if (self.amount_remaining - amount) < 0:
            raise PurchaseException("All ICO tokens have been sold.")

        self.amount_remaining = self.amount_remaining - amount
        self.save()


class PhaseManager(models.Manager):
    def get_queryset(self):
        return super(PhaseManager, self)\
            .get_queryset()\
            .filter(deleted=False)


class Phase(DateModel):
    ico = models.ForeignKey('ico.Ico')
    level = models.IntegerField()
    percentage = models.IntegerField(default=100)
    base_rate = MoneyField(default=Decimal(0))
    deleted = models.BooleanField(default=False)

    objects = PhaseManager()
    all_objects = models.Manager()

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

    def _calculate_crypto_rate(self):
        currency_code = self.currency.code
        ico_base_currency_code = self.phase.ico.base_currency.code

        # Get the updated rates from the exchange or caches
        crypto_rates = get_crypto_rates()

        # For crypto currencies the rates are listed in
        # currency pairs (symbols), in which case we would need to
        # check them both ways because they are only listed
        # in one "direction"
        symbol = currency_code + ico_base_currency_code
        reverse_symbol = ico_base_currency_code + currency_code
        check_reverse = False

        try:
            # "Forward" checking of the rates symbol. If it
            # matches do the normal rate calculation
            if not symbol.startswith('BTC'):
                # Bitcoin is treated as a fiat currency by the exchange
                crypto_rate = Decimal(crypto_rates[symbol]['last'])
                return (1 / crypto_rate) * self.phase.base_rate
        except KeyError:
            check_reverse = True

        if check_reverse:
            try:
                # "Backwards" checking on the rates symbol. If it
                # matches do the inverse rate calculation
                crypto_rate = Decimal(crypto_rates[reverse_symbol]['last'])
                return crypto_rate * self.phase.base_rate
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
            base_rate = Decimal(fiat_rates[ico_base_currency_code]['rate'])
            exchange_rate = Decimal(fiat_rates[currency_code]['rate'])
        except KeyError as exc:
            return self._calculate_crypto_rate()
        else:
            if self.phase.ico.base_currency.code == 'USD':
                # "Forward" checking of the rates symbol since they
                # are USD based. Do the normal rate calculation.
                return (base_rate * exchange_rate) * self.phase.base_rate
            else:
                # Inverse calculation to get the rate with
                # relation to USD.
                return ((1 / base_rate) * exchange_rate) * self.phase.base_rate

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

    def save(self, *args, **kwargs):
        # Delete all previous quotes for the same currency and phase.
        if not self.id:
            Quote.objects.filter(phase=self.phase, 
                deposit_amount=self.deposit_amount,
                deposit_currency=self.deposit_currency,
                purchase=None).delete()

        return super(Quote, self).save(*args, **kwargs)


class PurchaseMessage(DateModel):
    purchase = models.ForeignKey('ico.Purchase', related_name="messages")
    message = models.CharField(max_length=300)
    exception = models.CharField(max_length=300, null=True, blank=True)


class PurchaseManager(models.Manager):

    def initiate_purchase(self, company, data):
        """
        Initiate a purchase in the ICO service.

        Uncaught exceptions will cause retries in the Rehive webhook logic, in
        order to not cause a retry, there is a SilentException whic will still
        return a 200 OK status.
        """

        tx_id = data.get('id')
        status =  data.get('status')
        currency =  data.get('currency')
        metadata =  data.get('metadata')

        # Check if the transaction is already associated to any purchases.
        # This silently fails already initiated/executed transactions.
        try:
            self.get(Q(Q(deposit_tx=tx_id) | Q(token_tx=tx_id)),
                quote__user__company=company)
            logger.exception(
                "Received already initiated transaction: {}".format(tx_id))
            raise SilentException
        except Purchase.DoesNotExist:
            pass

        # Check if there is an enabled ICO and the ICO has at least one phase.
        # Exclude ICO instances that have the same currency code as the received
        # transaction.
        try:
            ico = Ico.objects.exclude(currency__code=currency['code']).get(
                company=company, enabled=True)
            phase = ico.get_phase()
        except (Ico.DoesNotExist, Phase.DoesNotExist):
            raise SilentException

        # Get currency details.
        deposit_currency = Currency.objects.get(
            code__iexact=currency['code'], company=company, 
            enabled=True)

        deposit_cent_amount = Decimal(str(data['amount']))
        deposit_divisibility = Decimal(str(deposit_currency.divisibility))
        deposit_amount = from_cents(deposit_cent_amount, deposit_divisibility)  
 
        # Get or create a user object.
        user, created = User.objects.get_or_create(
            identifier=uuid.UUID(data['user']['identifier']).hex,
            company=company)

        # Check for matching unused quotes, if none exist, create one.
        try:
            date_from = datetime.datetime.now() - datetime.timedelta(minutes=10)
            quote = Quote.objects.filter(
                user=user, 
                deposit_amount=deposit_amount, 
                deposit_currency=deposit_currency,
                purchase=None,
                phase=phase, 
                created__gte=date_from).latest('created')

        except Quote.DoesNotExist:
            # Stop a new quote from being created if the deposit amount is
            # lower than the minimum allowed amount for the deposit currency
            # Silently fail the purchase so that Rehive does not keep retrying
            if deposit_amount < from_cents(1, deposit_divisibility):
                logger.exception(
                    'Deposit amount is below the min amount '
                    'of {currency} {deposit_amount}.'.format(
                        deposit_amount=from_cents(1, deposit_divisibility),
                        currency=deposit_currency
                    ))
                raise SilentException
            else:
                rate = Rate.objects.get(phase=phase, currency=deposit_currency)
                token_amount = Decimal(deposit_amount / rate.rate)
                quote = Quote.objects.create(
                    user=user,
                    phase=phase,
                    deposit_amount=deposit_amount, 
                    deposit_currency=deposit_currency,
                    token_amount=token_amount,
                    rate=rate.rate)

        return self.create_purchase(quote, tx_id, status, metadata)

    def execute_purchase(self, company, data):
        """
        Execute a purchase with a new status (complete/fail) the transaction.

        Uncaught exceptions will cause retries in the Rehive webhook logic, in
        order to not cause a retry, there is a SilentException which will still
        return a 200 OK status.
        """

        tx_id = data.get('id')
        status =  data.get('status')
        currency =  data.get('currency')

        # Check if there is a disabled or enabled ICO for purchase completion.
        # Exclude ICO instances that have the same currency code as the received
        # transaction.
        try:
            ico = Ico.objects.exclude(currency__code=currency['code']).get(
                company=company)
            phase = ico.get_phase()
        except (Ico.DoesNotExist, Phase.DoesNotExist):
            raise SilentException

        # Try to find an existing purchase with the same deposit_tx as the 
        # transaction received in the webhook.
        try:
            purchase = self.exclude(token_tx__isnull=True).get(
                deposit_tx=tx_id,
                status=PurchaseStatus.PENDING,
                quote__user__company=company)
        except Purchase.DoestNotExist:
            logger.exception(
                "Purchase does not exist for transaction: {}".format(tx_id))
            raise

        return self.update_purchase(purchase, status)

    @transaction.atomic()
    def create_purchase(self, quote, tx_id, status, metadata):
        rehive = Rehive(quote.user.company.admin.token)

        # Create ICO purchase.
        purchase = self.create(quote=quote, deposit_tx=tx_id,
            status=status, metadata=metadata)

        # Get token amount in cents for Rehive.
        token_divisibility = Decimal(
            str(quote.phase.ico.currency.divisibility))
        token_cent_amount = to_cents(
            quote.token_amount, token_divisibility)

        # Create asscociated token credit transaction.
        token_tx = rehive.admin.transactions.create_credit(
            user=str(quote.user.identifier),
            amount=token_cent_amount,
            currency=quote.phase.ico.currency.code,
            confirm_on_create=False)

        purchase.token_tx = token_tx['id']
        purchase.save()

        return purchase  

    def update_purchase(self, purchase, status):
        try:
            rehive = Rehive(purchase.quote.user.company.admin.token) 

            with transaction.atomic():
                purchase.lock_ico()

                if status == "Complete":
                    try:
                        # Final verification of purchase.
                        self.verify_purchase(purchase)

                        # Deduct amount.
                        purchase.quote.phase.ico.deduct_amount(
                            purchase.quote.token_amount)

                    except PurchaseException as exc:
                        purchase.log_message(exc)
                        status = "Failed"

                # Update the transaction based on the status.
                purchase.status = status
                purchase.save()

                # Update associated Rehive token transaction.
                rehive.admin.transactions.patch(purchase.token_tx, status)

                return purchase

        except Exception as exc:
            # Log uncaught exceptions before re-raising the exception.
            # Uncught exceptions may include connection errors.
            purchase.log_message(exc)
            raise exc

    def verify_purchase(self, purchase):
        ico = purchase.quote.phase.ico
        user = purchase.quote.user
        token_amount = purchase.quote.token_amount

        total_purchases = Quote.objects.exclude(purchase=None).filter(
            user=user, phase__ico=ico).count()

        if total_purchases >= ico.max_purchases: 
            raise PurchaseException(
                "Reached max purchases allowed.")

        if (ico.max_purchase_amount > 0
                and token_amount > ico.max_purchase_amount):
            raise PurchaseException(
                "Exceeds the max purchase amount.")

        if (ico.min_purchase_amount > 0
                and token_amount < ico.min_purchase_amount):
            raise PurchaseException(
                "Below the min purchase amount.")


class Purchase(DateModel):
    quote = models.ForeignKey('ico.Quote')
    deposit_tx = models.CharField(unique=True, max_length=200, null=True)
    token_tx = models.CharField(unique=True, max_length=200, null=True)
    metadata = JSONField(null=True, blank=True, default=dict)
    status = EnumField(PurchaseStatus, max_length=50)

    objects = PurchaseManager()

    def lock_ico(self):
        """
        Locks a transaction's ICO for concurrent balance changes.

        This should always be called first before any balance modifying methods
        are invoked.
        """

        self.quote.phase.ico = Ico.objects.\
            select_for_update().get(id=self.quote.phase.ico.id)

    def log_message(self, msg):
        """
        Utility method to log a message for a specific transaction. Only an
        exception/string is required.
        """

        # Truncate message and convert to string (300 chars in total).
        string_msg = (msg[:297] + '...') if len(str(msg)) > 300 else str(msg)

        message = {}
        message['purchase'] = self
        message['message'] = string_msg

        if isinstance(msg, PurchaseException):
            message['exception'] = string_msg

        elif not isinstance(msg, str):
            message['message'] = "A server error occurred."
            message['exception'] = string_msg

        PurchaseMessage.objects.create(**message)