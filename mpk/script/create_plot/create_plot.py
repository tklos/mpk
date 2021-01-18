import math
from datetime import datetime

import pytz
from matplotlib.collections import LineCollection
from matplotlib.figure import Figure

from routes.models import Route

from .lib import settings


# Some global settings
params = settings.Params()
settings.set_mpl_settings()


_MPL_EPOCH_PLUS_DAY = datetime(1, 1, 1, tzinfo=pytz.utc)


def _epoch_to_datetime(sec):
    return datetime.fromtimestamp(sec)


def _datetime_to_num(d):
    """ Convert datetime to matplotlib's internal datetime representation

    This is ~50 times faster than matplotlib.dates.date2num.

    It also seems to be (slightly) faster than a more obvious implementation:
    _MPL_EPOCH = datetime(1, 1, 1, tzinfo=pytz.utc).timestamp() - 86400.
    return (d.timestamp() - _MPL_EPOCH) / 86400.

    Note: matplotlib 3.3.0 changed its epoch from 0000-12-31 to 1970-01-01.
    """
    return (d - _MPL_EPOCH_PLUS_DAY).total_seconds() / 86400. + 1.


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


def _process_vehicle_locations(locations, num_stops, params):
    """
    Returns a dict with 'data', 'gap-data' and 'invalid-data' keys. Each value is a dict of vehicle_id: list-of-lines,
    where line is a list of two-element tuples (date, stop-idx).
    Dates are in matplotlib date format.
    These structures are ready to be used to create LineCollection objects
    """
    max_diff_continuous_data = params.max_diff_continuous_data_s / 24 / 3600
    max_length_data_gap = params.max_length_data_gap_h / 24

    data, gap_data, invalid_data = {}, {}, {}
    prev_vehicle_id, prev_point, num_unprocessed_in_a_row = None, None, 0
    for loc in locations:
        date_ = _datetime_to_num(loc.date)
        vehicle_id = loc.vehicle_id

        if loc.is_processed:
            stop_ind = loc.current_stop.route_index if loc.is_at_stop else loc.current_stop.route_index + loc.to_next_stop_ratio
            point = (date_, stop_ind)

            if prev_vehicle_id != vehicle_id:
                # First data point
                data[vehicle_id] = [[]]
                num_unprocessed_in_a_row = 0

            else:
                # Not the first data point
                diff = date_ - prev_point[0]
                if diff > max_diff_continuous_data:
                    # Data gap or invalid data
                    num_exp_pts = round(diff * 24 * 3600 / params.sampling_interval_s) - 1  # Expected number of points
                    if num_unprocessed_in_a_row > num_exp_pts / 2:
                        # Invalid data
                        dest_data = invalid_data
                    else:
                        # Data gap
                        dest_data = gap_data

                        ## Heuristics for not plotting data gap when reusing vehicle id
                        # Case 1: gap longer than params.max_length_data_gap hours
                        if diff > max_length_data_gap:
                            dest_data = None

                        # Case 2: gap from almost the first stop to almost the last one
                        prev_stop_ind = prev_point[1]
                        min_stop_ind, max_stop_ind = min(prev_stop_ind, stop_ind), max(prev_stop_ind, stop_ind)
                        if min_stop_ind <= 2 and max_stop_ind >= num_stops-3:
                            dest_data = None

                    if dest_data is None:
                        # Break this vehicle data in two and don't plot line between the two parts
                        new_vehicle_id = str(vehicle_id)
                        while new_vehicle_id in data:
                            new_vehicle_id = f'{new_vehicle_id}_'

                        data[new_vehicle_id] = data[vehicle_id]
                        data[vehicle_id] = [[]]

                    else:
                        # Plot gap/invalid data line
                        dest_data.setdefault(loc.vehicle_id, []).append([prev_point, point])
                        data[vehicle_id][0].append((date_ - diff / 2, None))

            # Add this point
            data[vehicle_id][0].append(point)

            # Set last processed point
            prev_vehicle_id, prev_point, num_unprocessed_in_a_row = vehicle_id, point, 0

        else:
            # Unprocessed location
            if prev_vehicle_id != vehicle_id:
                # New vehicle id; ignore all unprocessed locations before the first processed
                continue

            num_unprocessed_in_a_row += 1

    return {
        'data': data,
        'gap-data': gap_data,
        'invalid-data': invalid_data,
    }


def create_plot(line_no, date_from_local, date_to_local, out_filename):
    # Check params
    if date_from_local.tzinfo is None or date_to_local.tzinfo != date_from_local.tzinfo:
        raise ValueError('Dates have to be timezone-aware')

    timezone_local = date_from_local.tzinfo

    ## Get data
    # Route
    try:
        route = Route.objects.get(line=line_no)
    except Route.DoesNotExist as exc:
        raise ValueError(f'Line {line_no} doesn\'t exist') from exc

    # Stops
    stops = list(route.stop_set.all())
    num_stops = len(stops)

    # Vehicle locations
    locations = (
        route
        .vehiclelocation_set
        .select_related('current_stop')
        .filter(date__gte=date_from_local, date__lt=date_to_local)
        .order_by('vehicle_id', 'date')
    )

    ## Process data
    # Vehicle locations
    data = _process_vehicle_locations(locations, num_stops, params)

    # No locations
    any_data_to_display = any([data['data'], data['gap-data'], data['invalid-data']])

    # Vehicle directions
    vehicle_directions = {}
    for veh_id, d in data['data'].items():
        vehicle_directions[veh_id] = params.DIR_UP if d[0][-1][1] > d[0][0][1] else params.DIR_DOWN

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
    figure_h = Figure(
        figsize=params.window_size_i,
        dpi=params.dpi,
    )

    full_window_h = figure_h.add_axes(
        [0., 0., 1., 1.],
        zorder=-20,
    )
    full_window_h.set_axis_off()

    canvas_h = figure_h.add_axes(
        (params.canvas_left_edge_n, params.canvas_bottom_edge_n, params.canvas_width_n, params.canvas_height_n),
        zorder=-20,
    )

    # X axis
    canvas_h.set_xlim(xlim)
    canvas_h.set_xticks(xticks)
    canvas_h.set_xticklabels(
        xticklabels,
        fontsize=params.bottom_fontsize,
    )
    for xtick in xticks:
        canvas_h.axvline(
            xtick,
            color='k',
            ls=':',
            lw=0.5,
        )

    # Y axis
    canvas_h.set_yticks(range(num_stops))
    canvas_h.set_yticklabels(
        [stop.display_name for stop in stops],
        fontsize=params.left_fontsize,
        linespacing=1.,
    )
    canvas_h.set_ylim(ylim)
    for stop_ind in range(len(stops)):
        canvas_h.axhline(
            stop_ind,
            color='k',
            ls=':',
            lw=0.5,
        )

    # Plot data
    for data_type in ['data', 'gap-data', 'invalid-data']:
        this_line_params = params.line_params[data_type]
        line_data, colours = [], []
        for veh_id, d in data[data_type].items():
            line_data.extend(d)
            colours.extend([params.line_colours[vehicle_directions[veh_id]]] * len(d))
        line_h = LineCollection(
            line_data,
            colors=colours,
            ls=this_line_params['ls'],
            zorder=this_line_params['zorder'],
        )
        canvas_h.add_collection(line_h, autolim=False)

    # No data to display
    if not any_data_to_display:
        earliest_data = (
            route
            .vehiclelocation_set
            .order_by('date')
            .first()
        )
        latest_data = (
            route
            .vehiclelocation_set
            .order_by('-date')
            .first()
        )

        if not earliest_data:
            no_data_msg = f'No data collected so far for line {line_no}'
        elif date_to_local < earliest_data.date:
            no_data_msg = 'The earliest data available for line {}\nis at {}'.format(line_no, earliest_data.date.astimezone(timezone_local).strftime('%Y-%m-%d %H:%M'))
        elif latest_data.date < date_to_local:
            no_data_msg = 'The latest data available for line {}\nis at {}'.format(line_no, latest_data.date.astimezone(timezone_local).strftime('%Y-%m-%d %H:%M'))
        else:
            no_data_msg = 'No data for this plot'

        canvas_h.text(
            .5,
            .5,
            no_data_msg,
            fontsize=params.no_data_fontsize,
            ha='center',
            va='center',
            transform=canvas_h.transAxes,
        )

    # Title
    title_str = f'MPK Wrocław stringline plot: line {line_no.upper()}'
    full_window_h.text(
        .5,
        params.title_top_margin_n,
        title_str,
        fontsize=params.title_fontsize,
        va='top',
        ha='center',
    )

    # Plot figure
    figure_h.savefig(out_filename, dpi=params.dpi)

