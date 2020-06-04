from django.conf import settings
from django.forms import model_to_dict
from django.test import TestCase

from routes.models import Route
from stops.models import Stop
from vehicle_locations import const
from vehicle_locations.management.commands.get_locations import process_vehicle
from vehicle_locations.models import VehicleLocation


class ProcessVehicleTests(TestCase):
    START_STOPS_LOC = (51., 17.)
    STOPS_DIST = [0, 100, 50, 100, 50]  # Distance from the first stop
    STOPS_RADIUS = [10, 30, 30, 5, 20]

    def setUp(self):
        route = Route.objects.create(line='L. 1')

        num_stops = len(self.STOPS_DIST)
        prev_longitude = self.START_STOPS_LOC[1]
        for ind in range(num_stops):
            name = f'Stop {ind}'
            longitude = prev_longitude + self.STOPS_DIST[ind] / settings.ONE_DEG_X_KM / 1000.

            Stop.objects.create(
                route=route,
                route_index=ind,
                name=name,
                display_name=name,
                latitude=self.START_STOPS_LOC[0],
                longitude=longitude,
                radius_m=self.STOPS_RADIUS[ind],
            )

            prev_longitude = longitude

    def test_process_vehicle(self):
        vehicle_data = [
            {'loc': (51., 17.000714), 'id': 0},
            {'loc': (51.1, 17.001786), 'id': 1},
            {'loc': (51., 17.001858), 'id': 2},
            {'loc': (51., 17.003502), 'id': 3},
            {'loc': (51., 17.003644), 'id': 4},
            {'loc': (51., 17.004859), 'id': 5},
        ]

        # Prepare
        routes = Route.objects.all()
        lines_l = [r.line for r in routes]
        if not lines_l:
            raise RuntimeError('No routes')
        routes_d = {r.line: (r, list(r.stop_set.all())) for r in routes}

        # Process vehicles
        for v in vehicle_data:
            el = {
                'name': 'L. 1',
                'x': v['loc'][0],
                'y': v['loc'][1],
                'k': v['id'],
            }
            process_vehicle(el, routes_d, '2001-02-03 04:05:06+00:00')

        # Check
        # 0
        v = VehicleLocation.objects.get(vehicle_id=0)
        self.assertTrue(v.is_processed)
        self.assertFalse(v.is_at_stop)
        self.assertEqual(v.current_stop, Stop.objects.get(route_index=0))
        self.assertTrue(0 < v.to_next_stop_ratio < 1)

        # 1
        v = VehicleLocation.objects.get(vehicle_id=1)
        self.assertFalse(v.is_processed)
        self.assertEqual(v.unprocessed_reason, const.UNPROC_REASON_TOO_FAR)

        # 2
        v = VehicleLocation.objects.get(vehicle_id=2)
        self.assertTrue(v.is_processed)
        self.assertTrue(v.is_at_stop)
        self.assertEqual(v.current_stop, Stop.objects.get(route_index=2))

        # 3
        v = VehicleLocation.objects.get(vehicle_id=3)
        self.assertTrue(v.is_processed)
        self.assertTrue(v.is_at_stop)
        self.assertEqual(v.current_stop, Stop.objects.get(route_index=3))

        # 4
        v = VehicleLocation.objects.get(vehicle_id=4)
        self.assertTrue(v.is_processed)
        self.assertTrue(v.is_at_stop)
        self.assertEqual(v.current_stop, Stop.objects.get(route_index=3))

        # 4
        v = VehicleLocation.objects.get(vehicle_id=5)
        self.assertFalse(v.is_processed)
        self.assertEqual(v.unprocessed_reason, const.UNPROC_REASON_BEYOND_FINAL_STOP)

