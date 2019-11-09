import logging
from datetime import datetime
import numpy as np
import pytz
import requests
from django.conf import settings
from django.core.management import BaseCommand

from lib import distance
from routes.models import Route
from vehicle_locations import const
from vehicle_locations.models import VehicleLocation


LOCATIONS_URL = 'http://pasazer.mpk.wroc.pl/position.php'


logger = logging.getLogger('get-locations')


def round_or_none(val, num_d):
    return None if val is None else round(val, num_d)


def _is_at_stop(stop, dist):
    return dist <= stop.radius_m + settings.STOP_ADD_RADIUS_M


def calculate_position_between_stops(stop_a, stop_b, dist_a, dist_b):
    std_stops_dist = distance.distance(stop_a, stop_b)
    this_total_dist = dist_a + dist_b
    logger.debug((std_stops_dist, this_total_dist))

    if this_total_dist > std_stops_dist * settings.MAX_ALLOWED_DETOUR_RATIO:
        # We are too far from the planned route
        return {
            'is_processed': False,
            'unprocessed_reason': const.UNPROC_REASON_TOO_FAR,
        }

    else:
        dist_limited = dist_a - stop_a.radius_m - settings.STOP_ADD_RADIUS_M
        total_dist_limited = dist_a + dist_b - stop_a.radius_m - stop_b.radius_m - 2 * settings.STOP_ADD_RADIUS_M
        to_next_stop_ratio = dist_limited / total_dist_limited
        logger.debug(to_next_stop_ratio)

        return {
            'is_processed': True,
            'is_at_stop': False,
            'current_stop': stop_a,
            'to_next_stop_ratio': to_next_stop_ratio,
        }


def process_vehicle(el, routes_d, date_created):
    """ Calculates position of element el and saves in the db """
    line, vehicle_id = el['name'], el['k']
    lat, lng = el['x'], el['y']
    logger.debug('Processing {}, {}'.format(lat, lng))

    loc = (lat, lng)
    route, stops = routes_d[line]

    # Calculate distance
    stop_dist = [distance.distance(loc, stop) for stop in stops]
    logger.debug(stop_dist)

    # Find location
    is_at_stop_l = [_is_at_stop(stops[ind], stop_dist[ind]) for ind in range(len(stops))]
    num_true = is_at_stop_l.count(True)

    if num_true > 1:
        # Vehicle at multiple stops
        proc_status = {
            'is_processed': False,
            'unprocessed_reason': const.UNPROC_REASON_MULTIPLE_STOPS,
        }

    elif num_true == 1:
        # Vehicle at a stop
        current_stop_ind = next((ind for ind in range(len(is_at_stop_l)) if is_at_stop_l[ind]))
        current_stop = stops[current_stop_ind]
        logger.debug('at stop {} ({:.2f})'.format(current_stop, stop_dist[current_stop_ind]))
        proc_status = {
            'is_processed': True,
            'is_at_stop': True,
            'current_stop': stops[current_stop_ind],
        }

    else:
        # Not at stop
        min_ind = np.argmin(stop_dist)
        stop1 = stops[min_ind]

        if min_ind == 0 or min_ind == len(stops) - 1:
            # We are between final and next to final stop or beyond final stop
            if min_ind == 0:
                ind_final, ind_other = 0, 1
            else:
                ind_final, ind_other = len(stops) - 1, len(stops) - 2

            ind_a, ind_b = min(ind_final, ind_other), max(ind_final, ind_other)
            dist_loc_next, dist_stop_next = distance.distance(loc, stops[ind_other]), distance.distance(stops[ind_final], stops[ind_other])
            if dist_stop_next < dist_loc_next:
                logger.debug('Beyond')
                proc_status = {
                    'is_processed': False,
                    'unprocessed_reason': const.UNPROC_REASON_BEYOND_FINAL_STOP,
                }

            else:
                proc_status = calculate_position_between_stops(stops[ind_a], stops[ind_b], stop_dist[ind_a], stop_dist[ind_b])

        else:
            # We are between stops (stop_a=min_ind-1 and min_ind) or (min_ind and stop_b=min_ind+1)
            stop_a, stop_b = stops[min_ind-1], stops[min_ind+1]

            dist_stop_a, dist_stop_b = distance.distance(stop1, stop_a), distance.distance(stop1, stop_b)
            dist_loc_a, dist_loc_b = distance.distance(loc, stop_a), distance.distance(loc, stop_b)

            diff_a, diff_b = dist_loc_a - dist_stop_a, dist_loc_b - dist_stop_b
            logger.debug('DIST ({:.0f} {:.0f} {:.0f}) ({:.0f} {:.0f} {:.0f})'.format(dist_loc_a, dist_stop_a, diff_a, dist_loc_b, dist_stop_b, diff_b))
            if diff_a < diff_b:
                # We are closer to stop a
                min_ind -= 1

            proc_status = calculate_position_between_stops(stops[min_ind], stops[min_ind+1], stop_dist[min_ind], stop_dist[min_ind+1])

    logger.debug(proc_status)
    # Save
    loc = VehicleLocation.objects.create(
        route=route,
        vehicle_id=vehicle_id,
        date=date_created,
        latitude=lat,
        longitude=lng,
        is_processed=proc_status['is_processed'],
        unprocessed_reason=proc_status.get('unprocessed_reason'),
        is_at_stop=proc_status.get('is_at_stop'),
        current_stop=proc_status.get('current_stop'),
        to_next_stop_ratio=round_or_none(proc_status.get('to_next_stop_ratio'), 3),
    )
    logger.debug(loc)
    logger.debug('')


class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        # Routes
        routes = Route.objects.all()
        lines_l = [r.line for r in routes]
        if not lines_l:
            raise RuntimeError('No routes')
        routes_d = {r.line: (r, list(r.stop_set.all())) for r in routes}

        # Get data
        locations_data = {'busList[][]': lines_l}
        resp = requests.post(LOCATIONS_URL, data=locations_data)
        resp.raise_for_status()

        date_created = datetime.strptime(resp.headers['Date'], '%a, %d %b %Y %H:%M:%S GMT').replace(tzinfo=pytz.utc)

        # Save data
        for el in resp.json():
            process_vehicle(el,routes_d, date_created)

