from django.db import models


class Route(models.Model):
    line = models.CharField(max_length=5, unique=True)

    class Meta:
        ordering = [
            'line',
        ]

    def __str__(self):
        return 'Route {}'.format(
            self.line,
        )

