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
    date_from = forms.CharField(max_length=16)
    date_to = forms.CharField(max_length=16)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Set widget attributes
        date_field_attrs = {
            'class': 'form-control input-sm input-font-size-14 width-input-date',
            'autocomplete': 'off',
            'placeholder': 'yyyy-mm-dd HH:MM',
        }
        dropdown_field_attrs = {
            'class': 'form-control input-sm input-font-size-14 width-auto',
        }

        current_time = datetime.now(settings.LOCAL_TIMEZONE)

        self.fields['line'].widget.attrs.update(dropdown_field_attrs)
        line_choices = [(route.line, route.line.upper()) for route in Route.objects.all()]
        line_choices.sort(key=line_sort_order)
        self.fields['line'].choices = line_choices

        self.fields['date_from'].widget.attrs.update(date_field_attrs)
        self.fields['date_from'].initial = (current_time - timedelta(hours=2)).strftime('%Y-%m-%d %H:%M')

        self.fields['date_to'].widget.attrs.update(date_field_attrs)
        self.fields['date_to'].initial = current_time.strftime('%Y-%m-%d %H:%M')

    def clean(self):
        date_from_s, date_to_s = self.cleaned_data['date_from'], self.cleaned_data['date_to']

        try:
            date_from = datetime.strptime(date_from_s, '%Y-%m-%d %H:%M')
            date_to = datetime.strptime(date_to_s, '%Y-%m-%d %H:%M')
        except ValueError as exc:
            raise ValidationError('Can\'t parse date: {}'.format(exc))

        if date_to < date_from:
            raise ValidationError('Date-to earlier than date-from..')
        self.cleaned_data['date_from'], self.cleaned_data['date_to'] = date_from, date_to

        return self.cleaned_data

