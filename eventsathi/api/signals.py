from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import F
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from events.models import Event, EventLike, EventComment, Registration, Notification
from accounts.models import Message

@receiver(post_save, sender=Event)
def broadcast_event_update(sender, instance, created, **kwargs):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "events_feed",
        {
            "type": "event_update",
            "event_id": instance.id,
            "title": instance.title,
            "status": instance.status,
            "total_likes": instance.total_likes,
            "total_bookings": instance.total_bookings,
            "action": "created" if created else "updated"
        }
    )

@receiver(post_save, sender=EventLike)
def update_event_likes_on_save(sender, instance, created, **kwargs):
    if created:
        Event.objects.filter(id=instance.event.id).update(total_likes=F('total_likes') + 1)
        # Re-broadcast updated count
        event = Event.objects.get(id=instance.event.id)
        broadcast_event_update(Event, event, False)

@receiver(post_delete, sender=EventLike)
def update_event_likes_on_delete(sender, instance, **kwargs):
    Event.objects.filter(id=instance.event.id).update(total_likes=F('total_likes') - 1)
    # Re-broadcast updated count
    event = Event.objects.get(id=instance.event.id)
    broadcast_event_update(Event, event, False)

@receiver(post_delete, sender=Event)
def broadcast_event_delete(sender, instance, **kwargs):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "events_feed",
        {
            "type": "event_update",
            "event_id": instance.id,
            "action": "deleted"
        }
    )
    
    # Notify booked users
    registrations = Registration.objects.filter(event_id=instance.id)
    for reg in registrations:
        Notification.objects.create(
            user=reg.user,
            title="Event Cancelled",
            content=f"The event '{instance.title}' has been cancelled by the organizer.",
            notification_type="cancellation",
            related_id=instance.id
        )

@receiver(post_save, sender=EventComment)
def broadcast_comment_update(sender, instance, created, **kwargs):
    if created:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "events_feed",
            {
                "type": "event_update",
                "event_id": instance.event.id,
                "action": "comment_added",
                "comment": {
                    "id": instance.id,
                    "username": instance.user.username,
                    "content": instance.content,
                    "created_at": instance.created_at.isoformat()
                },
                "comments_count": instance.event.comments.count()
            }
        )

@receiver(post_save, sender=Registration)
def update_event_bookings(sender, instance, created, **kwargs):
    if created and instance.status in ['confirmed', 'checked_in']:
        Event.objects.filter(id=instance.event.id).update(total_bookings=F('total_bookings') + 1)
        event = Event.objects.get(id=instance.event.id)
        broadcast_event_update(Event, event, False)
        
        # Notify organizer of new booking
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"event_{instance.event.id}_attendance",
            {
                "type": "checkin_update", # Reuse same handler for simplicity or add booking_update
                "action": "booking",
                "registration": {
                    "id": instance.id,
                    "ticket_id": instance.ticket_id,
                    "attendee_name": instance.user.get_full_name() or instance.user.username,
                    "amount": float(instance.amount_paid),
                    "time": instance.registered_at.isoformat(),
                    "status": instance.status
                }
            }
        )
    
    # Broadcast check-in update to organizer dashboard
    if instance.status == 'checked_in':
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"event_{instance.event.id}_attendance",
            {
                "type": "checkin_update",
                "action": "checkin",
                "registration": {
                    "id": instance.id,
                    "ticket_id": instance.ticket_id,
                    "attendee_name": instance.user.get_full_name() or instance.user.username,
                    "checkin_time": instance.checked_in_at.isoformat() if instance.checked_in_at else None,
                    "status": instance.status
                }
            }
        )

@receiver(post_save, sender=Notification)
def broadcast_notification(sender, instance, created, **kwargs):
    if created:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{instance.user.id}_notifications",
            {
                "type": "send_notification",
                "notification": {
                    "id": instance.id,
                    "title": instance.title,
                    "content": instance.content,
                    "type": instance.notification_type,
                    "created_at": instance.created_at.isoformat()
                }
            }
        )

@receiver(post_save, sender=Message)
def broadcast_message(sender, instance, created, **kwargs):
    if created:
        channel_layer = get_channel_layer()
        # Notify receiver
        async_to_sync(channel_layer.group_send)(
            f"user_{instance.receiver.id}_chat",
            {
                "type": "chat_message",
                "message": {
                    "id": instance.id,
                    "sender_id": instance.sender.id,
                    "sender_name": instance.sender.username,
                    "content": instance.content,
                    "created_at": instance.created_at.isoformat()
                }
            }
        )
