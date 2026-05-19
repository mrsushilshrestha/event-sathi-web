from django.contrib import admin
from .models import (Event, TicketTier, Registration, Speaker, EventSession,
                     Sponsor, Announcement, Poll, PollChoice, QAQuestion, FavoriteSession)


class TicketTierInline(admin.TabularInline):
    model = TicketTier
    extra = 1


class SpeakerInline(admin.TabularInline):
    model = Speaker
    extra = 1


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['title', 'organizer', 'category', 'status', 'start_date', 'city', 'is_featured']
    list_filter = ['status', 'category', 'is_virtual', 'is_featured']
    search_fields = ['title', 'description', 'city']
    prepopulated_fields = {'slug': ('title',)}
    inlines = [TicketTierInline]
    list_editable = ['status', 'is_featured']


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = ['ticket_id', 'user', 'event', 'ticket_tier', 'status', 'amount_paid', 'registered_at']
    list_filter = ['status']
    search_fields = ['ticket_id', 'user__username', 'event__title']


@admin.register(Speaker)
class SpeakerAdmin(admin.ModelAdmin):
    list_display = ['name', 'designation', 'organization', 'event']
    search_fields = ['name', 'organization']


@admin.register(EventSession)
class EventSessionAdmin(admin.ModelAdmin):
    list_display = ['title', 'event', 'track', 'speaker', 'start_time', 'end_time']
    list_filter = ['track']


@admin.register(Sponsor)
class SponsorAdmin(admin.ModelAdmin):
    list_display = ['name', 'tier', 'event']
    list_filter = ['tier']


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ['title', 'event', 'priority', 'created_at']
    list_filter = ['priority']


@admin.register(Poll)
class PollAdmin(admin.ModelAdmin):
    list_display = ['question', 'session', 'is_active']

admin.site.register(QAQuestion)
admin.site.register(FavoriteSession)
