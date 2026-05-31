from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    # Health Check
    path('health/', views.HealthCheckView.as_view(), name='api_health_check'),

    # Auth Endpoints
    path('auth/register/', views.RegisterView.as_view(), name='api_register'),
    path('auth/verify/', views.VerifyEmailView.as_view(), name='api_verify_email'),
    path('auth/resend/', views.ResendCodeView.as_view(), name='api_resend_code'),
    path('auth/login/', views.LoginView.as_view(), name='api_login'),
    path('auth/logout/', views.LogoutView.as_view(), name='api_logout'),
    path('auth/forgot-password/', views.ForgotPasswordView.as_view(), name='api_forgot_password'),
    path('auth/reset-password/', views.ResetPasswordView.as_view(), name='api_reset_password'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='api_token_refresh'),
    path('auth/profile/', views.UserProfileView.as_view(), name='api_profile'),
    path('auth/profile/avatar/', views.UserAvatarUploadView.as_view(), name='api_avatar_upload'),
    path('auth/upgrade/', views.OrganizerUpgradeView.as_view(), name='api_upgrade'),
    path('auth/switch-role/', views.SwitchRoleView.as_view(), name='api_switch_role'),
    path('auth/google/', views.GoogleLoginView.as_view(), name='api_google_login'),

    # Events Endpoints
    path('events/', views.EventListCreateView.as_view(), name='api_events'),
    path('events/create/', views.EventListCreateView.as_view(), name='api_event_create'),
    path('events/<int:pk>/', views.EventDetailUpdateDeleteView.as_view(), name='api_event_detail'),
    path('events/<int:pk>/update/', views.EventDetailUpdateDeleteView.as_view(), name='api_event_update'),
    path('events/<int:pk>/delete/', views.EventDetailUpdateDeleteView.as_view(), name='api_event_delete'),
    path('events/<int:pk>/banner/', views.EventBannerUploadView.as_view(), name='api_event_banner_upload'),
    path('events/<int:pk>/duplicate/', views.EventDuplicateView.as_view(), name='api_event_duplicate'),
    path('events/<int:pk>/track/', views.EventViewTrackView.as_view(), name='api_event_track'),
    path('events/<int:event_id>/like/', views.EventLikeToggleView.as_view(), name='api_event_like'),
    path('events/<int:event_id>/comments/', views.EventCommentsListView.as_view(), name='api_event_comments_list'),
    path('events/<int:event_id>/comment/', views.EventCommentCreateView.as_view(), name='api_event_comment'),
    path('comments/<int:comment_id>/reply/', views.CommentReplyView.as_view(), name='api_comment_reply'),
    path('events/organizer/', views.OrganizerEventsView.as_view(), name='api_organizer_events'),
    path('events/featured/', views.FeaturedEventsView.as_view(), name='api_featured_events'),
    path('events/nearby/', views.NearbyEventsView.as_view(), name='api_nearby_events'),
    path('events/reverse-geocode/', views.ReverseGeocodeView.as_view(), name='api_reverse_geocode'),
    path('events/category/<slug:category_slug>/', views.CategoryEventsView.as_view(), name='api_category_events'),
    path('categories/', views.EventCategoriesView.as_view(), name='api_categories'),
    path('search/', views.EventSearchView.as_view(), name='api_search'),
    
    # Saved events
    path('events/<int:event_id>/save/', views.EventSaveToggleView.as_view(), name='api_event_save'),
    path('events/saved/', views.SavedEventsListView.as_view(), name='api_saved_events'),
    
    # Organizer follows
    path('organizer/<int:organizer_id>/follow/', views.OrganizerFollowToggleView.as_view(), name='api_organizer_follow'),
    path('organizer/<int:organizer_id>/followers/', views.OrganizerFollowersListView.as_view(), name='api_organizer_followers'),
    path('organizer/followed/', views.FollowedOrganizersListView.as_view(), name='api_followed_organizers'),
    
    # Event interests
    path('events/<int:event_id>/interest/', views.EventInterestToggleView.as_view(), name='api_event_interest'),
    path('events/interested/', views.InterestedEventsListView.as_view(), name='api_interested_events'),
    
    # Pin event
    path('events/<int:event_id>/pin/', views.EventPinToggleView.as_view(), name='api_event_pin'),

    # Bookings/Tickets Endpoints
    path('bookings/', views.BookingListCreateView.as_view(), name='api_bookings'),
    path('book-ticket/', views.BookingListCreateView.as_view(), name='api_book_ticket'),
    path('my-bookings/', views.BookingListCreateView.as_view(), name='api_my_bookings'),
    path('bookings/verify/', views.VerifyTicketView.as_view(), name='api_bookings_verify'),
    path('tickets/', views.TicketsListView.as_view(), name='api_tickets'),
    path('ticket/<int:pk>/qr/', views.TicketQRView.as_view(), name='api_ticket_qr'),

    # Organizer Endpoints
    path('organizer/dashboard/', views.OrganizerDashboardAnalyticsView.as_view(), name='api_organizer_dashboard'),
    path('organizer/events/', views.OrganizerEventsView.as_view(), name='api_organizer_dashboard_events'),
    path('organizer/analytics/', views.OrganizerAnalyticsView.as_view(), name='api_organizer_analytics'),
    path('organizer/events/<int:pk>/export-attendees/', views.OrganizerExportAttendeesView.as_view(), name='api_organizer_export_attendees'),
    path('organizer/events/<int:pk>/export-revenue/', views.OrganizerExportRevenueView.as_view(), name='api_organizer_export_revenue'),

    # Direct messaging
    path('messages/conversations/', views.ConversationsListView.as_view(), name='api_conversations'),
    path('messages/<int:user_id>/', views.UserMessagesView.as_view(), name='api_user_messages'),
    path('messages/send/', views.SendMessageView.as_view(), name='api_send_message'),

    # Notifications Endpoints
    path('notifications/', views.NotificationsListView.as_view(), name='api_notifications'),
    path('unread-counts/', views.GlobalUnreadCountView.as_view(), name='api_unread_counts'),
    path('notifications/<int:pk>/read/', views.NotificationReadView.as_view(), name='api_notification_read'),
    path('notifications/read-all/', views.NotificationReadAllView.as_view(), name='api_notifications_read_all'),

    # Admin Endpoints
    path('admin/users/', views.AdminUsersListView.as_view(), name='api_admin_users'),
    path('admin/events/', views.AdminEventsListView.as_view(), name='api_admin_events'),
    path('admin/payments/', views.AdminPaymentsView.as_view(), name='api_admin_payments'),
]
