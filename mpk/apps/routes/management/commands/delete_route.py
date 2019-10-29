from django.core.management import BaseCommand

from routes.models import Route


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('line_no')

    def handle(self, *args, **kwargs):
        line_no = kwargs['line_no']

        Route.objects.get(line=line_no).delete()

