# -*- coding: utf-8 -*-
# Generated by Django 1.10 on 2016-09-05 08:55
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('commerce', '0010_auto_20160905_0445'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='item',
            options={'ordering': ['date_added']},
        ),
    ]
