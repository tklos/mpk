from django.core.management import BaseCommand

from routes.models import Route

from .add_route import check_if_any_stops_overlap


def line_sort_order(route):
    line = route.line

    try:
        return int(line)
    except Exception:
        pass

    return 1000 + sum(ord(c) for c in line)


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('-s', '--list-stops', dest='list_stops', action='store_true', help='List stops')

    def handle(self, *args, **kwargs):
        list_stops = kwargs['list_stops']

        for route in sorted(Route.objects.all(), key=line_sort_order):
            print(route)
            if list_stops:
                for stop in route.stop_set.all():
                    print('    {}'.format(stop))

                check_if_any_stops_overlap(route)
                print('')

