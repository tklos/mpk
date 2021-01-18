import logging
import re
from datetime import datetime

import numpy as np
import pytz
import requests
import urllib3
from django.conf import settings
from django.core.management import BaseCommand
from django.db import IntegrityError

from lib import distance
from routes.models import Route
from vehicle_locations import const
from vehicle_locations.models import VehicleLocation


LOCATIONS_URL = 'https://mpk.wroc.pl/bus_position'


logger = logging.getLogger('get-locations')


# Suppress SSL warning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def round_or_none(val, num_d):
    return None if val is None else round(val, num_d)


def _is_at_stop(stop, dist):
    return dist <= stop.radius_m + settings.STOP_ADD_RADIUS_M


def calculate_position_between_stops(stop_a, stop_b, dist_a, dist_b):
    std_stops_dist = distance.distance(stop_a, stop_b)
    this_total_dist = dist_a + dist_b

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
    logger.debug(f'Processing {lat}, {lng}')

    loc = (lat, lng)
    route, stops = routes_d[line]

    # Check if location is valid
    # Example of incorrect coordinates: {'name': 'd', 'type': 'bus', 'y': 2634.2861, 'x': 6429.7183, 'k': 14429515}
    if not settings.MIN_LAT <= lat <= settings.MAX_LAT or not settings.MIN_LONG <= lng <= settings.MAX_LONG:
        logger.error(f'Invalid location: {el}')
        return

    # Calculate distance
    stop_dist = [distance.distance(loc, stop) for stop in stops]
    logger.debug(stop_dist)

    # Find location
    is_at_stop_l = [_is_at_stop(stops[ind], stop_dist[ind]) for ind in range(len(stops))]
    num_true = is_at_stop_l.count(True)

    if num_true > 1:
        # Vehicle at multiple stops; choosing nearest stop
        curr_stops_ind_l = [ind for ind, is_at_stop in enumerate(is_at_stop_l) if is_at_stop]
        curr_stops_dist_l = [stop_dist[ind] for ind in curr_stops_ind_l]
        _, nearest_stop_ind = min(zip(curr_stops_dist_l, curr_stops_ind_l))
        nearest_stop = stops[nearest_stop_ind]

        logger.warning('Vehicle at multiple stops: {}   vehicle ({} {} {} {})   stops {}   nearest {}'.format(
            date_created,
            line, vehicle_id, lat, lng,
            [stops[ind] for ind in curr_stops_ind_l],
            nearest_stop,
        ))

        proc_status = {
            'is_processed': True,
            'is_at_stop': True,
            'current_stop': nearest_stop,
        }

    elif num_true == 1:
        # Vehicle at a stop
        current_stop_ind = next((ind for ind in range(len(is_at_stop_l)) if is_at_stop_l[ind]))
        current_stop = stops[current_stop_ind]

        proc_status = {
            'is_processed': True,
            'is_at_stop': True,
            'current_stop': current_stop,
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
    try:
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

    except IntegrityError as exc:
        # Duplicate key
        match = re.search('Key \(route_id, vehicle_id, date\)=.* already exists', str(exc))
        if not match:
            raise

        logger.error('Duplicate key: {}'.format(match.string[match.start():match.end()]))


class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        # Routes
        routes = Route.objects.all()
        lines_l = [r.line for r in routes]
        if not lines_l:
            raise RuntimeError('No routes')
        routes_d = {r.line: (r, list(r.stop_set.all())) for r in routes}

        # Send request
        locations_data = {'busList[][]': lines_l}
        try:
            resp = requests.post(
                LOCATIONS_URL,
                data=locations_data,
                verify=False,
                timeout=settings.GET_LOCATIONS_TIMEOUT_S,
            )
            resp.raise_for_status()

        except requests.exceptions.Timeout:
            logger.error('Request timed out, exiting..')
            return

        except Exception as exc:
            msg = 'Error getting data, exiting..  {}.{}: {}'.format(type(exc).__module__, type(exc).__qualname__, str(exc))
            logger.error(msg)
            return

        # Check if response is empty
        if not len(resp.content):
            logger.error('Response empty, exiting..')
            return

        # Get data
        data = resp.json()
        date_created = datetime.strptime(resp.headers['Date'], '%a, %d %b %Y %H:%M:%S GMT').replace(tzinfo=pytz.utc)

        # There might be duplicate vehicle ids in the data,
        # e.g. {'name': '3', 'type': 'tram', 'y': 16.98013, 'x': 51.12673, 'k': 14339663} and {'name': '3', 'type': 'tram', 'y': 17.03928, 'x': 51.107746, 'k': 14339663}
        # In that case, remove all duplicate records
        # (a) Convert data to a dict of vehicle-id: list-of-locations
        data_d = {}
        for d in data:
            data_d.setdefault(d['k'], []).append(d)
        # (b) Remove duplicates
        for vehicle_id in list(data_d.keys()):
            if len(data_d[vehicle_id]) != 1:
                logger.error(f'Duplicate vehicle id {vehicle_id}: {data_d[vehicle_id]}')
                del data_d[vehicle_id]

        # Save data
        for el in data_d.values():
            process_vehicle(el[0], routes_d, date_created)

