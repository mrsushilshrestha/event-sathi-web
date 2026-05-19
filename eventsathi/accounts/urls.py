from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.profile_edit_view, name='profile_edit'),
    path('network/', views.network_hub, name='network_hub'),
    path('network/connect/<int:user_id>/', views.send_connection, name='send_connection'),
    path('network/accept/<int:connection_id>/', views.accept_connection, name='accept_connection'),
    path('network/reject/<int:connection_id>/', views.reject_connection, name='reject_connection'),
    path('messages/', views.messages_list, name='messages_list'),
    path('messages/<int:user_id>/', views.conversation, name='conversation'),
    path('attendees/', views.attendees_list, name='attendees_list'),
]
