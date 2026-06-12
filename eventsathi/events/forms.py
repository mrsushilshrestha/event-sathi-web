from django import forms
from django.utils.text import slugify
from django.utils import timezone
from .models import Event, TicketTier, Speaker, EventSession, Sponsor, Announcement, QAQuestion, Poll, PollChoice


class EventForm(forms.ModelForm):
    unlimited_capacity = forms.BooleanField(
        required=False,
        label='Unlimited attendees',
        widget=forms.CheckboxInput()
    )

    class Meta:
        model = Event
        fields = [
            'title', 'description', 'category', 'banner',
            'start_date', 'end_date',
            'registration_start', 'registration_end',
            'venue', 'city', 'latitude', 'longitude',
            'is_virtual', 'virtual_link', 'max_capacity', 'price', 'tags',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Describe your event — agenda highlights, what attendees will learn, who should attend…'}),
            'start_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'end_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'registration_start': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'registration_end': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'tags': forms.TextInput(attrs={'placeholder': 'e.g. AI, Tech, Innovation'}),
            'virtual_link': forms.URLInput(attrs={'placeholder': 'https://meet.google.com/...'}),
            'title': forms.TextInput(attrs={'placeholder': 'Give your event a catchy title'}),
            'venue': forms.TextInput(attrs={'placeholder': 'Auditorium, Hall, Building name…'}),
            'city': forms.TextInput(attrs={'placeholder': 'Mumbai'}),
            'price': forms.NumberInput(attrs={'placeholder': 'Leave blank for free event', 'min': 0, 'step': '0.01'}),
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set minimum selectable date to now (prevents picking past dates in the UI)
        now_min = timezone.now().strftime('%Y-%m-%dT%H:%M')
        for f in ['start_date', 'end_date', 'registration_start', 'registration_end']:
            self.fields[f].input_formats = ['%Y-%m-%dT%H:%M']
            self.fields[f].widget.attrs['min'] = now_min
        self.fields['registration_start'].required = False
        self.fields['registration_end'].required = False
        self.fields['virtual_link'].required = False
        self.fields['banner'].required = False
        self.fields['latitude'].required = False
        self.fields['longitude'].required = False
        self.fields['price'].required = False
        # If editing and max_capacity is 0, pre-check unlimited
        if self.instance and self.instance.pk and self.instance.max_capacity == 0:
            self.fields['unlimited_capacity'].initial = True

    def clean(self):
        cleaned_data = super().clean()
        now = timezone.now()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        reg_start = cleaned_data.get('registration_start')
        reg_end = cleaned_data.get('registration_end')
        max_capacity = cleaned_data.get('max_capacity')
        price = cleaned_data.get('price')
        unlimited = cleaned_data.get('unlimited_capacity', False)
        is_virtual = cleaned_data.get('is_virtual', False)
        virtual_link = cleaned_data.get('virtual_link', '').strip()
        venue = cleaned_data.get('venue', '').strip()
        city = cleaned_data.get('city', '').strip()

        if price is not None and price < 0:
            self.add_error('price', 'Price cannot be negative.')

        if unlimited:
            cleaned_data['max_capacity'] = 0
        elif max_capacity is not None and max_capacity <= 0:
            self.add_error('max_capacity', 'Maximum capacity must be a positive number.')

        if start_date and start_date < now:
            self.add_error('start_date', 'Start date cannot be in the past. Please choose a future date.')
        if end_date:
            if end_date < now:
                self.add_error('end_date', 'End date cannot be in the past.')
            elif start_date and end_date <= start_date:
                self.add_error('end_date', 'End date must be after the start date.')
        if reg_start and reg_start < now:
            self.add_error('registration_start', 'Registration start cannot be in the past.')
        if reg_end and reg_start and reg_end <= reg_start:
            self.add_error('registration_end', 'Registration end must be after registration start.')
        if reg_end and start_date and reg_end > start_date:
            self.add_error('registration_end', 'Registration must close before or at the start time of the event.')

        if is_virtual:
            if not virtual_link:
                self.add_error('virtual_link', 'Virtual link is required for virtual events.')
            if not venue:
                cleaned_data['venue'] = 'Virtual / Online'
            if not city:
                cleaned_data['city'] = 'Online'
        else:
            if not venue:
                self.add_error('venue', 'Venue is required for in-person events.')
            if not city:
                self.add_error('city', 'City is required for in-person events.')

        return cleaned_data

    def save(self, commit=True):
        event = super().save(commit=False)
        if not event.slug:
            base_slug = slugify(event.title)
            slug = base_slug
            counter = 1
            from .models import Event
            while Event.objects.filter(slug=slug).exclude(pk=event.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            event.slug = slug
        if commit:
            event.save()
        return event


class TicketTierForm(forms.ModelForm):
    class Meta:
        model = TicketTier
        fields = ['name', 'description', 'price', 'capacity', 'benefits', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'benefits': forms.Textarea(attrs={'rows': 4, 'placeholder': 'One benefit per line\nFree lunch\nNetworking access'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        price = cleaned_data.get('price')
        capacity = cleaned_data.get('capacity')

        if price is not None and price < 0:
            self.add_error('price', 'Price cannot be negative.')
        if capacity is not None and capacity <= 0:
            self.add_error('capacity', 'Capacity must be greater than zero.')
        return cleaned_data


class SpeakerForm(forms.ModelForm):
    class Meta:
        model = Speaker
        fields = ['name', 'designation', 'organization', 'bio', 'photo', 'abstract', 'linkedin', 'twitter', 'website']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4}),
            'abstract': forms.Textarea(attrs={'rows': 4}),
        }


class SessionForm(forms.ModelForm):
    class Meta:
        model = EventSession
        fields = ['title', 'description', 'speaker', 'track', 'room', 'start_time', 'end_time', 'stream_url', 'order']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'end_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
        }

    def __init__(self, *args, event=None, **kwargs):
        self.event = event
        super().__init__(*args, **kwargs)
        if event:
            self.fields['speaker'].queryset = Speaker.objects.filter(event=event)
        self.fields['start_time'].input_formats = ['%Y-%m-%dT%H:%M']
        self.fields['end_time'].input_formats = ['%Y-%m-%dT%H:%M']

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')

        if start_time and end_time and end_time <= start_time:
            self.add_error('end_time', 'Session end time must be after start time.')

        if self.event:
            if start_time and (start_time < self.event.start_date or start_time > self.event.end_date):
                self.add_error('start_time', f'Session start time must be between event start ({self.event.start_date}) and end ({self.event.end_date}).')
            if end_time and (end_time < self.event.start_date or end_time > self.event.end_date):
                self.add_error('end_time', f'Session end time must be between event start ({self.event.start_date}) and end ({self.event.end_date}).')

        return cleaned_data


class SponsorForm(forms.ModelForm):
    class Meta:
        model = Sponsor
        fields = ['name', 'tier', 'logo', 'website', 'description', 'booth_info']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'booth_info': forms.Textarea(attrs={'rows': 3}),
        }


class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ['title', 'content', 'priority']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 4}),
        }


class QAQuestionForm(forms.ModelForm):
    class Meta:
        model = QAQuestion
        fields = ['question']
        widgets = {
            'question': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Ask your question...'}),
        }


class PollForm(forms.Form):
    question = forms.CharField(max_length=500, widget=forms.TextInput(attrs={'placeholder': 'Poll question...'}))
    choice_1 = forms.CharField(max_length=300, label='Choice 1')
    choice_2 = forms.CharField(max_length=300, label='Choice 2')
    choice_3 = forms.CharField(max_length=300, label='Choice 3 (optional)', required=False)
    choice_4 = forms.CharField(max_length=300, label='Choice 4 (optional)', required=False)


class CheckInForm(forms.Form):
    ticket_id = forms.CharField(max_length=50, label='Ticket ID / QR Code',
                                 widget=forms.TextInput(attrs={'placeholder': 'e.g. ES-ABC12345'}))
