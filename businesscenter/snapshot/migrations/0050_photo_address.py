# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2016-09-10 21:10
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('snapshot', '0049_auto_20160906_1910'),
    ]

    operations = [
        migrations.AddField(
            model_name='photo',
            name='address',
            field=models.CharField(blank=True, max_length=300, null=True, verbose_name='Address'),
        ),
    ]
