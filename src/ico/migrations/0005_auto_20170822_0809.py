# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2017-08-22 08:09
from __future__ import unicode_literals

from decimal import Decimal
from django.db import migrations
import ico.models


class Migration(migrations.Migration):

    dependencies = [
        ('ico', '0004_auto_20170821_1512'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='ico',
            name='number',
        ),
        migrations.AddField(
            model_name='ico',
            name='amount',
            field=ico.models.MoneyField(decimal_places=18, default=Decimal('0'), max_digits=28),
        ),
    ]
