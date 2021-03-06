# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2017-09-07 10:41
from __future__ import unicode_literals

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import ico.models


class Migration(migrations.Migration):

    dependencies = [
        ('ico', '0008_purchasemessage'),
    ]

    operations = [
        migrations.AddField(
            model_name='ico',
            name='max_purchase_amount',
            field=ico.models.MoneyField(decimal_places=18, max_digits=28, null=True),
        ),
        migrations.AddField(
            model_name='ico',
            name='max_purchases',
            field=models.IntegerField(default=10),
        ),
        migrations.AddField(
            model_name='ico',
            name='min_purchase_amount',
            field=ico.models.MoneyField(decimal_places=18, max_digits=28, null=True),
        ),
        migrations.AddField(
            model_name='purchase',
            name='metadata',
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True, default=dict, null=True),
        ),
    ]
