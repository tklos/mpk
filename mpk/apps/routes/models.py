from django.db import models


class Route(models.Model):
    line = models.CharField(max_length=5, unique=True)

    def __str__(self):
        return 'Route {}'.format(
            self.line,
        )

