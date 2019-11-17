import logging
import os
import random
import string

from django.conf import settings
from django.shortcuts import render
from django.views.generic import FormView

from .forms import ProcessForm


logger = logging.getLogger('default')


class HomeView(FormView):
    form_class = ProcessForm
    template_name = 'mpk/home.html'

    @staticmethod
    def get_std_context_data():
        return {
            'was_processed': None,
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        std_context = self.get_std_context_data()
        context.update(std_context)
        context.update({
            'was_processed': False
        })
        return context

    def form_valid(self, form):
        from mpk.script.create_plot.create_plot import create_plot

        # Processing arguments
        line_no = form.cleaned_data['line']
        date_from, date_to = settings.LOCAL_TIMEZONE.localize(form.cleaned_data['date_from']), settings.LOCAL_TIMEZONE.localize(form.cleaned_data['date_to'])

        # Directory and filename
        location = ''.join(random.choices(string.ascii_letters, k=6))
        out_dir = '{}/{}'.format(
            settings.MEDIA_ROOT,
            location,
        )
        plot_fn = '{}.png'.format(location)
        plot_filename = '{}/{}'.format(out_dir, plot_fn)
        # django_plot_location = '{}/{}/{}'.format(settings.DJANGO_DOWNLOAD_LOCATION, location, plot_fn)
        django_plot_location = '{}/{}/{}'.format(settings.MEDIA_URL, location, plot_fn)

        # Process
        context = self.get_std_context_data()
        context.update({
            'form': form,
            'was_processed': True,
            'success': None,
        })

        try:
            logger.info('Running {} {} -- {} {}'.format(line_no, date_from, date_to, out_dir))
            logger.debug('Creating out-dir {}'.format(out_dir))
            os.makedirs(out_dir)

            create_plot(line_no, date_from, date_to, plot_filename)
            context.update({
                'success': True,
                'plot_path': django_plot_location,
            })

            # Mogrify
            # cmd = 'mogrify -alpha off {}'.format(plot_filename)
            # logger.debug('Running mogrify {}'.format(cmd))
            # ret = os.system(cmd)
            # if ret != 0:
            #     raise RuntimeError('{} returned {}'.format(cmd, ret))

        except Exception as exc:
            context.update({
                'success': False,
                'error': str(exc),
            })
            logger.exception(exc)

        return render(self.request, self.template_name, context=context)

