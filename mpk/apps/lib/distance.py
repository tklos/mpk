import math

from django.conf import settings

from stops.models import Stop


def distance(p1, p2):
    """ Distance in meters between p1 and p2 """
    if isinstance(p1, Stop):
        p1 = (p1.latitude, p1.longitude)
    if isinstance(p2, Stop):
        p2 = (p2.latitude, p2.longitude)

    return math.sqrt(
            math.pow(math.fabs(p2[0] - p1[0]) * settings.ONE_DEG_Y_KM, 2) +
            math.pow(math.fabs(p2[1] - p1[1]) * settings.ONE_DEG_X_KM, 2)
    ) * 1000.

