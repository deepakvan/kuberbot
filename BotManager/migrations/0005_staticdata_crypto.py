# Generated by Django 5.0.4 on 2024-04-06 05:30

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('BotManager', '0004_botsignals_coinpair_botsignals_side'),
    ]

    operations = [
        migrations.AddField(
            model_name='staticdata',
            name='crypto',
            field=models.CharField(default=django.utils.timezone.now, max_length=100),
            preserve_default=False,
        ),
    ]