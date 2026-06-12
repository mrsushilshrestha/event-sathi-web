from .models import FavoriteEvent, Event

def favorite_events(request):
    if request.user.is_authenticated:
        favs = set(FavoriteEvent.objects.filter(user=request.user).values_list('event_id', flat=True))
        return {'favorite_event_ids': favs}
    return {'favorite_event_ids': set()}

def search_context(request):
    return {
        'query': request.GET.get('q', ''),
        'category': request.GET.get('category', ''),
        'event_type': request.GET.get('type', ''),
        'categories': Event.CATEGORY_CHOICES,
    }
