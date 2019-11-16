import csv
import math
import xml.etree.ElementTree as ET

from django.conf import settings
from django.core.management import BaseCommand
from django.db import transaction

from lib import distance
from routes.models import Route
from stops.models import Stop


DATA_DIR = '{}/resources'.format(settings.BASE_DIR)


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
        raise ValueError('There have to be exactly two route versions; got {}'.format(len(route_versions)))

    # Direction 1 -- outward
    for stop_ind, stop_tag in enumerate(route_versions[0].find('przystanek').find('czasy').findall('przystanek')):
        route_data[stop_tag.get('nazwa')] = {
            'index': stop_ind,
            'codes': [stop_tag.get('id')],
        }

    # Direction 2 -- inward
    for stop_tag in route_versions[1].find('przystanek').find('czasy').findall('przystanek'):
        try:
            route_data[stop_tag.get('nazwa')]['codes'].append(stop_tag.get('id'))
        except KeyError as exc:
            raise KeyError('Unknown stop "{}" in the return route'.format(stop_tag.get('nazwa'))) from exc

    route_data_l = len(route_data) * [None]
    for k, v in route_data.items():
        ind = v.pop('index')
        v['name'] = k
        route_data_l[ind] = v

    return route_data_l


def create_route_stops_data(route_data, stops_data):
    ret_data = []
    for route_stop in route_data:
        rec = {'name': route_stop['name']}
        if len(route_stop['codes']) != 2:
            raise ValueError('Unknown stop "{}" in the inward route'.format(route_stop['name']))

        s1, s2 = stops_data[route_stop['codes'][0]], stops_data[route_stop['codes'][1]]
        center = ((s1[0] + s2[0]) / 2, (s1[1] + s2[1]) / 2)

        rec['location'] = center
        rec['radius'] = distance.distance(center, s1)

        ret_data.append(rec)

    return ret_data


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('line_no')

    def handle(self, *args, **kwargs):
        line_no = kwargs['line_no']

        # Files
        stops_file = '{}/stops.csv'.format(DATA_DIR)
        route_file = '{}/routes/{:>04}.xml'.format(DATA_DIR, line_no)

        # Read files
        stops_data = read_stops_file(stops_file)
        route_data = read_route_file(route_file)

        # Create route stops data
        route_stops_data = create_route_stops_data(route_data, stops_data)

        # Save data
        with transaction.atomic():
            route = Route.objects.create(
                line=line_no,
            )
            print('Added route {}'.format(route))

            for ind, stop in enumerate(route_stops_data):
                stop = Stop.objects.create(
                    route=route,
                    route_index=ind,
                    name=stop['name'],
                    display_name=stop['name'],
                    latitude=round(stop['location'][0], 6),
                    longitude=round(stop['location'][1], 6),
                    radius_m=math.ceil(stop['radius']),
                )
                print('Added stop {}'.format(stop))

