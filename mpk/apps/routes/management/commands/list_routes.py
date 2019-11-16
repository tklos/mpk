from django.core.management import BaseCommand

from routes.models import Route


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('-s', '--list-stops', dest='list_stops', action='store_true', help='List stops')

    def handle(self, *args, **kwargs):
        list_stops = kwargs['list_stops']

        for route in Route.objects.all():
            print(route)
            if list_stops:
                for stop in route.stop_set.all():
                    print('    {}'.format(stop))
                print('')

