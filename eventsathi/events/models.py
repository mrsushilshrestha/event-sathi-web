import qrcode
import io
import os
import base64
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Event(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    CATEGORY_CHOICES = [
        ('conference', 'Conference'),
        ('workshop', 'Workshop'),
        ('seminar', 'Seminar'),
        ('webinar', 'Webinar'),
        ('hackathon', 'Hackathon'),
        ('cultural', 'Cultural'),
        ('sports', 'Sports'),
        ('networking', 'Networking'),
        ('other', 'Other'),
    ]
    organizer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='organized_events')
    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=300, unique=True)
    description = models.TextField()
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='conference')
    banner = models.ImageField(upload_to='event_banners/', blank=True, null=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    registration_start = models.DateTimeField(blank=True, null=True)
    registration_end = models.DateTimeField(blank=True, null=True)
    venue = models.CharField(max_length=300)
    city = models.CharField(max_length=100)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    is_virtual = models.BooleanField(default=False)
    virtual_link = models.URLField(blank=True)
    max_capacity = models.PositiveIntegerField(default=100)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=0.00)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='published')
    is_featured = models.BooleanField(default=False)
    tags = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if not is_new:
            # Sync default ticket tier (General Admission) or single active tier
            tier = self.ticket_tiers.filter(name='General Admission').first()
            if not tier:
                if self.ticket_tiers.count() == 1:
                    tier = self.ticket_tiers.first()
            if tier:
                tier.price = self.price or 0.00
                tier.capacity = self.max_capacity
                tier.save()

    def get_registered_count(self):
        return self.registrations.filter(status='confirmed').count()

    def get_available_seats(self):
        if self.max_capacity == 0:
            return float('inf')
        return self.max_capacity - self.get_registered_count()

    def is_unlimited_capacity(self):
        return self.max_capacity == 0

    def is_registration_open(self):
        return self.status == 'published' and self.start_date > timezone.now()

    def get_tags_list(self):
        if self.tags:
            return [t.strip() for t in self.tags.split(',') if t.strip()]
        return []

    def get_min_price(self):
        tiers = self.ticket_tiers.filter(is_active=True)
        if not tiers.exists():
            return self.price or 0.00
        prices = [t.price for t in tiers]
        return min(prices)

    def get_live_status(self):
        now = timezone.now()
        if self.status == 'ongoing' or (self.start_date <= now <= self.end_date):
            return 'live'
        elif self.status in ('completed',) or self.end_date < now:
            return 'past'
        else:
            return 'upcoming'


class TicketTier(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='ticket_tiers')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    capacity = models.PositiveIntegerField(default=50)
    benefits = models.TextField(blank=True, help_text='One benefit per line')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.event.title} - {self.name}"

    def get_sold_count(self):
        return self.registrations.filter(status='confirmed').count()

    def get_available(self):
        return self.capacity - self.get_sold_count()

    def get_benefits_list(self):
        if self.benefits:
            return [b.strip() for b in self.benefits.split('\n') if b.strip()]
        return []

    def is_free(self):
        return self.price == 0


class Registration(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('checked_in', 'Checked In'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='registrations')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='registrations')
    ticket_tier = models.ForeignKey(TicketTier, on_delete=models.CASCADE, related_name='registrations')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='confirmed')
    qr_code = models.TextField(blank=True)
    ticket_id = models.CharField(max_length=50, unique=True)
    registered_at = models.DateTimeField(auto_now_add=True)
    checked_in_at = models.DateTimeField(null=True, blank=True)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    class Meta:
        ordering = ['-registered_at']

    def __str__(self):
        return f"{self.user.username} - {self.event.title}"

    def generate_qr_code(self):
        data = f"EVENTSATHI:{self.ticket_id}:{self.user.username}:{self.event.slug}"
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        self.qr_code = base64.b64encode(buffer.getvalue()).decode()
        return self.qr_code

    def save(self, *args, **kwargs):
        if not self.ticket_id:
            import uuid
            self.ticket_id = f"ES-{str(uuid.uuid4()).upper()[:8]}"
        if not self.qr_code:
            self.generate_qr_code()
        super().save(*args, **kwargs)


class Speaker(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='speakers')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='speaker_profiles')
    name = models.CharField(max_length=200)
    designation = models.CharField(max_length=200)
    organization = models.CharField(max_length=200, blank=True)
    bio = models.TextField()
    photo = models.ImageField(upload_to='speaker_photos/', blank=True, null=True)
    abstract = models.TextField(blank=True)
    linkedin = models.URLField(blank=True)
    twitter = models.URLField(blank=True)
    website = models.URLField(blank=True)

    def __str__(self):
        return f"{self.name} @ {self.event.title}"


class EventSession(models.Model):
    TRACK_CHOICES = [
        ('main', 'Main Stage'),
        ('technical', 'Technical Track'),
        ('workshop', 'Workshop'),
        ('keynote', 'Keynote'),
        ('panel', 'Panel Discussion'),
        ('networking', 'Networking'),
        ('break', 'Break'),
    ]
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='sessions')
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    speaker = models.ForeignKey(Speaker, on_delete=models.SET_NULL, null=True, blank=True, related_name='sessions')
    track = models.CharField(max_length=50, choices=TRACK_CHOICES, default='main')
    room = models.CharField(max_length=100, blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    max_capacity = models.PositiveIntegerField(default=0)
    stream_url = models.URLField(blank=True)
    is_recorded = models.BooleanField(default=False)
    recording_url = models.URLField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['start_time', 'order']

    def __str__(self):
        return f"{self.event.title} - {self.title}"

    def duration_minutes(self):
        delta = self.end_time - self.start_time
        return int(delta.total_seconds() / 60)


class FavoriteSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorite_sessions')
    session = models.ForeignKey(EventSession, on_delete=models.CASCADE, related_name='favorites')
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'session')


class FavoriteEvent(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorite_events')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='favorited_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'event')

    def __str__(self):
        return f"{self.user.username} - {self.event.title}"



class Sponsor(models.Model):
    TIER_CHOICES = [
        ('platinum', 'Platinum'),
        ('gold', 'Gold'),
        ('silver', 'Silver'),
        ('bronze', 'Bronze'),
        ('community', 'Community Partner'),
    ]
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='sponsors')
    name = models.CharField(max_length=200)
    tier = models.CharField(max_length=20, choices=TIER_CHOICES, default='bronze')
    logo = models.ImageField(upload_to='sponsor_logos/', blank=True, null=True)
    website = models.URLField(blank=True)
    description = models.TextField(blank=True)
    booth_info = models.TextField(blank=True)

    class Meta:
        ordering = ['tier', 'name']

    def __str__(self):
        return f"{self.name} ({self.tier}) @ {self.event.title}"


class Announcement(models.Model):
    PRIORITY_CHOICES = [
        ('normal', 'Normal'),
        ('important', 'Important'),
        ('urgent', 'Urgent'),
    ]
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='announcements')
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=300)
    content = models.TextField()
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='normal')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.event.title} - {self.title}"


class Poll(models.Model):
    session = models.ForeignKey(EventSession, on_delete=models.CASCADE, related_name='polls')
    question = models.CharField(max_length=500)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.question

    def total_votes(self):
        return sum(c.vote_count() for c in self.choices.all())


class PollChoice(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=300)

    def __str__(self):
        return self.text

    def vote_count(self):
        return self.votes.count()

    def percentage(self):
        total = self.poll.total_votes()
        if total == 0:
            return 0
        return round((self.vote_count() / total) * 100)


class PollVote(models.Model):
    choice = models.ForeignKey(PollChoice, on_delete=models.CASCADE, related_name='votes')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    voted_at = models.DateTimeField(auto_now_add=True)


class QAQuestion(models.Model):
    session = models.ForeignKey(EventSession, on_delete=models.CASCADE, related_name='questions')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    question = models.TextField()
    is_answered = models.BooleanField(default=False)
    answer = models.TextField(blank=True)
    upvotes = models.ManyToManyField(User, related_name='upvoted_questions', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Q: {self.question[:50]}"

    def upvote_count(self):
        return self.upvotes.count()


class Payment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('khalti', 'Khalti'),
        ('esewa', 'eSewa'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    registration = models.OneToOneField(Registration, on_delete=models.CASCADE, related_name='payment', null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='khalti')
    pidx = models.CharField(max_length=255, unique=True, null=True, blank=True)  # Khalti-specific
    transaction_uuid = models.CharField(max_length=255, unique=True, null=True, blank=True)  # eSewa-specific
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    transaction_id = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payment {self.id} - {self.user.username} - {self.payment_method} - {self.status}"
