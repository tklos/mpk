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

    def clean(self):
        # Parse dates
        date_from_s, date_to_s = self.cleaned_data['date_from'].strip(), self.cleaned_data['date_to'].strip()
        try:
            # To date
            if date_to_s == 'now':
                date_to = self.current_time_next_m
            else:
                date_to = settings.LOCAL_TIMEZONE.localize(datetime.strptime(date_to_s, '%Y-%m-%d %H:%M'))

            # From date
            prefix, suffix = '-', 'hours'
            if date_from_s.startswith(prefix) and date_from_s.endswith(suffix):
                offset_h = float(date_from_s[len(prefix):-len(suffix)])
                date_from = date_to - timedelta(hours=offset_h)
                if date_to_s == 'now':
                    date_from -= timedelta(minutes=1)
            else:
                date_from = settings.LOCAL_TIMEZONE.localize(datetime.strptime(date_from_s, '%Y-%m-%d %H:%M'))

        except ValueError as exc:
            raise ValidationError('Can\'t parse date: {}'.format(exc))

        # Check dates
        if date_to < date_from:
            raise ValidationError('Date-to earlier than date-from..')
        self.cleaned_data['date_from'], self.cleaned_data['date_to'] = date_from, date_to

        return self.cleaned_data

