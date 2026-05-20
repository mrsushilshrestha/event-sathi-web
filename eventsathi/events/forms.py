from django import forms
from django.utils.text import slugify
from django.utils import timezone
from .models import Event, TicketTier, Speaker, EventSession, Sponsor, Announcement, QAQuestion, Poll, PollChoice


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            'title', 'description', 'category', 'banner',
            'start_date', 'end_date',
            'registration_start', 'registration_end',
            'venue', 'city',
            'is_virtual', 'virtual_link', 'max_capacity', 'tags', 'is_featured',
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
        self.fields['is_featured'].required = False
        self.fields['virtual_link'].required = False
        self.fields['banner'].required = False

    def clean(self):
        cleaned_data = super().clean()
        now = timezone.now()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        reg_start = cleaned_data.get('registration_start')
        reg_end = cleaned_data.get('registration_end')

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
        super().__init__(*args, **kwargs)
        if event:
            self.fields['speaker'].queryset = Speaker.objects.filter(event=event)
        self.fields['start_time'].input_formats = ['%Y-%m-%dT%H:%M']
        self.fields['end_time'].input_formats = ['%Y-%m-%dT%H:%M']


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
