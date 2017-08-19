from django.core.management.base import BaseCommand
from ico.models import Phase, Rate


class Command(BaseCommand):
    """
    Loop through all phases and find all the currencies for those phases.
    Then get or create a new Rate object and calculate the rate for that
    rate object.
    """

    help = "Get exchange rates and calculate ICO Rates"

    def handle(self, *args, **kwargs):

        for phase in Phase.objects.all():
            for currency in phase.ico.company.currency_set.all():
                rate, _ = Rate.objects\
                    .get_or_create(phase=phase, currency=currency)
                rate.set_rate()
