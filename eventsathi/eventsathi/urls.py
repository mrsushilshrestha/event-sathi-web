from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from events import views as event_views
from accounts import views as account_views

urlpatterns = [
    # Custom Admin Portal
    path('adminlogin/', account_views.admin_login_view, name='admin_login'),
    path('adminlogin/dashboard/', account_views.admin_dashboard_view, name='admin_dashboard'),
    path('adminlogin/event/<slug:slug>/edit/', account_views.admin_event_edit_view, name='admin_event_edit'),
    path('adminlogin/event/<slug:slug>/delete/', account_views.admin_event_delete_view, name='admin_event_delete'),
    path('adminlogin/event/<slug:slug>/toggle-feature/', account_views.admin_event_toggle_feature, name='admin_event_toggle_feature'),
    path('adminlogin/event/<slug:slug>/change-status/', account_views.admin_event_change_status, name='admin_event_change_status'),
    path('adminlogin/organizer/<int:user_id>/toggle-verification/', account_views.admin_organizer_toggle_verification, name='admin_organizer_toggle_verification'),
    path('adminlogin/organizer/<int:user_id>/delete/', account_views.admin_organizer_delete, name='admin_organizer_delete'),

    # Original Django admin as fallback/secure utility
    path('sysadmin/', admin.site.urls),

    path('accounts/', include('accounts.urls')),
    path('', event_views.home, name='home'),
    path('events/', include('events.urls')),
    path('api/', include('api.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

