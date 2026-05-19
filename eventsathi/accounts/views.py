from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Q
from .models import UserProfile, NetworkConnection, Message
from .forms import RegisterForm, LoginForm, ProfileUpdateForm, MessageForm


def register_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, f'Welcome to EventSathi, {user.first_name}!')
        return redirect('home')
    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        login(request, user)
        messages.success(request, f'Welcome back, {user.first_name or user.username}!')
        return redirect(request.GET.get('next', 'home'))
    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('home')


@login_required
def profile_view(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    from events.models import Registration
    registrations = Registration.objects.filter(user=request.user).select_related('event', 'ticket_tier').order_by('-registered_at')
    return render(request, 'accounts/profile.html', {
        'profile': profile,
        'registrations': registrations,
    })


@login_required
def profile_edit_view(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    form = ProfileUpdateForm(request.POST or None, request.FILES or None, instance=profile)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Profile updated successfully!')
        return redirect('profile')
    return render(request, 'accounts/profile_edit.html', {'form': form})


@login_required
def network_hub(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    my_interests = profile.get_interests_list()

    sent = NetworkConnection.objects.filter(from_user=request.user).values_list('to_user_id', flat=True)
    received_accepted = NetworkConnection.objects.filter(to_user=request.user, status='accepted').values_list('from_user_id', flat=True)
    connected_ids = list(set(list(sent) + list(received_accepted)))

    pending_requests = NetworkConnection.objects.filter(to_user=request.user, status='pending').select_related('from_user__profile')

    all_profiles = UserProfile.objects.exclude(user=request.user).select_related('user')
    suggestions = []
    for p in all_profiles:
        if p.user.id not in connected_ids:
            p_interests = p.get_interests_list()
            common = len(set(my_interests) & set(p_interests))
            suggestions.append((p, common))
    suggestions.sort(key=lambda x: x[1], reverse=True)

    my_connections = NetworkConnection.objects.filter(
        Q(from_user=request.user, status='accepted') | Q(to_user=request.user, status='accepted')
    ).select_related('from_user__profile', 'to_user__profile')

    return render(request, 'accounts/network.html', {
        'suggestions': suggestions[:20],
        'pending_requests': pending_requests,
        'my_connections': my_connections,
    })


@login_required
def send_connection(request, user_id):
    to_user = get_object_or_404(User, id=user_id)
    if to_user != request.user:
        NetworkConnection.objects.get_or_create(from_user=request.user, to_user=to_user)
        messages.success(request, f'Connection request sent to {to_user.get_full_name() or to_user.username}!')
    return redirect('network_hub')


@login_required
def accept_connection(request, connection_id):
    conn = get_object_or_404(NetworkConnection, id=connection_id, to_user=request.user)
    conn.status = 'accepted'
    conn.save()
    messages.success(request, f'You are now connected with {conn.from_user.get_full_name() or conn.from_user.username}!')
    return redirect('network_hub')


@login_required
def reject_connection(request, connection_id):
    conn = get_object_or_404(NetworkConnection, id=connection_id, to_user=request.user)
    conn.delete()
    return redirect('network_hub')


@login_required
def messages_list(request):
    conversations = Message.objects.filter(
        Q(sender=request.user) | Q(receiver=request.user)
    ).order_by('-created_at')

    seen_users = set()
    unique_convos = []
    for msg in conversations:
        other = msg.receiver if msg.sender == request.user else msg.sender
        if other.id not in seen_users:
            seen_users.add(other.id)
            unread = Message.objects.filter(sender=other, receiver=request.user, is_read=False).count()
            unique_convos.append({'user': other, 'last_message': msg, 'unread': unread})

    return render(request, 'accounts/messages_list.html', {'conversations': unique_convos})


@login_required
def conversation(request, user_id):
    other_user = get_object_or_404(User, id=user_id)
    form = MessageForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        Message.objects.create(
            sender=request.user,
            receiver=other_user,
            content=form.cleaned_data['content']
        )
        form = MessageForm()

    msgs = Message.objects.filter(
        Q(sender=request.user, receiver=other_user) | Q(sender=other_user, receiver=request.user)
    ).order_by('created_at')
    msgs.filter(sender=other_user, receiver=request.user).update(is_read=True)

    return render(request, 'accounts/conversation.html', {
        'other_user': other_user,
        'messages': msgs,
        'form': form,
    })


@login_required
def attendees_list(request):
    query = request.GET.get('q', '')
    profiles = UserProfile.objects.exclude(user=request.user).select_related('user')
    if query:
        profiles = profiles.filter(
            Q(user__first_name__icontains=query) | Q(user__last_name__icontains=query) |
            Q(organization__icontains=query) | Q(interests__icontains=query)
        )
    return render(request, 'accounts/attendees_list.html', {'profiles': profiles, 'query': query})
