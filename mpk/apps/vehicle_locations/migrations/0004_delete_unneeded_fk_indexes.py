# Generated by Django 2.2.6 on 2020-04-27 07:13

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('vehicle_locations', '0003_delete_invalid_coordinates'),
    ]

    operations = [
        migrations.AlterField(
            model_name='vehiclelocation',
            name='current_stop',
            field=models.ForeignKey(blank=True, db_index=False, null=True, on_delete=django.db.models.deletion.CASCADE, to='stops.Stop'),
        ),
        migrations.AlterField(
            model_name='vehiclelocation',
            name='route',
            field=models.ForeignKey(db_index=False, on_delete=django.db.models.deletion.CASCADE, to='routes.Route'),
        ),
    ]
