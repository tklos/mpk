from django.db import models

from routes.models import Route


class Stop(models.Model):
    route = models.ForeignKey(Route, on_delete=models.CASCADE)
    route_index = models.IntegerField()
    name = models.CharField(max_length=50)
    latitude = models.FloatField()
    longitude = models.FloatField()
    radius_m = models.IntegerField()

    class Meta:
        unique_together = [
            ['route', 'route_index'],
        ]
        ordering = [
            'route',
            'route_index',
        ]

    def __str__(self):
        return 'Stop {:>2} {:02d}: {}: {:.6f} {:.6f} {}'.format(
            self.route.line,
            self.route_index,
            self.name,
            self.latitude,
            self.longitude,
            self.radius_m,
        )

