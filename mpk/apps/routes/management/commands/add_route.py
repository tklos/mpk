import csv
import math
import warnings
import xml.etree.ElementTree as ET
from collections import Counter

from django.conf import settings
from django.core.management import BaseCommand
from django.db import transaction
from django.db.models import Max
from django.db.models.functions import Coalesce

from lib import distance, warn
from routes.models import Route
from stops.models import Stop


DATA_DIR = f'{settings.BASE_DIR}/resources'


warnings.formatwarning = warn.format_warning


def reset_auto_increment():
    import os
    from io import StringIO
    from django.core.management import call_command
    from django.db import connection

    os.environ['DJANGO_COLORS'] = 'nocolor'

    commands = StringIO()
    cursor = connection.cursor()
    call_command('sqlsequencereset', 'stops', stdout=commands)

    cursor.execute(commands.getvalue())


def read_stops_file(filename):
    """ Returns a dict of stop_code: (lat, long) """
    stops_data = {}

    with open(filename) as f:
        reader = csv.DictReader(f)
        for stop in reader:
            stops_data[stop['stop_code']] = tuple(map(float, (stop['stop_lat'], stop['stop_lon'])))

    return stops_data


def read_route_file(filename):
    """ Returns a list stops
    Each stop is a dict {'name': name, 'codes': [stop_code1, stop_code2]}
    """
    route_data = {}

    root = ET.parse(filename).getroot()
    route_versions = list(root.iter('wariant'))
    if len(route_versions) != 2:
        raise ValueError(f'There have to be exactly two route versions; got {len(route_versions)}')

    stops = [route_versions[dir_].find('przystanek').find('czasy').findall('przystanek') for dir_ in (0, 1)]
    stops[1] = list(reversed(stops[1]))

    direction_names = ['outward', 'return']
    stop_names = [[stop.get('nazwa').strip() for stop in stops[dir_]] for dir_ in (0, 1)]

    # Check if stop names are unique within each direction
    for dir_ in 0, 1:
        counter = Counter(stop_names[dir_])
        most_common = counter.most_common(1)[0]
        if most_common[1] > 1:
            raise ValueError('Stop "{}" in the {} route appears more than once'.format(most_common[0], direction_names[dir_]))

    # Check if stops are in the correct order
    for stop1, stop2 in zip(*stop_names):
        if stop1 != stop2:
            raise ValueError(f'Stops not in reverse order; expected "{stop1}" in the return route, got "{stop2}"')

    if len(stop_names[0]) < len(stop_names[1]):
        raise ValueError('Unknown stop "{}" in the return route'.format(stop_names[1][len(stop_names[0])]))
    elif len(stop_names[0]) > len(stop_names[1]):
        raise ValueError('Stop "{}" doesn\'t exist in the return route'.format(stop_names[0][len(stop_names[1])]))


    # Direction 1 -- outward
    for stop_ind, stop_tag in enumerate(stops[0]):
        route_data[stop_tag.get('nazwa')] = {
            'index': stop_ind,
            'codes': [stop_tag.get('id')],
        }

    # Direction 2 -- inward
    for stop_tag in stops[1]:
        route_data[stop_tag.get('nazwa')]['codes'].append(stop_tag.get('id'))

    # Create route data
    route_l = [{'name': name, 'codes': data['codes']} for name, data in sorted(route_data.items(), key=lambda item: item[1]['index'])]

    return route_l


def create_route_stops_data(route_data, stops_data):
    """ Returns a list of stops
    Each stops is a dict {'name': name, 'location': center-location, 'radius': radius'}
    """
    ret_data = []
    for route_stop in route_data:
        s1, s2 = stops_data[route_stop['codes'][0]], stops_data[route_stop['codes'][1]]
        center = ((s1[0] + s2[0]) / 2, (s1[1] + s2[1]) / 2)

        rec = {
            'name': route_stop['name'],
            'location': center,
            'radius': distance.distance(center, s1),
        }
        ret_data.append(rec)

    return ret_data


def check_if_any_stops_overlap(route):
    stops = list(route.stop_set.all().order_by('route_index'))

    for ind1 in range(len(stops)):
        for ind2 in range(ind1+1, len(stops)):
            stop1, stop2 = stops[ind1], stops[ind2]

            stops_dist = distance.distance(stop1, stop2)
            stops_combined_range = stop1.radius_m + stop2.radius_m + 2 * settings.STOP_ADD_RADIUS_M
            if stops_dist <= stops_combined_range:
                warnings.warn('Stops ({}) and ({}) overlap by {:.2f}m'.format(
                    stop1, stop2,
                    stops_combined_range - stops_dist,
                ))


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('line_no')
        parser.add_argument('-r', '--route-id', dest='route_id', type=int, help='Route id')
        parser.add_argument('-n', '--dont-set-route-id', dest='no_route_id', action='store_true', help='Don\'t set route id')

    def handle(self, *args, **kwargs):
        # Parse arguments
        line_no = kwargs['line_no']
        route_id = kwargs['route_id']
        no_route_id = kwargs['no_route_id']

        if no_route_id and route_id is not None:
            raise ValueError('Options -r and -n can\'t be set at the same time')

        # Get route id
        if no_route_id:
            reset_auto_increment()
        else:
            if route_id is None:
                try:
                    route_id = int(line_no)
                except ValueError:
                    max_route_id = Route.objects.aggregate(max_val=Coalesce(Max('id'), 0))['max_val']
                    route_id = max(max_route_id, settings.NOT_INT_ROUTE_MIN_ID) + 1

        # Files
        stops_file = f'{DATA_DIR}/stops.csv'
        route_file = f'{DATA_DIR}/routes/{line_no:>04}.xml'

        # Read files
        stops_data = read_stops_file(stops_file)
        route_data = read_route_file(route_file)

        # Create route stops data
        route_stops_data = create_route_stops_data(route_data, stops_data)

        # Save data
        with transaction.atomic():
            route = Route.objects.create(
                id=None if no_route_id else route_id,
                line=line_no,
            )
            print(f'Added route {route}')

            for ind, stop in enumerate(route_stops_data):
                stop = Stop.objects.create(
                    id=None if no_route_id else route_id * settings.ROUTE_STOPS_STEP + ind,
                    route=route,
                    route_index=ind,
                    name=stop['name'],
                    display_name=stop['name'],
                    latitude=round(stop['location'][0], 6),
                    longitude=round(stop['location'][1], 6),
                    radius_m=math.ceil(stop['radius']),
                )
                print(f'Added stop {stop}')

        # Check if any two stops overlap
        check_if_any_stops_overlap(route)

