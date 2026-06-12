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
    path('adminlogin/user/<int:user_id>/toggle-status/', account_views.admin_user_toggle_status, name='admin_user_toggle_status'),
    path('adminlogin/user/<int:user_id>/change-role/', account_views.admin_user_change_role, name='admin_user_change_role'),
    path('adminlogin/user/<int:user_id>/delete/', account_views.admin_user_delete, name='admin_user_delete'),
    path('adminlogin/user/<int:user_id>/reset-password/', account_views.admin_reset_user_password, name='admin_reset_user_password'),
    path('adminlogin/admin/add/', account_views.admin_add_admin, name='admin_add_admin'),
    path('adminlogin/user/add/', account_views.admin_add_user, name='admin_add_user'),
    path('adminlogin/organizer/add/', account_views.admin_add_organizer, name='admin_add_organizer'),

    # Payment Routes
    path('payment/esewa/success/', event_views.esewa_payment_success, name='esewa_payment_success'),
    path('payment/esewa/failure/', event_views.esewa_payment_failure, name='esewa_payment_failure'),

    # Original Django admin as fallback/secure utility
    path('sysadmin/', admin.site.urls),

    path('accounts/', include('accounts.urls')),
    path('', event_views.event_list, name='home'),
    path('events/', include('events.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

