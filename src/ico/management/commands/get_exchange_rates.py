from requests import request
from django.core.management.base import BaseCommand, CommandError
from django.core.cache import cache, InvalidCacheBackendError
from ico.models import Rate, Phase, Currency, Ico


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
    rates = cache.get(FIAT_RATES_CACHE_KEY)
    if not rates:
        rates = request('GET', FIAT_RATES).json()
        cache.set(FIAT_RATES_CACHE_KEY, rates, 600)
    return rates


def get_crypto_rates():
    rates = cache.get(CRYPTO_RATES_CACHE_KEY)
    if not rates:
        rates = request('GET', CRYPTO_RATES).json()
        cache.set(CRYPTO_RATES_CACHE_KEY, rates, 600)
    return rates


class Command(BaseCommand):
    """
    Query the current exchange rates and update the Rates objects for
    the relevant ICOs.

    Currently running on the free plan https://bitcoinaverage.com/en/plans

    Exchange used: https://apiv2.bitcoinaverage.com/
    Exchange limit: 5000 requests per month
    """
    help = "Get exchange rates and update ICO Rates"

    def handle(self, *args, **kwargs):
        crypto_rates = get_crypto_rates()
        fiat_rates = get_fiat_rates()

        import pdb; pdb.set_trace()

        for ico in Ico.objects.all():
            for phase in ico.phase_set.all():
                for currency in ico.company.currency_set.all():
                    rate = Rate.objects.get_or_create(phase=phase, currency=currency)
                    if currency == ico.currency:
                        rate.rate = 1
                    elif currency == ico.fiat_currency:
                        rate.rate = phase.fiat_rate
                    else:
                        if currency.code in fiat_rates['rates'].keys():
                            rate = fiat_rates['rates'][currency.code]
                            if ico.currency.code == 'USD':
                                rate.rate = rate * phase.fiat_rate
                            else:
                                rate.rate = (1 / rate) * phase.fiat_rate
                        elif currency.code in crypto_rates['rates'].keys():
                            # TODO: Calculate crypto fee
                            # crypto in terms of USD



# supported_symbols = [
#     "BCHAED", "BCHAFN", "BCHALL", "BCHAMD", "BCHANG", "BCHAOA", "BCHARS",
#     "BCHAUD", "BCHAWG", "BCHAZN", "BCHBAM", "BCHBBD", "BCHBDT", "BCHBGN",
#     "BCHBHD", "BCHBIF", "BCHBMD", "BCHBND", "BCHBOB", "BCHBRL", "BCHBSD",
#     "BCHBTC", "BCHBTN", "BCHBWP", "BCHBYN", "BCHBZD", "BCHCAD", "BCHCDF",
#     "BCHCHF", "BCHCLF", "BCHCLP", "BCHCNH", "BCHCNY", "BCHCOP", "BCHCRC",
#     "BCHCUC", "BCHCUP", "BCHCVE", "BCHCZK", "BCHDJF", "BCHDKK", "BCHDOP",
#     "BCHDZD", "BCHEGP", "BCHERN", "BCHETB", "BCHEUR", "BCHFJD", "BCHFKP",
#     "BCHGBP", "BCHGEL", "BCHGGP", "BCHGHS", "BCHGIP", "BCHGMD", "BCHGNF",
#     "BCHGTQ", "BCHGYD", "BCHHKD", "BCHHNL", "BCHHRK", "BCHHTG", "BCHHUF",
#     "BCHIDR", "BCHILS", "BCHIMP", "BCHINR", "BCHIQD", "BCHIRR", "BCHISK",
#     "BCHJEP", "BCHJMD", "BCHJOD", "BCHJPY", "BCHKES", "BCHKGS", "BCHKHR",
#     "BCHKMF", "BCHKPW", "BCHKRW", "BCHKWD", "BCHKYD", "BCHKZT", "BCHLAK",
#     "BCHLBP", "BCHLKR", "BCHLRD", "BCHLSL", "BCHLYD", "BCHMAD", "BCHMDL",
#     "BCHMGA", "BCHMKD", "BCHMMK", "BCHMNT", "BCHMOP", "BCHMRO", "BCHMUR",
#     "BCHMVR", "BCHMWK", "BCHMXN", "BCHMYR", "BCHMZN", "BCHNAD", "BCHNGN",
#     "BCHNIO", "BCHNOK", "BCHNPR", "BCHNZD", "BCHOMR", "BCHPAB", "BCHPEN",
#     "BCHPGK", "BCHPHP", "BCHPKR", "BCHPLN", "BCHPYG", "BCHQAR", "BCHRON",
#     "BCHRSD", "BCHRUB", "BCHRWF", "BCHSAR", "BCHSBD", "BCHSCR", "BCHSDG",
#     "BCHSEK", "BCHSGD", "BCHSHP", "BCHSLL", "BCHSOS", "BCHSRD", "BCHSSP",
#     "BCHSTD", "BCHSVC", "BCHSYP", "BCHSZL", "BCHTHB", "BCHTJS", "BCHTMT",
#     "BCHTND", "BCHTOP", "BCHTRY", "BCHTTD", "BCHTWD", "BCHTZS", "BCHUAH",
#     "BCHUGX", "BCHUSD", "BCHUYU", "BCHUZS", "BCHVEF", "BCHVND", "BCHVUV",
#     "BCHWST", "BCHXAF", "BCHXAG", "BCHXAU", "BCHXCD", "BCHXDR", "BCHXOF",
#     "BCHXPD", "BCHXPF", "BCHXPT", "BCHYER", "BCHZAR", "BCHZMW", "BCHZWL",
#     "BTCAED", "BTCAFN", "BTCALL", "BTCAMD", "BTCANG", "BTCAOA", "BTCARS",
#     "BTCAUD", "BTCAWG", "BTCAZN", "BTCBAM", "BTCBBD", "BTCBDT", "BTCBGN",
#     "BTCBHD", "BTCBIF", "BTCBMD", "BTCBND", "BTCBOB", "BTCBRL", "BTCBSD",
#     "BTCBTC", "BTCBTN", "BTCBWP", "BTCBYN", "BTCBZD", "BTCCAD", "BTCCDF",
#     "BTCCHF", "BTCCLF", "BTCCLP", "BTCCNH", "BTCCNY", "BTCCOP", "BTCCRC",
#     "BTCCUC", "BTCCUP", "BTCCVE", "BTCCZK", "BTCDJF", "BTCDKK", "BTCDOP",
#     "BTCDZD", "BTCEGP", "BTCERN", "BTCETB", "BTCEUR", "BTCFJD", "BTCFKP",
#     "BTCGBP", "BTCGEL", "BTCGGP", "BTCGHS", "BTCGIP", "BTCGMD", "BTCGNF",
#     "BTCGTQ", "BTCGYD", "BTCHKD", "BTCHNL", "BTCHRK", "BTCHTG", "BTCHUF",
#     "BTCIDR", "BTCILS", "BTCIMP", "BTCINR", "BTCIQD", "BTCIRR", "BTCISK",
#     "BTCJEP", "BTCJMD", "BTCJOD", "BTCJPY", "BTCKES", "BTCKGS", "BTCKHR",
#     "BTCKMF", "BTCKPW", "BTCKRW", "BTCKWD", "BTCKYD", "BTCKZT", "BTCLAK",
#     "BTCLBP", "BTCLKR", "BTCLRD", "BTCLSL", "BTCLYD", "BTCMAD", "BTCMDL",
#     "BTCMGA", "BTCMKD", "BTCMMK", "BTCMNT", "BTCMOP", "BTCMRO", "BTCMUR",
#     "BTCMVR", "BTCMWK", "BTCMXN", "BTCMYR", "BTCMZN", "BTCNAD", "BTCNGN",
#     "BTCNIO", "BTCNOK", "BTCNPR", "BTCNZD", "BTCOMR", "BTCPAB", "BTCPEN",
#     "BTCPGK", "BTCPHP", "BTCPKR", "BTCPLN", "BTCPYG", "BTCQAR", "BTCRON",
#     "BTCRSD", "BTCRUB", "BTCRWF", "BTCSAR", "BTCSBD", "BTCSCR", "BTCSDG",
#     "BTCSEK", "BTCSGD", "BTCSHP", "BTCSLL", "BTCSOS", "BTCSRD", "BTCSSP",
#     "BTCSTD", "BTCSVC", "BTCSYP", "BTCSZL", "BTCTHB", "BTCTJS", "BTCTMT",
#     "BTCTND", "BTCTOP", "BTCTRY", "BTCTTD", "BTCTWD", "BTCTZS", "BTCUAH",
#     "BTCUGX", "BTCUSD", "BTCUYU", "BTCUZS", "BTCVEF", "BTCVND", "BTCVUV",
#     "BTCWST", "BTCXAF", "BTCXAG", "BTCXAU", "BTCXCD", "BTCXDR", "BTCXOF",
#     "BTCXPD", "BTCXPF", "BTCXPT", "BTCYER", "BTCZAR", "BTCZMW", "BTCZWL",
#     "ETHAED", "ETHAFN", "ETHALL", "ETHAMD", "ETHANG", "ETHAOA", "ETHARS",
#     "ETHAUD", "ETHAWG", "ETHAZN", "ETHBAM", "ETHBBD", "ETHBDT", "ETHBGN",
#     "ETHBHD", "ETHBIF", "ETHBMD", "ETHBND", "ETHBOB", "ETHBRL", "ETHBSD",
#     "ETHBTC", "ETHBTN", "ETHBWP", "ETHBYN", "ETHBZD", "ETHCAD", "ETHCDF",
#     "ETHCHF", "ETHCLF", "ETHCLP", "ETHCNH", "ETHCNY", "ETHCOP", "ETHCRC",
#     "ETHCUC", "ETHCUP", "ETHCVE", "ETHCZK", "ETHDJF", "ETHDKK", "ETHDOP",
#     "ETHDZD", "ETHEGP", "ETHERN", "ETHETB", "ETHEUR", "ETHFJD", "ETHFKP",
#     "ETHGBP", "ETHGEL", "ETHGGP", "ETHGHS", "ETHGIP", "ETHGMD", "ETHGNF",
#     "ETHGTQ", "ETHGYD", "ETHHKD", "ETHHNL", "ETHHRK", "ETHHTG", "ETHHUF",
#     "ETHIDR", "ETHILS", "ETHIMP", "ETHINR", "ETHIQD", "ETHIRR", "ETHISK",
#     "ETHJEP", "ETHJMD", "ETHJOD", "ETHJPY", "ETHKES", "ETHKGS", "ETHKHR",
#     "ETHKMF", "ETHKPW", "ETHKRW", "ETHKWD", "ETHKYD", "ETHKZT", "ETHLAK",
#     "ETHLBP", "ETHLKR", "ETHLRD", "ETHLSL", "ETHLYD", "ETHMAD", "ETHMDL",
#     "ETHMGA", "ETHMKD", "ETHMMK", "ETHMNT", "ETHMOP", "ETHMRO", "ETHMUR",
#     "ETHMVR", "ETHMWK", "ETHMXN", "ETHMYR", "ETHMZN", "ETHNAD", "ETHNGN",
#     "ETHNIO", "ETHNOK", "ETHNPR", "ETHNZD", "ETHOMR", "ETHPAB", "ETHPEN",
#     "ETHPGK", "ETHPHP", "ETHPKR", "ETHPLN", "ETHPYG", "ETHQAR", "ETHRON",
#     "ETHRSD", "ETHRUB", "ETHRWF", "ETHSAR", "ETHSBD", "ETHSCR", "ETHSDG",
#     "ETHSEK", "ETHSGD", "ETHSHP", "ETHSLL", "ETHSOS", "ETHSRD", "ETHSSP",
#     "ETHSTD", "ETHSVC", "ETHSYP", "ETHSZL", "ETHTHB", "ETHTJS", "ETHTMT",
#     "ETHTND", "ETHTOP", "ETHTRY", "ETHTTD", "ETHTWD", "ETHTZS", "ETHUAH",
#     "ETHUGX", "ETHUSD", "ETHUYU", "ETHUZS", "ETHVEF", "ETHVND", "ETHVUV",
#     "ETHWST", "ETHXAF", "ETHXAG", "ETHXAU", "ETHXCD", "ETHXDR", "ETHXOF",
#     "ETHXPD", "ETHXPF", "ETHXPT", "ETHYER", "ETHZAR", "ETHZMW", "ETHZWL",
#     "LTCAED", "LTCAFN", "LTCALL", "LTCAMD", "LTCANG", "LTCAOA", "LTCARS",
#     "LTCAUD", "LTCAWG", "LTCAZN", "LTCBAM", "LTCBBD", "LTCBDT", "LTCBGN",
#     "LTCBHD", "LTCBIF", "LTCBMD", "LTCBND", "LTCBOB", "LTCBRL", "LTCBSD",
#     "LTCBTC", "LTCBTN", "LTCBWP", "LTCBYN", "LTCBZD", "LTCCAD", "LTCCDF",
#     "LTCCHF", "LTCCLF", "LTCCLP", "LTCCNH", "LTCCNY", "LTCCOP", "LTCCRC",
#     "LTCCUC", "LTCCUP", "LTCCVE", "LTCCZK", "LTCDJF", "LTCDKK", "LTCDOP",
#     "LTCDZD", "LTCEGP", "LTCERN", "LTCETB", "LTCEUR", "LTCFJD", "LTCFKP",
#     "LTCGBP", "LTCGEL", "LTCGGP", "LTCGHS", "LTCGIP", "LTCGMD", "LTCGNF",
#     "LTCGTQ", "LTCGYD", "LTCHKD", "LTCHNL", "LTCHRK", "LTCHTG", "LTCHUF",
#     "LTCIDR", "LTCILS", "LTCIMP", "LTCINR", "LTCIQD", "LTCIRR", "LTCISK",
#     "LTCJEP", "LTCJMD", "LTCJOD", "LTCJPY", "LTCKES", "LTCKGS", "LTCKHR",
#     "LTCKMF", "LTCKPW", "LTCKRW", "LTCKWD", "LTCKYD", "LTCKZT", "LTCLAK",
#     "LTCLBP", "LTCLKR", "LTCLRD", "LTCLSL", "LTCLYD", "LTCMAD", "LTCMDL",
#     "LTCMGA", "LTCMKD", "LTCMMK", "LTCMNT", "LTCMOP", "LTCMRO", "LTCMUR",
#     "LTCMVR", "LTCMWK", "LTCMXN", "LTCMYR", "LTCMZN", "LTCNAD", "LTCNGN",
#     "LTCNIO", "LTCNOK", "LTCNPR", "LTCNZD", "LTCOMR", "LTCPAB", "LTCPEN",
#     "LTCPGK", "LTCPHP", "LTCPKR", "LTCPLN", "LTCPYG", "LTCQAR", "LTCRON",
#     "LTCRSD", "LTCRUB", "LTCRWF", "LTCSAR", "LTCSBD", "LTCSCR", "LTCSDG",
#     "LTCSEK", "LTCSGD", "LTCSHP", "LTCSLL", "LTCSOS", "LTCSRD", "LTCSSP",
#     "LTCSTD", "LTCSVC", "LTCSYP", "LTCSZL", "LTCTHB", "LTCTJS", "LTCTMT",
#     "LTCTND", "LTCTOP", "LTCTRY", "LTCTTD", "LTCTWD", "LTCTZS", "LTCUAH",
#     "LTCUGX", "LTCUSD", "LTCUYU", "LTCUZS", "LTCVEF", "LTCVND", "LTCVUV",
#     "LTCWST", "LTCXAF", "LTCXAG", "LTCXAU", "LTCXCD", "LTCXDR", "LTCXOF",
#     "LTCXPD", "LTCXPF", "LTCXPT", "LTCYER", "LTCZAR", "LTCZMW", "LTCZWL",
#     "XRPAED", "XRPAFN", "XRPALL", "XRPAMD", "XRPANG", "XRPAOA", "XRPARS",
#     "XRPAUD", "XRPAWG", "XRPAZN", "XRPBAM", "XRPBBD", "XRPBDT", "XRPBGN",
#     "XRPBHD", "XRPBIF", "XRPBMD", "XRPBND", "XRPBOB", "XRPBRL", "XRPBSD",
#     "XRPBTC", "XRPBTN", "XRPBWP", "XRPBYN", "XRPBZD", "XRPCAD", "XRPCDF",
#     "XRPCHF", "XRPCLF", "XRPCLP", "XRPCNH", "XRPCNY", "XRPCOP", "XRPCRC",
#     "XRPCUC", "XRPCUP", "XRPCVE", "XRPCZK", "XRPDJF", "XRPDKK", "XRPDOP",
#     "XRPDZD", "XRPEGP", "XRPERN", "XRPETB", "XRPEUR", "XRPFJD", "XRPFKP",
#     "XRPGBP", "XRPGEL", "XRPGGP", "XRPGHS", "XRPGIP", "XRPGMD", "XRPGNF",
#     "XRPGTQ", "XRPGYD", "XRPHKD", "XRPHNL", "XRPHRK", "XRPHTG", "XRPHUF",
#     "XRPIDR", "XRPILS", "XRPIMP", "XRPINR", "XRPIQD", "XRPIRR", "XRPISK",
#     "XRPJEP", "XRPJMD", "XRPJOD", "XRPJPY", "XRPKES", "XRPKGS", "XRPKHR",
#     "XRPKMF", "XRPKPW", "XRPKRW", "XRPKWD", "XRPKYD", "XRPKZT", "XRPLAK",
#     "XRPLBP", "XRPLKR", "XRPLRD", "XRPLSL", "XRPLYD", "XRPMAD", "XRPMDL",
#     "XRPMGA", "XRPMKD", "XRPMMK", "XRPMNT", "XRPMOP", "XRPMRO", "XRPMUR",
#     "XRPMVR", "XRPMWK", "XRPMXN", "XRPMYR", "XRPMZN", "XRPNAD", "XRPNGN",
#     "XRPNIO", "XRPNOK", "XRPNPR", "XRPNZD", "XRPOMR", "XRPPAB", "XRPPEN",
#     "XRPPGK", "XRPPHP", "XRPPKR", "XRPPLN", "XRPPYG", "XRPQAR", "XRPRON",
#     "XRPRSD", "XRPRUB", "XRPRWF", "XRPSAR", "XRPSBD", "XRPSCR", "XRPSDG",
#     "XRPSEK", "XRPSGD", "XRPSHP", "XRPSLL", "XRPSOS", "XRPSRD", "XRPSSP",
#     "XRPSTD", "XRPSVC", "XRPSYP", "XRPSZL", "XRPTHB", "XRPTJS", "XRPTMT",
#     "XRPTND", "XRPTOP", "XRPTRY", "XRPTTD", "XRPTWD", "XRPTZS", "XRPUAH",
#     "XRPUGX", "XRPUSD", "XRPUYU", "XRPUZS", "XRPVEF", "XRPVND", "XRPVUV",
#     "XRPWST", "XRPXAF", "XRPXAG", "XRPXAU", "XRPXCD", "XRPXDR", "XRPXOF",
#     "XRPXPD", "XRPXPF", "XRPXPT", "XRPYER", "XRPZAR", "XRPZMW", "XRPZWL",
#     "ZECAED", "ZECAFN", "ZECALL", "ZECAMD", "ZECANG", "ZECAOA", "ZECARS",
#     "ZECAUD", "ZECAWG", "ZECAZN", "ZECBAM", "ZECBBD", "ZECBDT", "ZECBGN",
#     "ZECBHD", "ZECBIF", "ZECBMD", "ZECBND", "ZECBOB", "ZECBRL", "ZECBSD",
#     "ZECBTC", "ZECBTN", "ZECBWP", "ZECBYN", "ZECBZD", "ZECCAD", "ZECCDF",
#     "ZECCHF", "ZECCLF", "ZECCLP", "ZECCNH", "ZECCNY", "ZECCOP", "ZECCRC",
#     "ZECCUC", "ZECCUP", "ZECCVE", "ZECCZK", "ZECDJF", "ZECDKK", "ZECDOP",
#     "ZECDZD", "ZECEGP", "ZECERN", "ZECETB", "ZECEUR", "ZECFJD", "ZECFKP",
#     "ZECGBP", "ZECGEL", "ZECGGP", "ZECGHS", "ZECGIP", "ZECGMD", "ZECGNF",
#     "ZECGTQ", "ZECGYD", "ZECHKD", "ZECHNL", "ZECHRK", "ZECHTG", "ZECHUF",
#     "ZECIDR", "ZECILS", "ZECIMP", "ZECINR", "ZECIQD", "ZECIRR", "ZECISK",
#     "ZECJEP", "ZECJMD", "ZECJOD", "ZECJPY", "ZECKES", "ZECKGS", "ZECKHR",
#     "ZECKMF", "ZECKPW", "ZECKRW", "ZECKWD", "ZECKYD", "ZECKZT", "ZECLAK",
#     "ZECLBP", "ZECLKR", "ZECLRD", "ZECLSL", "ZECLYD", "ZECMAD", "ZECMDL",
#     "ZECMGA", "ZECMKD", "ZECMMK", "ZECMNT", "ZECMOP", "ZECMRO", "ZECMUR",
#     "ZECMVR", "ZECMWK", "ZECMXN", "ZECMYR", "ZECMZN", "ZECNAD", "ZECNGN",
#     "ZECNIO", "ZECNOK", "ZECNPR", "ZECNZD", "ZECOMR", "ZECPAB", "ZECPEN",
#     "ZECPGK", "ZECPHP", "ZECPKR", "ZECPLN", "ZECPYG", "ZECQAR", "ZECRON",
#     "ZECRSD", "ZECRUB", "ZECRWF", "ZECSAR", "ZECSBD", "ZECSCR", "ZECSDG",
#     "ZECSEK", "ZECSGD", "ZECSHP", "ZECSLL", "ZECSOS", "ZECSRD", "ZECSSP",
#     "ZECSTD", "ZECSVC", "ZECSYP", "ZECSZL", "ZECTHB", "ZECTJS", "ZECTMT",
#     "ZECTND", "ZECTOP", "ZECTRY", "ZECTTD", "ZECTWD", "ZECTZS", "ZECUAH",
#     "ZECUGX", "ZECUSD", "ZECUYU", "ZECUZS", "ZECVEF", "ZECVND", "ZECVUV",
#     "ZECWST", "ZECXAF", "ZECXAG", "ZECXAU", "ZECXCD", "ZECXDR", "ZECXOF",
#     "ZECXPD", "ZECXPF", "ZECXPT", "ZECYER", "ZECZAR", "ZECZMW", "ZECZWL"
# ]