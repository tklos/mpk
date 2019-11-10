import os
import sys
from datetime import datetime

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pytz
from matplotlib import rcParams
from matplotlib.collections import LineCollection

from routes.models import Route

sys.path.insert(0, os.path.dirname(__file__))
from lib import settings


def create_plot(line_no, date_from, date_to):
    try:
        route = Route.objects.get(line=line_no)
    except Route.DoesNotExist as exc:
        raise ValueError('Line {} doesn\'t exist'.format(line_no)) from exc


    params = settings.Params()
    out_filename = 'x.png'

    # date_from, date_to = datetime(2019, 11, 9, 10, 40).replace(tzinfo=pytz.utc), datetime(2019, 11, 9, 12, 0).replace(tzinfo=pytz.utc)
    date_from, date_to = datetime(2019, 11, 10, 21, 44).replace(tzinfo=pytz.utc), datetime(2019, 11, 10, 23, 0).replace(tzinfo=pytz.utc)

    # Process stops
    stops = list(route.stop_set.all())
    num_stops = len(stops)

    full_range = (num_stops - 1) / (1. - 2 * params.stops_margin_n)
    full_margin = full_range - num_stops + 1
    ylim = (0 - full_margin / 2, num_stops - 1 + full_margin / 2)

    # Settings
    rcParams.update({
        'font.sans-serif': ['Liberation Sans'],
    })

    # Figure
    figure_h = plt.figure(figsize=params.window_size_i, dpi=params.dpi)

    full_window_h = plt.axes([0., 0., 1., 1.], zorder=-20)
    full_window_h.set_axis_off()

    canvas_h = plt.axes((params.canvas_left_edge_n, params.canvas_bottom_edge_n, params.canvas_width_n, params.canvas_height_n), zorder=-20)

    # X axis
    plt.xlim((date_from, date_to))

    # Y axis
    plt.ylim(ylim)
    plt.yticks(range(num_stops), [stop.display_name.replace('\\n', '\n') for stop in stops], fontsize=params.left_fontsize, linespacing=0.9)

    for stop_ind in range(len(stops)):
        plt.axhline(stop_ind, c='k', ls=':', lw=0.5)

    # Data
    locations = route.vehiclelocation_set \
            .filter(date__gte=date_from, date__lt=date_to) \
            .filter(is_processed=True)

    data, gap_data, gap_data_colours = {}, [], []
    for loc in locations:
        if loc.is_at_stop:
            stop_ind = loc.current_stop.route_index
        else:
            stop_ind = loc.current_stop.route_index + loc.to_next_stop_ratio

        d = data.get(loc.vehicle_id, None)
        if d is None:
            # First data point
            data[loc.vehicle_id] = ([loc.date], [stop_ind])

        else:
            diff = loc.date - d[0][-1]
            if diff > params.max_diff_continuous_data:
                # Long gap
                gap_data.append(((mdates.date2num(d[0][-1]), d[1][-1]), (mdates.date2num(loc.date), stop_ind)))
                gap_data_colours.append(params.line_colours[0 if stop_ind > d[1][-1] else 1])
                d[0].append(loc.date - diff / 2)
                d[1].append(None)

            d[0].append(loc.date)
            d[1].append(stop_ind)

    # Plot lines
    for d in data.values():
        c_ind = 0 if d[1][-1] > d[1][0] else 1
        plt.plot(d[0], d[1], color=params.line_colours[c_ind])

    gap_line_h = LineCollection(gap_data, colors=gap_data_colours, ls='--')
    canvas_h.add_collection(gap_line_h)

    # Title
    title_str = 'MPK Wrocław stringline plot: line {}'.format(line_no)
    full_window_h.text(.5, params.title_top_margin_n, title_str, fontsize=params.title_fontsize, va='top', ha='center')

    # Plot figure
    plt.savefig(out_filename, dpi=params.dpi)


create_plot(31, None, None)

