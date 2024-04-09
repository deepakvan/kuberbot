# Generated by Django 5.0.4 on 2024-04-05 09:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('BotManager', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='StaticData',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('volume', models.IntegerField()),
                ('leverage', models.IntegerField()),
                ('static_id', models.IntegerField(default=1)),
                ('created', models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
