import qrcode
import io
import os
import base64
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    icon = models.CharField(max_length=50, blank=True, help_text="FontAwesome icon name")
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


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
    title = models.CharField(max_length=300, db_index=True)
    slug = models.SlugField(max_length=300, unique=True)
    description = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='events')
    banner = models.ImageField(upload_to='event_banners/', blank=True, null=True)
    start_date = models.DateTimeField(db_index=True)
    end_date = models.DateTimeField()
    registration_start = models.DateTimeField(blank=True, null=True)
    registration_end = models.DateTimeField(blank=True, null=True)
    venue = models.CharField(max_length=300)
    city = models.CharField(max_length=100, db_index=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_virtual = models.BooleanField(default=False)
    virtual_link = models.URLField(blank=True)
    
    # Advanced Virtual details
    meet_link = models.URLField(max_length=500, blank=True, null=True)
    zoom_link = models.URLField(max_length=500, blank=True, null=True)
    teams_link = models.URLField(max_length=500, blank=True, null=True)
    meeting_id = models.CharField(max_length=100, blank=True, null=True)
    meeting_password = models.CharField(max_length=100, blank=True, null=True)
    joining_instructions = models.TextField(blank=True, null=True)
    streaming_link = models.URLField(max_length=500, blank=True, null=True)
    
    max_capacity = models.PositiveIntegerField(default=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='published', db_index=True)
    is_featured = models.BooleanField(default=False, db_index=True)
    is_pinned = models.BooleanField(default=False)
    tags = models.CharField(max_length=500, blank=True)
    views = models.PositiveIntegerField(default=0)
    total_likes = models.PositiveIntegerField(default=0)
    total_bookings = models.PositiveIntegerField(default=0)
    popularity_score = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['status', 'start_date']),
        ]

    def __str__(self):
        return self.title

    def get_registered_count(self):
        return self.registrations.filter(status__in=['confirmed', 'checked_in']).count()

    def get_available_seats(self):
        return self.max_capacity - self.get_registered_count()

    def is_registration_open(self):
        return self.status == 'published' and self.start_date > timezone.now()

    def get_tags_list(self):
        if self.tags:
            return [t.strip() for t in self.tags.split(',') if t.strip()]
        return []

    def get_min_price(self):
        tiers = self.ticket_tiers.filter(is_active=True)
        if not tiers.exists():
            return None
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
    updated_at = models.DateTimeField(auto_now=True)
    checked_in_at = models.DateTimeField(null=True, blank=True)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    class Meta:
        ordering = ['-registered_at']
        unique_together = ('user', 'event')
        indexes = [
            models.Index(fields=['status', 'registered_at']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.event.title}"

    def generate_qr_code(self):
        import hashlib
        from django.conf import settings
        secret_key = settings.SECRET_KEY
        token = hashlib.sha256(f"{self.ticket_id}{secret_key}".encode()).hexdigest()[:8]
        data = f"EVENTSATHI:{self.ticket_id}:{self.user.id}:{self.event.id}:{token}"

        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white').convert('RGB')

        # Draw central branded text
        from PIL import ImageDraw, ImageFont
        draw = ImageDraw.Draw(img)
        width, height = img.size

        # Center box size
        box_width, box_height = 110, 35
        x0 = (width - box_width) // 2
        y0 = (height - box_height) // 2
        x1 = x0 + box_width
        y1 = y0 + box_height

        # White background rectangle with dark teal border
        draw.rectangle([x0, y0, x1, y1], fill='white', outline='#0F766E', width=2)

        # Try to use a nice font, or fallback to default
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None

        # Draw text "Event Sathi"
        text = "Event Sathi"
        # Center text inside the box
        draw.text((x0 + 20, y0 + 10), text, fill='#0F766E', font=font)

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


class EventLike(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('event', 'user')

    def __str__(self):
        return f"{self.user.username} liked {self.event.title}"


class EventComment(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    content = models.TextField()
    likes = models.ManyToManyField(User, related_name='liked_comments', blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['event', 'created_at']),
        ]

    def __str__(self):
        return f"Comment by {self.user.username} on {self.event.title}"


class SavedEvent(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_events')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='saved_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'event')

    def __str__(self):
        return f"{self.user.username} bookmarked {self.event.title}"


class OrganizerFollow(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='following_organizers')
    organizer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='organizer_followers')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'organizer')

    def __str__(self):
        return f"{self.user.username} follows {self.organizer.username}"


class EventInterest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='event_interests')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='interests')
    is_interested = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'event')

    def __str__(self):
        status = "interested" if self.is_interested else "not interested"
        return f"{self.user.username} is {status} in {self.event.title}"


class EventImage(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='event_images/')
    caption = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.event.title}"


class Payment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    registration = models.OneToOneField(Registration, on_delete=models.CASCADE, related_name='payment')
    transaction_id = models.CharField(max_length=100, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='NPR')
    payment_method = models.CharField(max_length=50) # e.g. Khalti, eSewa, Card
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payment {self.transaction_id} - {self.status}"


class EventAnalytics(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='analytics')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=50) # e.g. view, like, share, book_attempt
    platform = models.CharField(max_length=20, default='web') # web, android, ios
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['event', 'action', 'created_at']),
            models.Index(fields=['created_at']),
        ]


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications_list')
    title = models.CharField(max_length=255)
    content = models.TextField()
    notification_type = models.CharField(max_length=50) # e.g. booking, like, comment, follow, message, OTP, cancellation
    is_read = models.BooleanField(default=False)
    related_id = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read', 'created_at']),
        ]

    def __str__(self):
        return f"Notification for {self.user.username}: {self.title}"

