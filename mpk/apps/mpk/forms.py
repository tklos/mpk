from datetime import datetime, timedelta

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError

from routes.models import Route


def line_sort_order(el):
    line = el[0]

    # int
    try:
        return int(line)
    except Exception:
        pass
    # string
    return 1000 + sum(ord(c) for c in line)


class ProcessForm(forms.Form):
    line = forms.ChoiceField()
    date_from = forms.CharField(max_length=16, initial='-2hours')
    date_to = forms.CharField(max_length=16, initial='now')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Current time
        self.current_time = datetime.now(settings.LOCAL_TIMEZONE)
        self.current_time_m = self.current_time.replace(second=0, microsecond=0)
        self.current_time_next_m = self.current_time_m + timedelta(minutes=1)

        self.date_from_timedelta = None  # None or (timedelta_str, timedelta)
        self.date_to_is_now = False

        # Set widget attributes
        date_field_attrs = {
            'class': 'form-control input-sm input-font-size-14 width-input-date',
            'autocomplete': 'off',
        }
        dropdown_field_attrs = {
            'class': 'form-control input-sm input-font-size-14 width-auto',
        }

        line_choices = sorted([(route.line, route.line.upper()) for route in Route.objects.all()], key=line_sort_order)
        self.fields['line'].choices = line_choices
        self.fields['line'].widget.attrs.update(dropdown_field_attrs)

        self.fields['date_from'].widget.attrs.update(date_field_attrs)
        self.fields['date_from'].widget.attrs['placeholder'] = 'datetime or offset'

        self.fields['date_to'].widget.attrs.update(date_field_attrs)
        self.fields['date_to'].widget.attrs['placeholder'] = 'datetime or "now"'

    def clean_date_from(self):
        s = self.cleaned_data['date_from'].strip()

        prefix, suffix = '-', 'hours'
        try:
            if s.startswith(prefix) and s.endswith(suffix):
                offset_h = float(s[len(prefix):-len(suffix)])
                date_from = timedelta(hours=offset_h)
                self.date_from_timedelta = (s, date_from)
            else:
                date_from = settings.LOCAL_TIMEZONE.localize(datetime.strptime(s, '%Y-%m-%d %H:%M'))

        except Exception as exc:
            raise ValidationError('Can\'t parse date: {}'.format(exc))

        return date_from

    def clean_date_to(self):
        s = self.cleaned_data['date_to'].strip()

        try:
            if s == 'now':
                self.date_to_is_now = True
                date_to = self.current_time_next_m
            else:
                date_to = settings.LOCAL_TIMEZONE.localize(datetime.strptime(s, '%Y-%m-%d %H:%M'))

        except Exception as exc:
            raise ValidationError('Can\'t parse date: {}'.format(exc))

        return date_to

    def clean(self):
        super().clean()

        # Check dates
        date_from, date_to = self.cleaned_data.get('date_from'), self.cleaned_data.get('date_to')
        if date_from is not None and date_to is not None:
            if isinstance(date_from, timedelta):
                try:
                    date_from = date_to - date_from
                except Exception as exc:
                    raise ValidationError('Can\'t create date-from: {}'.format(exc))

                if self.date_to_is_now:
                    date_from -= timedelta(minutes=1)

            if date_to < date_from:
                self.add_error(None, 'Date-to earlier than date-from')

            max_plot_interval = settings.MAX_PLOT_INTERVAL
            if self.date_to_is_now:
                max_plot_interval += timedelta(minutes=1)
            if date_to - date_from > max_plot_interval:
                self.add_error(None, 'Plot interval is larger than maximum allowed {} hours'.format(settings.MAX_PLOT_INTERVAL // timedelta(hours=1)))

        self.cleaned_data['date_from'], self.cleaned_data['date_to'] = date_from, date_to

