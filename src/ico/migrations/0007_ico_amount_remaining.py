# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2017-09-04 09:42
from __future__ import unicode_literals

from decimal import Decimal
from django.db import migrations
import ico.models


class Migration(migrations.Migration):

    dependencies = [
        ('ico', '0006_auto_20170825_0930'),
    ]

    operations = [
        migrations.AddField(
            model_name='ico',
            name='amount_remaining',
            field=ico.models.MoneyField(decimal_places=18, default=Decimal('0'), max_digits=28),
        ),
    ]
