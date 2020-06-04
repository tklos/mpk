"""
Dumps records older than keep-days to a file and deletes these records from the database.
The data are dumped to daily files. The file for date d contains records from [d, d+1day) in *local* timezone.
"""
import gzip
import os
from datetime import datetime, timedelta

import pytz
from django.conf import settings
from django.core.management import BaseCommand
from django.db import connection

from vehicle_locations.models import VehicleLocation

LOCATION_TABLE = VehicleLocation._meta.db_table


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('-d', '--keep-days', dest='keep_days', type=int, help='Number of days of data to keep', required=True)
        parser.add_argument('-o', '--out-dir', dest='out_dir', help='Out dir', required=True)

    def handle(self, *args, **kwargs):
        # Parse arguments
        keep_days = kwargs['keep_days']
        out_dir = kwargs['out_dir']

        if keep_days <= 0:
            raise ValueError('keep-days must be positive')

        # Current and oldest date to keep
        current_date = datetime.now().date()
        last_date = current_date - timedelta(days=keep_days)

        # Earliest record
        earliest_record = (
            VehicleLocation
            .objects
            .order_by('date')
            .first()
        )
        if earliest_record is None:
            return

        this_date = earliest_record.date.astimezone(settings.LOCAL_TIMEZONE).date()
        while this_date < last_date:
            next_date = this_date + timedelta(days=1)
            next_date_dt = settings.LOCAL_TIMEZONE.localize(datetime.combine(next_date, datetime.min.time()))
            next_date_utc_dt = next_date_dt.astimezone(pytz.utc)

            # Archive records
            query = 'copy (select * from {} where date < \'{}\' order by date) to stdout'.format(LOCATION_TABLE, next_date_utc_dt.strftime('%Y-%m-%d %H:%M+00:00'))
            out_filename = '{}/loc-{}.dump.gz'.format(out_dir, this_date.strftime('%Y%m%d'))

            cursor = connection.cursor()
            cursor.copy_expert(query, gzip.open(out_filename, 'w'))

            # Make sure that the file has been created
            if not os.path.isfile(out_filename):
                raise RuntimeError(f'Dump for {this_date} failed; {out_filename} hasn\'t been created')

            # Delete records
            VehicleLocation.objects.filter(date__lt=next_date_dt).order_by().delete()

            this_date = next_date

