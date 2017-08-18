from requests import request
from django.core.cache import cache


# Exchange used: https://apiv2.bitcoinaverage.com/
# Exchange limit: 5000 requests per month
# Currently running on the free plan https://bitcoinaverage.com/en/plans

# API endpoints
# ================
EXCHANGE = 'https://apiv2.bitcoinaverage.com'
SYMBOLS = '{}/constants/symbols/global'.format(EXCHANGE)
# In relation to USD (BTC -> USD = 0.000233958343)
FIAT_RATES = '{}/constants/exchangerates/global'.format(EXCHANGE)
# Currency pair (BTCUSD = 4238.720735048802)
CRYPTO_RATES = '{}/indices/global/ticker/short'.format(EXCHANGE)
CONVERT = '{}/convert/global?from={source_cur}&to={target_cur}'

# Cache keys
# ================
FIAT_RATES_CACHE_KEY = 'ico_service_fiat_rates'
CRYPTO_RATES_CACHE_KEY = 'ico_service_crypto_rates'


def get_fiat_rates():
    """
    Check the cache if the fiat rates have been stored, otherwise
    make a request to the exchange to get updated rates
    """
    rates = cache.get(FIAT_RATES_CACHE_KEY)
    if rates is None:
        rates = request('GET', FIAT_RATES).json().get('rates')
        cache.set(FIAT_RATES_CACHE_KEY, rates, 600)
    return rates


def get_crypto_rates():
    """
    Check the cache if the crypto rates have been stored, otherwise
    make a request to the exchange to get updated rates
    """
    rates = cache.get(CRYPTO_RATES_CACHE_KEY)
    if rates is None:
        rates = request('GET', CRYPTO_RATES).json()
        cache.set(CRYPTO_RATES_CACHE_KEY, rates, 600)
    return rates
