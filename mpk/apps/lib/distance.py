import math


# Number of kilometers between current position and the one one degree east/west or north/south
ONE_DEG_X_KM =  69.977  # 2 * PI * EARTH_RADIUS * sin(radians(90-lat)) / 360, (EARTH_RADIUS=6371, lat=51)
ONE_DEG_Y_KM = 111.194  # 2 * PI * EARTH_RADIUS / 360


def distance(p1, p2):
    """ Distance in meters between p1 and p2 """
    return math.sqrt(
            math.pow(math.fabs(p2[0] - p1[0]) * ONE_DEG_Y_KM, 2) +
            math.pow(math.fabs(p2[1] - p1[1]) * ONE_DEG_X_KM, 2)
    ) * 1000.

