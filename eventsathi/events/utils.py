import logging
from events.models import EventAnalytics

logger = logging.getLogger(__name__)

def log_analytics(request, event, action):
    try:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        platform = 'web'
        if 'Android' in user_agent:
            platform = 'android'
        elif 'iPhone' in user_agent or 'iPad' in user_agent:
            platform = 'ios'

        EventAnalytics.objects.create(
            event=event,
            user=request.user if request.user.is_authenticated else None,
            action=action,
            platform=platform,
            ip_address=ip,
            user_agent=user_agent
        )
    except Exception as e:
        logger.error(f"Analytics logging failed: {e}")
