# -*- coding: utf-8 -*-
# Generated by Django 1.10 on 2016-08-31 07:28
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('commerce', '0002_auto_20160831_0312'),
    ]

    operations = [
        migrations.AlterField(
            model_name='icon',
            name='static_id',
            field=models.CharField(default='unknown.png', max_length=36),
        ),
    ]
