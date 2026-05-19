from django.contrib import admin
from .models import UserProfile, NetworkConnection, Message

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'organization', 'designation']
    list_filter = ['role']
    search_fields = ['user__username', 'user__email', 'organization']

@admin.register(NetworkConnection)
class NetworkConnectionAdmin(admin.ModelAdmin):
    list_display = ['from_user', 'to_user', 'status', 'created_at']
    list_filter = ['status']

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['sender', 'receiver', 'is_read', 'created_at']
