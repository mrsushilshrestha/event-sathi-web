from django import forms
from django.utils.text import slugify
from .models import Event, TicketTier, Speaker, EventSession, Sponsor, Announcement, QAQuestion, Poll, PollChoice


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            'title', 'description', 'category', 'banner',
            'start_date', 'end_date', 'venue', 'city',
            'is_virtual', 'virtual_link', 'max_capacity', 'status', 'tags'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5}),
            'start_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'end_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'tags': forms.TextInput(attrs={'placeholder': 'e.g. AI, Tech, Innovation'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['start_date'].input_formats = ['%Y-%m-%dT%H:%M']
        self.fields['end_date'].input_formats = ['%Y-%m-%dT%H:%M']

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
