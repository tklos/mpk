from django.db import models

from routes.models import Route
from stops.models import Stop
from . import const


class VehicleLocation(models.Model):
    route = models.ForeignKey(Route, on_delete=models.CASCADE, db_index=False)
    vehicle_id = models.IntegerField()
    date = models.DateTimeField()
    date_added = models.DateTimeField(auto_now_add=True)
    latitude = models.FloatField()
    longitude = models.FloatField()
    is_processed = models.BooleanField()
    unprocessed_reason = models.SmallIntegerField(choices=const.UNPROC_REASON_CHOICES, null=True, blank=True)
    is_at_stop = models.BooleanField(null=True, blank=True)
    current_stop = models.ForeignKey(Stop, on_delete=models.CASCADE, null=True, blank=True, db_index=False)
    to_next_stop_ratio = models.FloatField(null=True, blank=True)

    class Meta:
        unique_together = [
            ['route', 'vehicle_id', 'date'],
        ]
        indexes = [
            models.Index(fields=['route', 'date']),
        ]
        ordering = [
            'route',
            'vehicle_id',
            'date',
        ]

    def __str__(self):
        ret = 'VehicleLocation {:>2} {} {}: {:.6f} {:.6f} {}: '.format(
            self.route.line,
            self.vehicle_id,
            self.date,
            self.latitude,
            self.longitude,
            self.is_processed,
        )
        if self.is_processed:
            if self.is_at_stop:
                ret += 'at-stop {}'.format(self.current_stop.name)
            else:
                ret += 'between-stops {} {:.3f}'.format(self.current_stop.name, self.to_next_stop_ratio)
        else:
            ret += self.get_unprocessed_reason_display()

        return ret


