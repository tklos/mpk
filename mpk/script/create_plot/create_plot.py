import math
import os
import sys
from datetime import datetime

import matplotlib
matplotlib.use('Agg')

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pytz
from matplotlib import rcParams
from matplotlib.collections import LineCollection

from routes.models import Route

sys.path.insert(0, os.path.dirname(__file__))
from lib import settings


def _epoch_to_datetime(sec):
    return datetime.fromtimestamp(sec)


def _calculate_xticks_and_labels(date_from_local, date_to_local, params):
    timezone_local = date_from_local.tzinfo
    date_from_local_utc, date_to_local_utc = date_from_local.replace(tzinfo=pytz.utc), date_to_local.replace(tzinfo=pytz.utc)
    date_from_e, date_to_e = date_from_local_utc.timestamp(), date_to_local_utc.timestamp()

    for ind in range(len(params.xticks_intervals)):
        interval = params.xticks_intervals[ind]
        interval_s = int(interval.total_seconds())

        min_e, max_e = math.ceil(date_from_e / interval_s) * interval_s, math.floor(date_to_e / interval_s) * interval_s

        num_ticks = (max_e - min_e) // interval_s + 1
        if num_ticks > params.max_num_xticks:
            continue

        xticks_e = [min_e + i * interval_s for i in range(num_ticks)]

        xticks = list(map(_epoch_to_datetime, xticks_e))
        labels = [dt.strftime('%H:%M') for dt in xticks]
        for ind, xtick in enumerate(xticks):
            if ind == 0 or xticks[ind-1].date() != xtick.date():
                labels[ind] = xtick.strftime('%Y-%m-%d\n%H:%M')

        xticks_loc_d = [timezone_local.localize(d) for d in xticks]

        return xticks_loc_d, labels

    return [], []


def _process_vehicle_locations(locations, params):
    data, gap_data, gap_data_colours = {}, [], []
    for loc in locations:
        stop_ind = loc.current_stop.route_index if loc.is_at_stop else loc.current_stop.route_index + loc.to_next_stop_ratio

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

    return data, gap_data, gap_data_colours


def create_plot(line_no, date_from_local, date_to_local, out_filename):
    # Check params
    if date_from_local.tzinfo is None or date_to_local.tzinfo is None:
        raise ValueError('Dates have to be timezone-aware')

    ## Get data
    # Route
    try:
        route = Route.objects.get(line=line_no)
    except Route.DoesNotExist as exc:
        raise ValueError('Line {} doesn\'t exist'.format(line_no)) from exc

    # Stops
    stops = list(route.stop_set.all())
    num_stops = len(stops)

    # Vehicle locations
    locations = route.vehiclelocation_set \
            .filter(date__gte=date_from_local, date__lt=date_to_local) \
            .filter(is_processed=True)

    ## Prepare
    # Settings
    params = settings.Params()

    rcParams.update({
        'font.sans-serif': ['Liberation Sans'],
    })

    ## Process data
    # Vehicle locations
    data, gap_data, gap_data_colours = _process_vehicle_locations(locations, params)

    # X axis
    xticks, xticklabels = _calculate_xticks_and_labels(date_from_local, date_to_local, params)
    if not xticks:
        raise RuntimeError('Can\'t calculate xticks for this interval')
    xlim = (date_from_local, date_to_local)

    # Y axis
    full_range = (num_stops - 1) / (1. - 2 * params.stops_margin_n)
    full_margin = full_range - num_stops + 1
    ylim = (num_stops - 1 + full_margin / 2, 0 - full_margin / 2)

    ## Plot
    # Figure
    figure_h = plt.figure(figsize=params.window_size_i, dpi=params.dpi)

    full_window_h = plt.axes([0., 0., 1., 1.], zorder=-20)
    full_window_h.set_axis_off()

    canvas_h = plt.axes((params.canvas_left_edge_n, params.canvas_bottom_edge_n, params.canvas_width_n, params.canvas_height_n), zorder=-20)

    # X axis
    plt.xlim(xlim)
    plt.xticks(xticks, xticklabels, fontsize=params.bottom_fontsize)
    for xtick in xticks:
        plt.axvline(xtick, c='k', ls=':', lw=0.5)

    # Y axis
    plt.yticks(range(num_stops), [stop.display_name for stop in stops], fontsize=params.left_fontsize, linespacing=1.)
    plt.ylim(ylim)
    for stop_ind in range(len(stops)):
        plt.axhline(stop_ind, c='k', ls=':', lw=0.5)

    # Plot lines
    for d in data.values():
        c_ind = 0 if d[1][-1] > d[1][0] else 1
        plt.plot(d[0], d[1], color=params.line_colours[c_ind])

    gap_line_h = LineCollection(gap_data, colors=gap_data_colours, ls='--')
    canvas_h.add_collection(gap_line_h)

    # Title
    title_str = 'MPK Wrocław stringline plot: line {}'.format(line_no.upper())
    full_window_h.text(.5, params.title_top_margin_n, title_str, fontsize=params.title_fontsize, va='top', ha='center')

    # Plot figure
    plt.savefig(out_filename, dpi=params.dpi)

    plt.close(figure_h)

