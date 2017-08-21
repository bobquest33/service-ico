from django.db.models.signals import post_save, post_init
from django.dispatch import receiver

from ico.models import Phase, Rate


@receiver(post_save, sender=Phase)
def create_rate(sender, instance, created, **kwargs):
    """
    Automatically create Rate objects foor all company currencies when a
    new Phase is successfully created
    """
    if not created:
        return

    for currency in instance.ico.company.currency_set.all():
        rate, _ = Rate.objects.get_or_create(phase=instance, currency=currency)
        rate.refresh_rate()
