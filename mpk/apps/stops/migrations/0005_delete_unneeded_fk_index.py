# Generated by Django 2.2.6 on 2020-04-27 07:13

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('stops', '0004_complete_display_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='stop',
            name='route',
            field=models.ForeignKey(db_index=False, on_delete=django.db.models.deletion.CASCADE, to='routes.Route'),
        ),
    ]
