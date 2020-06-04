import logging
import os
import random
import shlex
import string
import subprocess
import time
from datetime import datetime

from django.conf import settings
from django.shortcuts import render
from django.views.generic import FormView

from mpk.script.create_plot.create_plot import create_plot

from .forms import ProcessForm


logger = logging.getLogger('default')


class HomeView(FormView):
    form_class = ProcessForm
    template_name = 'mpk/home.html'

    def __init__(self, *args, **kwargs):
        self.start_time = time.time()
        super().__init__(*args, **kwargs)

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
        current_time = datetime.now()

        # Processing arguments
        line_no = form.cleaned_data['line']
        date_from, date_to = form.cleaned_data['date_from'], form.cleaned_data['date_to']

        # Directory and filename
        location = ''.join(random.choices(string.ascii_letters, k=6))
        location_ext = '{}-{}'.format(current_time.strftime('%y%m%d-%H%M'), location)
        out_dir = f'{settings.MEDIA_ROOT}/{location_ext}'
        plot_fn = '{:0>3s}--{}--{}.png'.format(line_no, date_from.strftime('%y%m%d-%H%M'), date_to.strftime('%y%m%d-%H%M'))
        plot_filename = f'{out_dir}/{plot_fn}'
        django_plot_location = f'{settings.MEDIA_URL}/{location_ext}/{plot_fn}'

        # Process
        context = self.get_std_context_data()
        context.update({
            'form': form,
            'was_processed': True,
            'success': None,
        })

        try:
            logger.info(f'Running {line_no} {date_from} -- {date_to} {out_dir}')
            logger.debug(f'Creating out-dir {out_dir}')
            os.makedirs(out_dir)

            # Create plot
            create_plot(line_no, date_from, date_to, plot_filename)

            # Calculate previous/next plot time ranges
            plot_length = date_to - date_from if form.date_from_timedelta is None else form.date_from_timedelta[1]
            prev_plot_from = (date_from - plot_length).strftime('%Y-%m-%d %H:%M') if form.date_from_timedelta is None else form.date_from_timedelta[0]
            prev_plot_to = date_from.strftime('%Y-%m-%d %H:%M')
            next_plot_from = date_to.strftime('%Y-%m-%d %H:%M') if form.date_from_timedelta is None else form.date_from_timedelta[0]
            next_plot_to = (date_to + plot_length).strftime('%Y-%m-%d %H:%M')

            context.update({
                'success': True,
                'plot_path': django_plot_location,
                'line': line_no,
                'prev_plot_from': prev_plot_from,
                'prev_plot_to': prev_plot_to,
                'next_plot_from': next_plot_from,
                'next_plot_to': next_plot_to,
            })

            # Mogrify
            if settings.RUN_MOGRIFY:
                cmd = f'mogrify -alpha off -colors 256 {plot_filename}'

                logger.debug(f'Running mogrify {cmd}')
                cmd_args = shlex.split(cmd)
                ret = subprocess.call(cmd_args, close_fds=False)
                if ret:
                    raise RuntimeError(f'{cmd} returned {ret}')

            # Log processing time
            total_time = time.time() - self.start_time
            logger.info(f'Processing finished   {location_ext}; Total time {total_time:.2f}s.')

        except Exception as exc:
            context.update({
                'success': False,
                'error': str(exc),
            })
            logger.exception(exc)

        return render(self.request, self.template_name, context=context)

