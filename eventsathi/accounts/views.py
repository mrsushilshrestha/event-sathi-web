from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Q
from django.core.mail import send_mail
from django.conf import settings
import random
import logging

logger = logging.getLogger(__name__)

def send_eventsathi_email(subject, message, recipient_list):
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            recipient_list,
            fail_silently=False,
        )
    except Exception as e:
        logger.error(f"Failed to send email to {recipient_list} via SMTP: {e}")
        # Fallback to Console backend
        from django.core.mail.backends.console import EmailBackend as ConsoleBackend
        from django.core.mail import EmailMessage
        console_backend = ConsoleBackend()
        email = EmailMessage(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            recipient_list,
            connection=console_backend,
        )
        email.send()
        # Add a visual console print for developer ease
        print("\n" + "="*80)
        print(f"SMTP EMAIL FAILED: {e}")
        print(f"SEAMLESS FALLBACK TO CONSOLE EMAIL FOR {recipient_list}:")
        print(f"Subject: {subject}")
        print(f"Message: {message}")
        print("="*80 + "\n")


from .models import UserProfile, NetworkConnection, Message, EmailVerificationCode, PasswordResetCode
from .forms import RegisterForm, SetRegistrationPasswordForm, LoginForm, ProfileUpdateForm, MessageForm, ForgotPasswordForm, ForceChangePasswordForm


def register_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save(commit=False)
        user.is_active = False
        user.save()

        # Create Profile
        profile, created = UserProfile.objects.get_or_create(
            user=user,
            defaults={
                'role': form.cleaned_data['role'],
                'phone': form.cleaned_data['phone']
            }
        )
        if not created:
            profile.phone = form.cleaned_data['phone']
            profile.role = form.cleaned_data['role']
            profile.save()

        # Generate verification code
        code = f"{random.randint(100000, 999999)}"
        EmailVerificationCode.objects.create(user=user, code=code)

        # Send activation email
        send_eventsathi_email(
            'Verify your EventSathi Account',
            f'Hi {user.first_name},\n\nWelcome to EventSathi!\nYour email verification code is: {code}\n\nPlease enter this code on the verification page to activate your account.',
            [user.email],
        )

        messages.info(request, 'An activation code has been sent to your email. Please verify to continue.')
        return redirect('verify_email', user_id=user.id)
    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        login(request, user, backend='accounts.backends.EmailOrUsernameBackend')
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
    from events.models import Registration, FavoriteEvent
    registrations = Registration.objects.filter(user=request.user).select_related('event', 'ticket_tier').order_by('-registered_at')
    favorite_events = FavoriteEvent.objects.filter(user=request.user).select_related('event').order_by('-created_at')
    return render(request, 'accounts/profile.html', {
        'profile': profile,
        'registrations': registrations,
        'favorite_events': favorite_events,
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
    pending_ids = pending_requests.values_list('from_user_id', flat=True)

    all_profiles = UserProfile.objects.exclude(user=request.user).select_related('user')
    suggestions = []
    for p in all_profiles:
        if p.user.id not in connected_ids and p.user.id not in pending_ids:
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


def verify_email_view(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if user.is_active:
        messages.info(request, "Your account is already active. Please log in.")
        return redirect('login')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'resend':
            # Delete old codes
            EmailVerificationCode.objects.filter(user=user).delete()
            # Generate new code
            code = f"{random.randint(100000, 999999)}"
            EmailVerificationCode.objects.create(user=user, code=code)
            # Send code
            send_eventsathi_email(
                'Verify your EventSathi Account',
                f'Hi {user.first_name},\n\nYour new email verification code is: {code}\n\nPlease enter this code to activate your account.',
                [user.email],
            )
            messages.success(request, 'A new verification code has been sent to your email.')
            return redirect('verify_email', user_id=user.id)

        entered_code = request.POST.get('code', '').strip()
        code_obj = EmailVerificationCode.objects.filter(user=user, code=entered_code).first()
        if code_obj:
            # Delete verification codes
            EmailVerificationCode.objects.filter(user=user).delete()
            # Activate the account
            user.is_active = True
            user.save()
            # Auto login the user
            login(request, user, backend='accounts.backends.EmailOrUsernameBackend')
            messages.success(request, f'Welcome to EventSathi, {user.first_name}! Your account is fully active.')
            return redirect('home')
        else:
            messages.error(request, 'Invalid verification code. Please try again.')

    return render(request, 'accounts/verify.html', {'target_user': user})


def set_registration_password_view(request):
    user_id = request.session.get('verified_user_id')
    if not user_id:
        messages.error(request, "Please verify your email address to set your password.")
        return redirect('register')

    user = get_object_or_404(User, id=user_id)
    form = SetRegistrationPasswordForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        password = form.cleaned_data['password1']
        user.set_password(password)
        user.is_active = True
        user.save()

        # Clear secure session variable
        if 'verified_user_id' in request.session:
            del request.session['verified_user_id']

        # Auto login the user
        login(request, user, backend='accounts.backends.EmailOrUsernameBackend')
        messages.success(request, f'Welcome to EventSathi, {user.first_name}! Your account is fully active.')
        return redirect('home')

    return render(request, 'accounts/set_registration_password.html', {'form': form, 'target_user': user})


def forgot_password_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    form = ForgotPasswordForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email']
        user = User.objects.filter(email=email).first()
        if user:
            # Generate password reset OTP
            code = f"{random.randint(100000, 999999)}"
            # Delete old codes for this user
            PasswordResetCode.objects.filter(user=user).delete()
            PasswordResetCode.objects.create(user=user, code=code)

            # Send OTP
            send_eventsathi_email(
                'Your EventSathi Password Reset OTP',
                f'Hi {user.first_name or user.username},\n\nYou requested a password reset. Use the following OTP to reset your password:\n\nOTP: {code}\n\nThis code is valid for a short time.',
                [user.email],
            )
            messages.success(request, 'An OTP has been sent to your email address.')
            return redirect('reset_password_verify', user_id=user.id)
        else:
            messages.error(request, 'No account found with this email address.')

    return render(request, 'accounts/forgot_password.html', {'form': form})


def reset_password_verify_view(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'resend':
            # Delete old codes
            PasswordResetCode.objects.filter(user=user).delete()
            # Generate new code
            code = f"{random.randint(100000, 999999)}"
            PasswordResetCode.objects.create(user=user, code=code)
            # Send code
            send_eventsathi_email(
                'Your EventSathi Password Reset OTP',
                f'Hi {user.first_name or user.username},\n\nYour new password reset OTP is: {code}',
                [user.email],
            )
            messages.success(request, 'A new OTP has been sent to your email.')
            return redirect('reset_password_verify', user_id=user.id)

        entered_code = request.POST.get('code', '').strip()
        code_obj = PasswordResetCode.objects.filter(user=user, code=entered_code).first()
        if code_obj:
            # Store user_id in session for next step
            request.session['reset_user_id'] = user.id
            return redirect('reset_password_confirm')
        else:
            messages.error(request, 'Invalid OTP. Please try again.')

    return render(request, 'accounts/reset_password_verify.html', {'target_user': user})


def reset_password_confirm_view(request):
    user_id = request.session.get('reset_user_id')
    if not user_id:
        messages.error(request, 'Please start the password reset process again.')
        return redirect('forgot_password')

    user = get_object_or_404(User, id=user_id)
    form = ForceChangePasswordForm(user=user, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        # Clear session and reset codes
        if 'reset_user_id' in request.session:
            del request.session['reset_user_id']
        PasswordResetCode.objects.filter(user=user).delete()
        # Clear must_change_password flag
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.must_change_password = False
        profile.save()
        messages.success(request, 'Your password has been reset successfully. Please log in.')
        return redirect('login')

    return render(request, 'accounts/reset_password_confirm.html', {'form': form, 'target_user': user})


@login_required
def force_change_password_view(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if not profile.must_change_password:
        return redirect('home')

    form = ForceChangePasswordForm(user=request.user, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        profile.must_change_password = False
        profile.save()
        update_session_auth_hash(request, request.user)
        messages.success(request, 'Your password has been changed successfully. You now have full access.')
        return redirect('home')

    return render(request, 'accounts/force_change_password.html', {'form': form})


from django.contrib.auth.decorators import user_passes_test
from django.utils import timezone
from events.models import Event, Registration
from .forms import AdminLoginForm, AdminEventForm

def organizer_profile_view(request, username):
    organizer = get_object_or_404(User, username=username)
    profile, _ = UserProfile.objects.get_or_create(user=organizer)
    
    # Retrieve non-draft events
    now = timezone.now()
    all_events = Event.objects.filter(organizer=organizer).exclude(status='draft')
    upcoming_events = all_events.filter(end_date__gte=now).order_by('start_date')
    past_events = all_events.filter(end_date__lt=now).order_by('-start_date')
    
    return render(request, 'accounts/organizer_profile.html', {
        'organizer': organizer,
        'profile': profile,
        'upcoming_events': upcoming_events,
        'past_events': past_events,
    })


def admin_login_view(request):
    if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
        return redirect('admin_dashboard')
        
    form = AdminLoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        login(request, user, backend='accounts.backends.EmailOrUsernameBackend')
        messages.success(request, f'Admin session started. Welcome, {user.first_name or user.username}!')
        return redirect('admin_dashboard')
        
    return render(request, 'accounts/admin_login.html', {'form': form})


@user_passes_test(lambda u: u.is_authenticated and (u.is_staff or u.is_superuser), login_url='admin_login')
def admin_dashboard_view(request):
    q = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    active_tab = request.GET.get('tab', 'events').strip()
    
    events = Event.objects.all().select_related('organizer')
    if q:
        events = events.filter(
            Q(title__icontains=q) |
            Q(organizer__username__icontains=q) |
            Q(venue__icontains=q) |
            Q(city__icontains=q)
        )
    if status_filter:
        events = events.filter(status=status_filter)
        
    events = events.order_by('-created_at')

    # Fetch organizers list
    organizers = UserProfile.objects.filter(role='organizer').select_related('user')
    if q:
        organizers = organizers.filter(
            Q(user__username__icontains=q) |
            Q(user__first_name__icontains=q) |
            Q(user__last_name__icontains=q) |
            Q(user__email__icontains=q) |
            Q(organization__icontains=q) |
            Q(designation__icontains=q)
        )
    organizers = organizers.order_by('-created_at')

    # Fetch users list for new Users tab
    users = User.objects.all().prefetch_related('profile')
    if q:
        users = users.filter(
            Q(username__icontains=q) |
            Q(email__icontains=q) |
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q)
        )
    users = users.order_by('-date_joined')
    
    # Statistics/Metrics
    total_events = Event.objects.count()
    total_registrations = Registration.objects.filter(status__in=['confirmed', 'checked_in']).count()
    total_users = User.objects.count()
    
    # Advanced breakdowns
    total_organizers = UserProfile.objects.filter(role='organizer').count()
    total_speakers = UserProfile.objects.filter(role='speaker').count()
    total_attendees = UserProfile.objects.filter(role='attendee').count()
    total_admins = User.objects.filter(Q(is_staff=True) | Q(is_superuser=True)).count()
    admins = User.objects.filter(Q(is_staff=True) | Q(is_superuser=True)).prefetch_related('profile').order_by('-date_joined')

    role_choices = [
        ('attendee', 'Attendee'),
        ('organizer', 'Organizer'),
        ('speaker', 'Speaker'),
        ('admin', 'Admin')
    ]
    
    return render(request, 'accounts/admin_dashboard.html', {
        'events': events,
        'organizers': organizers,
        'users': users,
        'admins': admins,
        'total_events': total_events,
        'total_registrations': total_registrations,
        'total_users': total_users,
        'total_organizers': total_organizers,
        'total_speakers': total_speakers,
        'total_attendees': total_attendees,
        'total_admins': total_admins,
        'q': q,
        'status_filter': status_filter,
        'active_tab': active_tab,
        'role_choices': role_choices,
    })


@user_passes_test(lambda u: u.is_authenticated and (u.is_staff or u.is_superuser), login_url='admin_login')
def admin_organizer_toggle_verification(request, user_id):
    if request.method == 'POST':
        profile = get_object_or_404(UserProfile, user_id=user_id)
        profile.is_verified = not profile.is_verified
        profile.save()
        state = "verified" if profile.is_verified else "unverified"
        messages.success(request, f'Organizer "{profile.user.get_full_name() or profile.user.username}" is now {state}.')
    return redirect(f'/adminlogin/dashboard/?tab=organizers')


@user_passes_test(lambda u: u.is_authenticated and (u.is_staff or u.is_superuser), login_url='admin_login')
def admin_organizer_delete(request, user_id):
    organizer_user = get_object_or_404(User, id=user_id)
    profile = get_object_or_404(UserProfile, user_id=user_id)
    
    # Fetch events organized by this user
    events = Event.objects.filter(organizer=organizer_user)
    
    if request.method == 'POST':
        # Execute delete
        username = organizer_user.username
        organizer_user.delete()
        messages.success(request, f'Organizer account "{username}" and all of their events have been permanently deleted.')
        return redirect('/adminlogin/dashboard/?tab=organizers')
        
    return render(request, 'accounts/admin_organizer_delete.html', {
        'organizer': organizer_user,
        'profile': profile,
        'events': events,
    })


@user_passes_test(lambda u: u.is_authenticated and (u.is_staff or u.is_superuser), login_url='admin_login')
def admin_event_toggle_feature(request, slug):
    if request.method == 'POST':
        event = get_object_or_404(Event, slug=slug)
        event.is_featured = not event.is_featured
        event.save()
        state = "featured" if event.is_featured else "unfeatured"
        messages.success(request, f'Event "{event.title}" is now {state}.')
    return redirect('admin_dashboard')


@user_passes_test(lambda u: u.is_authenticated and (u.is_staff or u.is_superuser), login_url='admin_login')
def admin_event_change_status(request, slug):
    if request.method == 'POST':
        event = get_object_or_404(Event, slug=slug)
        new_status = request.POST.get('status', '').strip()
        if new_status in dict(Event.STATUS_CHOICES):
            event.status = new_status
            event.save()
            messages.success(request, f'Event status updated to {event.get_status_display()}.')
        else:
            messages.error(request, 'Invalid status choice.')
    return redirect('admin_dashboard')


@user_passes_test(lambda u: u.is_authenticated and (u.is_staff or u.is_superuser), login_url='admin_login')
def admin_event_edit_view(request, slug):
    event = get_object_or_404(Event, slug=slug)
    form = AdminEventForm(request.POST or None, request.FILES or None, instance=event)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Event details updated successfully!')
        return redirect('admin_dashboard')
        
    return render(request, 'accounts/admin_event_edit.html', {
        'form': form,
        'event': event,
    })


@user_passes_test(lambda u: u.is_authenticated and (u.is_staff or u.is_superuser), login_url='admin_login')
def admin_event_delete_view(request, slug):
    event = get_object_or_404(Event, slug=slug)
    if request.method == 'POST':
        title = event.title
        event.delete()
        messages.success(request, f'Event "{title}" has been permanently deleted from the platform.')
        return redirect('admin_dashboard')
        
    return render(request, 'accounts/admin_event_delete.html', {
        'event': event,
    })


@user_passes_test(lambda u: u.is_authenticated and (u.is_staff or u.is_superuser), login_url='admin_login')
def admin_user_toggle_status(request, user_id):
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)
        if user == request.user:
            messages.error(request, "You cannot deactivate your own administrative account.")
        else:
            user.is_active = not user.is_active
            user.save()
            status = "activated" if user.is_active else "deactivated"
            messages.success(request, f'User "{user.username}" has been successfully {status}.')
    return redirect('/adminlogin/dashboard/?tab=users')


@user_passes_test(lambda u: u.is_authenticated and (u.is_staff or u.is_superuser), login_url='admin_login')
def admin_user_change_role(request, user_id):
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)
        new_role = request.POST.get('role', '').strip()
        if new_role in ['attendee', 'organizer']:
            profile, _ = UserProfile.objects.get_or_create(user=user)
            is_demoting_self = (user == request.user and (user.is_staff or user.is_superuser))
            if is_demoting_self:
                messages.error(request, "For safety reasons, you cannot revoke your own Admin status.")
            else:
                user.is_staff = False
                user.is_superuser = False
                user.save()
                profile.role = new_role
                profile.save()
                messages.success(request, f'User "{user.username}" role updated to {new_role.title()}.')
        else:
            messages.error(request, 'Invalid role selected.')
    return redirect('/adminlogin/dashboard/?tab=users')


@user_passes_test(lambda u: u.is_authenticated and (u.is_staff or u.is_superuser), login_url='admin_login')
def admin_user_delete(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    if target_user == request.user:
        messages.error(request, "You cannot delete your own admin account.")
        return redirect('/adminlogin/dashboard/?tab=users')
    
    profile, _ = UserProfile.objects.get_or_create(user=target_user)
    organized_events = Event.objects.filter(organizer=target_user)
    registrations = Registration.objects.filter(user=target_user)
    
    if request.method == 'POST':
        username = target_user.username
        target_user.delete()
        messages.success(request, f'User account "{username}" has been permanently deleted from the platform.')
        return redirect('/adminlogin/dashboard/?tab=users')
        
    return render(request, 'accounts/admin_user_delete.html', {
        'target_user': target_user,
        'profile': profile,
        'events': organized_events,
        'registrations': registrations,
    })


@user_passes_test(lambda u: u.is_authenticated and (u.is_staff or u.is_superuser), login_url='admin_login')
def admin_add_user(request):
    error = None
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name  = request.POST.get('last_name', '').strip()
        email      = request.POST.get('email', '').strip().lower()
        password   = request.POST.get('password', '').strip()
        confirm_pw = request.POST.get('confirm_password', '').strip()
        phone      = request.POST.get('phone', '').strip()

        if not all([first_name, last_name, email, password, confirm_pw]):
            error = "All fields are required."
        elif password != confirm_pw:
            error = "Passwords do not match."
        elif len(password) < 8:
            error = "Password must be at least 8 characters."
        elif User.objects.filter(email__iexact=email).exists():
            error = f"An account with email '{email}' already exists."
        else:
            new_user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_active=True
            )
            # Create profile without auto-verification
            UserProfile.objects.get_or_create(user=new_user, defaults={'role': 'attendee', 'phone': phone})
            send_eventsathi_email(
                'Your EventSathi Attendee Account',
                f'Hi {first_name},\n\nA new attendee account has been created for you on EventSathi.\n\nLogin URL: /accounts/login/\nEmail: {email}\nPassword: {password}\n\n– EventSathi Admin',
                [email],
            )
            messages.success(request, f'User account for "{first_name} {last_name}" ({email}) created successfully.')
            return redirect('/adminlogin/dashboard/?tab=users')

    return render(request, 'accounts/admin_add_user.html', {'error': error})


@user_passes_test(lambda u: u.is_authenticated and (u.is_staff or u.is_superuser), login_url='admin_login')
def admin_add_organizer(request):
    error = None
    if request.method == 'POST':
        first_name   = request.POST.get('first_name', '').strip()
        last_name    = request.POST.get('last_name', '').strip()
        email        = request.POST.get('email', '').strip().lower()
        password     = request.POST.get('password', '').strip()
        confirm_pw   = request.POST.get('confirm_password', '').strip()
        phone        = request.POST.get('phone', '').strip()
        organization = request.POST.get('organization', '').strip()
        designation  = request.POST.get('designation', '').strip()

        if not all([first_name, last_name, email, password, confirm_pw]):
            error = "First name, last name, email, password, and confirm password are required."
        elif password != confirm_pw:
            error = "Passwords do not match."
        elif len(password) < 8:
            error = "Password must be at least 8 characters."
        elif User.objects.filter(email__iexact=email).exists():
            error = f"An account with email '{email}' already exists."
        else:
            new_organizer = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_active=True
            )
            # Create profile without auto-verification
            UserProfile.objects.get_or_create(
                user=new_organizer, 
                defaults={
                    'role': 'organizer', 
                    'phone': phone, 
                    'organization': organization, 
                    'designation': designation
                }
            )
            send_eventsathi_email(
                'Your EventSathi Organizer Account',
                f'Hi {first_name},\n\nA new organizer account has been created for you on EventSathi.\n\nLogin URL: /accounts/login/\nEmail: {email}\nPassword: {password}\n\n– EventSathi Admin',
                [email],
            )
            messages.success(request, f'Organizer account for "{first_name} {last_name}" ({email}) created successfully.')
            return redirect('/adminlogin/dashboard/?tab=organizers')

    return render(request, 'accounts/admin_add_organizer.html', {'error': error})


@user_passes_test(lambda u: u.is_authenticated and (u.is_staff or u.is_superuser), login_url='admin_login')
def admin_add_admin(request):
    error = None
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name  = request.POST.get('last_name', '').strip()
        email      = request.POST.get('email', '').strip().lower()
        password   = request.POST.get('password', '').strip()
        confirm_pw = request.POST.get('confirm_password', '').strip()

        if not all([first_name, last_name, email, password, confirm_pw]):
            error = "All fields are required."
        elif password != confirm_pw:
            error = "Passwords do not match."
        elif len(password) < 8:
            error = "Password must be at least 8 characters."
        elif User.objects.filter(email__iexact=email).exists():
            error = f"An account with email '{email}' already exists."
        else:
            new_admin = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_active=True,
                is_staff=True,
                is_superuser=True
            )
            UserProfile.objects.get_or_create(user=new_admin, defaults={'role': 'attendee', 'phone': ''})
            send_eventsathi_email(
                'Your EventSathi Admin Account',
                f'Hi {first_name},\n\nA new admin account has been created for you on EventSathi.\n\nLogin URL: /adminlogin/\nEmail: {email}\nPassword: {password}\n\nPlease change your password after first login.\n\n– EventSathi Admin',
                [email],
            )
            messages.success(request, f'Admin account for "{first_name} {last_name}" ({email}) created successfully.')
            return redirect('/adminlogin/dashboard/?tab=admins')

    return render(request, 'accounts/admin_add_admin.html', {'error': error})


@user_passes_test(lambda u: u.is_authenticated and (u.is_staff or u.is_superuser), login_url='admin_login')
def admin_reset_user_password(request, user_id):
    from django.utils.crypto import get_random_string
    target_user = get_object_or_404(User, id=user_id)
    # Generate temporary password
    temp_password = get_random_string(length=8)
    # Set password
    target_user.set_password(temp_password)
    target_user.save()
    # Send email
    send_eventsathi_email(
        'Your EventSathi Password Has Been Reset',
        f'Hi {target_user.first_name or target_user.username},\n\nYour EventSathi password has been reset by an administrator.\n\nTemporary Password: {temp_password}\n\nPlease change your password after logging in.\n\n– EventSathi Admin',
        [target_user.email],
    )
    messages.success(request, f'Password reset for {target_user.get_full_name or target_user.username} ({target_user.email}) — temporary password sent.')
    # Redirect back to appropriate tab
    if target_user.profile.role == 'organizer':
        return redirect('/adminlogin/dashboard/?tab=organizers')
    else:
        return redirect('/adminlogin/dashboard/?tab=users')
