from .models import NetworkConnection

def pending_connection_count(request):
    if request.user.is_authenticated:
        count = NetworkConnection.objects.filter(to_user=request.user, status='pending').count()
        return {'pending_connection_count': count}
    return {'pending_connection_count': 0}
