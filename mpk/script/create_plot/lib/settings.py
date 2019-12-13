from datetime import timedelta


class Params:

    DIR_UP, DIR_DOWN = 0, 1

    def __init__(self):
        # Window
        window_size_p = (1350, 955)
        dpi = 96.
        canvas_margin_p = (195, 30, 50, 55)  # l,r,b,t

        # Fontsize
        err_fontsize = 11
        title_fontsize = 22
        bottom_fontsize = 14
        left_fontsize = 12

        # Plot
        stops_margin_p = 10
        max_diff_continuous_data = timedelta(seconds=30)
        line_colours = ['C0', 'C1']
        title_top_margin_p = 12
        xticks_intervals = [
                timedelta(minutes=1), timedelta(minutes=2), timedelta(minutes=5), timedelta(minutes=10), timedelta(minutes=20), timedelta(minutes=30),
                timedelta(hours=1), timedelta(hours=2), timedelta(hours=4), timedelta(hours=6), timedelta(hours=12),
        ]
        max_num_xticks = 9


        ## Processing
        window_width_p, window_height_p = window_size_p
        window_size_i = tuple(x / dpi for x in window_size_p)

        canvas_left_edge_p, canvas_right_edge_p = canvas_margin_p[0], window_size_p[0] - canvas_margin_p[1]
        canvas_bottom_edge_p, canvas_top_edge_p = canvas_margin_p[2], window_size_p[1] - canvas_margin_p[3]
        canvas_width_p, canvas_height_p = canvas_right_edge_p - canvas_left_edge_p, canvas_top_edge_p - canvas_bottom_edge_p

        canvas_left_edge_n, canvas_right_edge_n = canvas_left_edge_p / window_width_p, canvas_right_edge_p / window_width_p
        canvas_bottom_edge_n, canvas_top_edge_n = canvas_bottom_edge_p / window_height_p, canvas_top_edge_p / window_height_p
        canvas_width_n, canvas_height_n = canvas_right_edge_n - canvas_left_edge_n, canvas_top_edge_n - canvas_bottom_edge_n

        title_top_margin_n = 1. - title_top_margin_p / window_height_p


        ## Save params
        # Window
        self.window_width_p, self.window_height_p = window_width_p, window_height_p
        self.window_size_i = window_size_i
        self.dpi = dpi
        self.canvas_width_p, self.canvas_height_p = canvas_width_p, canvas_height_p
        self.canvas_left_edge_n, self.canvas_right_edge_n, self.canvas_width_n = canvas_left_edge_n, canvas_right_edge_n, canvas_width_n
        self.canvas_bottom_edge_n, self.canvas_top_edge_n, self.canvas_height_n = canvas_bottom_edge_n, canvas_top_edge_n, canvas_height_n

        # Fontsize
        self.err_fontsize = err_fontsize
        self.title_fontsize = title_fontsize
        self.bottom_fontsize = bottom_fontsize
        self.left_fontsize = left_fontsize

        # Plot
        self.stops_margin_n = stops_margin_p / canvas_height_p
        self.max_diff_continuous_data = max_diff_continuous_data
        self.line_colours = line_colours
        self.title_top_margin_n = title_top_margin_n
        self.xticks_intervals = xticks_intervals
        self.max_num_xticks = max_num_xticks


        ## Check params
        if self.stops_margin_n >= .5:
            raise RuntimeError('stops_margin_n too large: {}'.format(self.stops_margin_n))

