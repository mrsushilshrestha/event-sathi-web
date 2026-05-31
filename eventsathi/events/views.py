from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, Http404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import models
from django.db.models import Q, Count, F, Sum, Avg
from django.utils import timezone
from .utils import log_analytics
from .models import (Event, TicketTier, Registration, Speaker, EventSession,
                     Sponsor, Announcement, Poll, PollChoice, PollVote, QAQuestion, FavoriteSession, Category,
                     EventComment, EventLike, SavedEvent, OrganizerFollow, EventInterest, Notification)
from .forms import (EventForm, TicketTierForm, SpeakerForm, SessionForm,
                    SponsorForm, AnnouncementForm, QAQuestionForm, PollForm, CheckInForm)


def home(request):
    now = timezone.now()
    live_events = Event.objects.filter(
        status='ongoing'
    ) | Event.objects.filter(
        status='published', start_date__lte=now, end_date__gte=now
    )
    live_events = live_events.distinct().order_by('end_date')[:4]

    upcoming_events = Event.objects.filter(
        status='published', start_date__gt=now
    ).order_by('start_date')[:8]

    past_events = Event.objects.filter(
        status__in=['completed']
    ).order_by('-end_date')[:4]

    total_events = Event.objects.filter(status__in=['published', 'ongoing', 'completed']).count()
    total_registrations = Registration.objects.filter(status='confirmed').count()
    return render(request, 'events/home.html', {
        'live_events': live_events,
        'upcoming_events': upcoming_events,
        'past_events': past_events,
        'total_events': total_events,
        'total_registrations': total_registrations,
        'has_events': live_events.exists() or upcoming_events.exists() or past_events.exists(),
    })


def event_list(request):
    events = Event.objects.filter(status__in=['published', 'ongoing', 'completed'])
    query = request.GET.get('q', '')
    category = request.GET.get('category', '')
    mode = request.GET.get('mode', '')
    status_filter = request.GET.get('status', '')

    if query:
        events = events.filter(Q(title__icontains=query) | Q(description__icontains=query) | Q(city__icontains=query) | Q(tags__icontains=query))
    if category:
        if category.isdigit():
            events = events.filter(category_id=int(category))
        else:
            events = events.filter(category__slug=category)
    if mode == 'virtual':
        events = events.filter(is_virtual=True)
    elif mode == 'in-person':
        events = events.filter(is_virtual=False)
    if status_filter:
        events = events.filter(status=status_filter)

    # Browser cookie-based Geolocation proximity sorting
    lat = request.COOKIES.get('user_lat') or request.GET.get('lat')
    lng = request.COOKIES.get('user_lng') or request.GET.get('lng')
    is_sorted_by_proximity = False

    if lat and lng:
        try:
            user_lat = float(lat)
            user_lng = float(lng)
            
            # Retrieve all matching events as list to calculate distance in memory
            events_list = list(events)
            for e in events_list:
                if e.latitude is not None and e.longitude is not None:
                    # Simple Euclidean distance squared
                    e.distance = (float(e.latitude) - user_lat) ** 2 + (float(e.longitude) - user_lng) ** 2
                else:
                    e.distance = 999999.0
            
            events_list.sort(key=lambda x: x.distance)
            events = events_list
            is_sorted_by_proximity = True
        except ValueError:
            events = events.order_by('-start_date')
    else:
        events = events.order_by('-start_date')

    return render(request, 'events/event_list.html', {
        'events': events,
        'query': query,
        'category': category,
        'categories': Category.objects.all(),
        'mode': mode,
        'is_sorted_by_proximity': is_sorted_by_proximity,
    })




def event_detail(request, slug):
    event = get_object_or_404(Event, slug=slug)
    # Track views
    Event.objects.filter(pk=event.pk).update(views=F('views') + 1)
    event.refresh_from_db()
    is_registered = False
    registration = None
    if request.user.is_authenticated:
        try:
            registration = Registration.objects.get(user=request.user, event=event)
            is_registered = True
        except Registration.DoesNotExist:
            pass
    tiers = event.ticket_tiers.filter(is_active=True)
    speakers = event.speakers.all()[:6]
    sponsors = event.sponsors.all()
    announcements = event.announcements.all()[:5]
    sessions = event.sessions.all()[:5]
    return render(request, 'events/event_detail.html', {
        'event': event,
        'is_registered': is_registered,
        'registration': registration,
        'tiers': tiers,
        'speakers': speakers,
        'sponsors': sponsors,
        'announcements': announcements,
        'sessions': sessions,
    })


@login_required
def event_register(request, slug):
    event = get_object_or_404(Event, slug=slug, status__in=['published', 'ongoing'])
    if Registration.objects.filter(user=request.user, event=event).exists():
        messages.warning(request, 'You are already registered for this event.')
        return redirect('event_detail', slug=slug)
    if not event.is_registration_open():
        messages.error(request, 'Registration is closed for this event.')
        return redirect('event_detail', slug=slug)
    tiers = event.ticket_tiers.filter(is_active=True)
    if request.method == 'POST':
        tier_id = request.POST.get('tier_id')
        tier = get_object_or_404(TicketTier, id=tier_id, event=event)
        if tier.get_available() <= 0:
            messages.error(request, 'Sorry, this ticket tier is sold out.')
            return redirect('event_register', slug=slug)
        
        # Route to simulated payment checkout for paid ticket tiers
        if tier.price > 0:
            return redirect(f'/events/{slug}/checkout/?tier_id={tier.id}')

        registration = Registration.objects.create(
            user=request.user,
            event=event,
            ticket_tier=tier,
            status='confirmed',
            amount_paid=tier.price,
        )
        messages.success(request, f'Successfully registered! Your ticket ID: {registration.ticket_id}')
        return redirect('view_ticket', ticket_id=registration.ticket_id)
    return render(request, 'events/event_register.html', {'event': event, 'tiers': tiers})


@login_required
def event_create(request):
    profile = getattr(request.user, 'profile', None)
    if profile and profile.role not in ['organizer', 'speaker'] and not request.user.is_staff:
        messages.error(request, 'Only organizers can create events.')
        return redirect('home')
    form = EventForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        try:
            event = form.save(commit=False)
            event.organizer = request.user
            event.status = 'published'
            event.save()
            
            # Create a default ticket tier if none exists
            TicketTier.objects.create(
                event=event, 
                name='General Admission', 
                price=0, 
                capacity=event.max_capacity,
                description='Regular entry to the event.'
            )
            
            # Log the analytics
            log_analytics(request, event, 'created')
            
            messages.success(request, 'Event published successfully! You can now add more ticket tiers, speakers, and sessions.')
            return redirect('event_manage', slug=event.slug)
        except Exception as e:
            messages.error(request, f'An error occurred while saving the event: {str(e)}')
    
    if form.errors:
        messages.error(request, 'Please correct the errors below.')
    return render(request, 'events/event_form.html', {'form': form, 'action': 'Post Event'})


@login_required
def event_edit(request, slug):
    event = get_object_or_404(Event, slug=slug, organizer=request.user)
    form = EventForm(request.POST or None, request.FILES or None, instance=event)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Event details updated successfully!')
        return redirect('event_manage', slug=event.slug)
    return render(request, 'events/event_form.html', {'form': form, 'action': 'Update Event', 'event': event})


@login_required
def event_duplicate(request, slug):
    original = get_object_or_404(Event, slug=slug, organizer=request.user)
    new_event = Event.objects.get(id=original.id)
    new_event.pk = None
    new_event.title = f"Copy of {original.title}"
    new_event.slug = f"{original.slug}-copy-{random.randint(100, 999)}"
    new_event.status = 'draft'
    new_event.created_at = timezone.now()
    new_event.save()
    
    # Duplicate tiers
    for tier in original.ticket_tiers.all():
        tier.pk = None
        tier.event = new_event
        tier.save()
    
    messages.success(request, f"Event '{original.title}' duplicated as draft.")
    return redirect('event_manage', slug=new_event.slug)


@login_required
def event_status_change(request, slug):
    event = get_object_or_404(Event, slug=slug, organizer=request.user)
    new_status = request.POST.get('status')
    if new_status in dict(Event.STATUS_CHOICES):
        event.status = new_status
        event.save()
        messages.success(request, f"Event status changed to {event.get_status_display()}.")
    return redirect('event_manage', slug=event.slug)


@login_required
def manage_attendees(request, slug):
    event = get_object_or_404(Event, slug=slug, organizer=request.user)
    query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    
    attendees = event.registrations.all().select_related('user', 'ticket_tier')
    
    if query:
        attendees = attendees.filter(
            Q(user__username__icontains=query) | 
            Q(user__first_name__icontains=query) | 
            Q(user__last_name__icontains=query) | 
            Q(ticket_id__icontains=query)
        )
    
    if status_filter:
        attendees = attendees.filter(status=status_filter)
        
    return render(request, 'events/manage/attendees.html', {
        'event': event,
        'attendees': attendees,
        'q': query,
        'status_filter': status_filter
    })


@login_required
def export_attendees(request, slug):
    import csv
    from django.http import HttpResponse
    event = get_object_or_404(Event, slug=slug, organizer=request.user)
    attendees = event.registrations.all().select_related('user', 'ticket_tier')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{event.slug}_attendees.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Ticket ID', 'Name', 'Email', 'Tier', 'Status', 'Registered At', 'Checked In At'])
    
    for reg in attendees:
        writer.writerow([
            reg.ticket_id,
            reg.user.get_full_name() or reg.user.username,
            reg.user.email,
            reg.ticket_tier.name,
            reg.get_status_display(),
            reg.registered_at,
            reg.checked_in_at or 'N/A'
        ])
    
    return response


@login_required
def manage_comments(request, slug):
    event = get_object_or_404(Event, slug=slug, organizer=request.user)
    from events.models import EventComment
    comments = EventComment.objects.filter(event=event).order_by('-created_at')
    
    if request.method == 'POST':
        comment_id = request.POST.get('comment_id')
        action = request.POST.get('action')
        comment = get_object_or_404(EventComment, id=comment_id, event=event)
        
        if action == 'delete':
            comment.delete()
            messages.success(request, "Comment deleted.")
        elif action == 'reply':
            content = request.POST.get('content')
            if content:
                EventComment.objects.create(
                    event=event,
                    user=request.user,
                    parent=comment,
                    content=content
                )
                messages.success(request, "Reply posted.")
        return redirect('manage_comments', slug=slug)
        
    return render(request, 'events/manage/comments.html', {'event': event, 'comments': comments})


@login_required
def event_manage(request, slug):
    event = get_object_or_404(Event, slug=slug, organizer=request.user)
    registrations = event.registrations.filter(status='confirmed')
    checked_in = event.registrations.filter(status='checked_in').count()
    return render(request, 'events/manage/dashboard.html', {
        'event': event,
        'registrations': registrations,
        'checked_in': checked_in,
        'reg_count': registrations.count(),
        'total_revenue': sum(r.amount_paid for r in registrations),
    })


@login_required
def manage_tickets(request, slug):
    event = get_object_or_404(Event, slug=slug, organizer=request.user)
    form = TicketTierForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        tier = form.save(commit=False)
        tier.event = event
        tier.save()
        messages.success(request, 'Ticket tier added!')
        return redirect('manage_tickets', slug=slug)
    tiers = event.ticket_tiers.all()
    return render(request, 'events/manage/tickets.html', {'event': event, 'form': form, 'tiers': tiers})


@login_required
def manage_speakers(request, slug):
    event = get_object_or_404(Event, slug=slug, organizer=request.user)
    form = SpeakerForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        speaker = form.save(commit=False)
        speaker.event = event
        speaker.save()
        messages.success(request, 'Speaker added!')
        return redirect('manage_speakers', slug=slug)
    speakers = event.speakers.all()
    return render(request, 'events/manage/speakers.html', {'event': event, 'form': form, 'speakers': speakers})


@login_required
def manage_sessions(request, slug):
    event = get_object_or_404(Event, slug=slug, organizer=request.user)
    form = SessionForm(request.POST or None, event=event)
    if request.method == 'POST' and form.is_valid():
        session = form.save(commit=False)
        session.event = event
        session.save()
        messages.success(request, 'Session added!')
        return redirect('manage_sessions', slug=slug)
    sessions = event.sessions.all()
    return render(request, 'events/manage/sessions.html', {'event': event, 'form': form, 'sessions': sessions})


@login_required
def manage_sponsors(request, slug):
    event = get_object_or_404(Event, slug=slug, organizer=request.user)
    form = SponsorForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        sponsor = form.save(commit=False)
        sponsor.event = event
        sponsor.save()
        messages.success(request, 'Sponsor added!')
        return redirect('manage_sponsors', slug=slug)
    sponsors = event.sponsors.all()
    return render(request, 'events/manage/sponsors.html', {'event': event, 'form': form, 'sponsors': sponsors})


@login_required
def manage_announcements(request, slug):
    event = get_object_or_404(Event, slug=slug, organizer=request.user)
    form = AnnouncementForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        ann = form.save(commit=False)
        ann.event = event
        ann.author = request.user
        ann.save()
        messages.success(request, 'Announcement posted!')
        return redirect('manage_announcements', slug=slug)
    announcements = event.announcements.all()
    return render(request, 'events/manage/announcements.html', {'event': event, 'form': form, 'announcements': announcements})


@login_required
def check_in_view(request, slug):
    event = get_object_or_404(Event, slug=slug, organizer=request.user)
    form = CheckInForm(request.POST or None)
    result = None
    if request.method == 'POST' and form.is_valid():
        ticket_id = form.cleaned_data['ticket_id'].strip()
        try:
            reg = Registration.objects.get(ticket_id=ticket_id, event=event)
            if reg.status == 'checked_in':
                result = {'status': 'already', 'registration': reg}
            elif reg.status == 'confirmed':
                reg.status = 'checked_in'
                reg.checked_in_at = timezone.now()
                reg.save()
                result = {'status': 'success', 'registration': reg}
            else:
                result = {'status': 'invalid', 'msg': 'Ticket is not confirmed.'}
        except Registration.DoesNotExist:
            result = {'status': 'not_found', 'msg': f'No ticket found with ID: {ticket_id}'}
    recent_checkins = event.registrations.filter(status='checked_in').order_by('-checked_in_at')[:10]
    return render(request, 'events/manage/checkin.html', {
        'event': event, 'form': form, 'result': result,
        'checked_in_count': event.registrations.filter(status='checked_in').count(),
        'total_registered': event.registrations.filter(status__in=['confirmed', 'checked_in']).count(),
        'recent_checkins': recent_checkins,
    })


@login_required
def event_analytics(request, slug):
    event = get_object_or_404(Event, slug=slug, organizer=request.user)
    
    # Core Metrics
    regs = event.registrations.filter(status__in=['confirmed', 'checked_in'])
    total_revenue = regs.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0
    checked_in_count = regs.filter(status='checked_in').count()
    turnout_rate = (checked_in_count / regs.count() * 100) if regs.count() > 0 else 0
    
    # Conversion Rate (Bookings / Views)
    conversion_rate = (regs.count() / event.views * 100) if event.views > 0 else 0
    
    # Ticket Tiers Breakdown
    tier_data = []
    for tier in event.ticket_tiers.all():
        tier_regs = tier.registrations.filter(status__in=['confirmed', 'checked_in'])
        sold = tier_regs.count()
        revenue = tier_regs.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0
        tier_data.append({
            'name': tier.name,
            'sold': sold,
            'capacity': tier.capacity,
            'revenue': revenue,
            'percent': (sold / tier.capacity * 100) if tier.capacity > 0 else 0
        })

    # Timeline Data (Last 30 Days)
    from django.db.models.functions import TruncDate
    daily_regs = (regs.annotate(date=TruncDate('registered_at'))
                  .values('date').annotate(count=Count('id')).order_by('date'))
    
    # Platform Distribution
    platform_data = list(event.analytics.values('platform').annotate(count=Count('id')))
    
    # Action Distribution
    action_data = list(event.analytics.values('action').annotate(count=Count('id')))

    return render(request, 'events/manage/analytics.html', {
        'event': event,
        'total_registered': regs.count(),
        'total_checked_in': checked_in_count,
        'total_revenue': total_revenue,
        'turnout_rate': round(turnout_rate, 1),
        'conversion_rate': round(conversion_rate, 1),
        'tier_data': tier_data,
        'daily_regs': list(daily_regs),
        'platform_data': platform_data,
        'action_data': action_data,
        'views': event.views,
        'likes': event.total_likes,
        'comments': event.comments.count(),
    })


def event_agenda(request, slug):
    event = get_object_or_404(Event, slug=slug)
    sessions = event.sessions.all().order_by('start_time')
    favorite_ids = set()
    if request.user.is_authenticated:
        favorite_ids = set(FavoriteSession.objects.filter(user=request.user, session__event=event).values_list('session_id', flat=True))
    if request.method == 'POST' and request.user.is_authenticated:
        session_id = request.POST.get('toggle_favorite')
        if session_id:
            session = get_object_or_404(EventSession, id=session_id, event=event)
            fav, created = FavoriteSession.objects.get_or_create(user=request.user, session=session)
            if not created:
                fav.delete()
            return redirect('event_agenda', slug=slug)
    tracks = sessions.values_list('track', flat=True).distinct()
    return render(request, 'events/event_agenda.html', {
        'event': event, 'sessions': sessions, 'favorite_ids': favorite_ids, 'tracks': tracks
    })


def event_speakers(request, slug):
    event = get_object_or_404(Event, slug=slug)
    speakers = event.speakers.all()
    return render(request, 'events/event_speakers.html', {'event': event, 'speakers': speakers})


def event_sponsors(request, slug):
    event = get_object_or_404(Event, slug=slug)
    sponsors = event.sponsors.all().order_by('tier')
    return render(request, 'events/event_sponsors.html', {'event': event, 'sponsors': sponsors})


def event_announcements(request, slug):
    event = get_object_or_404(Event, slug=slug)
    announcements = event.announcements.all()
    return render(request, 'events/event_announcements.html', {'event': event, 'announcements': announcements})


@login_required
def session_detail(request, slug, session_id):
    event = get_object_or_404(Event, slug=slug)
    session = get_object_or_404(EventSession, id=session_id, event=event)
    is_organizer = event.organizer == request.user

    qa_form = QAQuestionForm(request.POST if request.method == 'POST' and 'question' in request.POST else None)
    poll_form = PollForm(request.POST if request.method == 'POST' and 'poll_question' in request.POST else None)

    if request.method == 'POST':
        if 'question' in request.POST and qa_form.is_valid():
            q = qa_form.save(commit=False)
            q.session = session
            q.user = request.user
            q.save()
            messages.success(request, 'Question submitted!')
            return redirect('session_detail', slug=slug, session_id=session_id)
        elif 'poll_question' in request.POST and is_organizer:
            pform = PollForm(request.POST)
            if pform.is_valid():
                poll = Poll.objects.create(session=session, question=pform.cleaned_data['question'])
                for i in range(1, 5):
                    choice_text = pform.cleaned_data.get(f'choice_{i}')
                    if choice_text:
                        PollChoice.objects.create(poll=poll, text=choice_text)
                messages.success(request, 'Poll created!')
                return redirect('session_detail', slug=slug, session_id=session_id)

    questions = session.questions.all().order_by('-created_at')
    polls = session.polls.filter(is_active=True).prefetch_related('choices__votes')
    user_votes = set()
    if request.user.is_authenticated:
        user_votes = set(PollVote.objects.filter(user=request.user, choice__poll__session=session).values_list('choice__poll_id', flat=True))

    return render(request, 'events/session_detail.html', {
        'event': event, 'session': session, 'is_organizer': is_organizer,
        'questions': questions, 'qa_form': qa_form,
        'polls': polls, 'poll_form': poll_form, 'user_votes': user_votes,
    })


@login_required
def upvote_question(request, slug, session_id, question_id):
    question = get_object_or_404(QAQuestion, id=question_id, session__event__slug=slug)
    if request.user in question.upvotes.all():
        question.upvotes.remove(request.user)
    else:
        question.upvotes.add(request.user)
    return redirect('session_detail', slug=slug, session_id=session_id)


@login_required
def vote_poll(request, slug, session_id, poll_id):
    poll = get_object_or_404(Poll, id=poll_id, session__event__slug=slug, is_active=True)
    if request.method == 'POST':
        choice_id = request.POST.get('choice_id')
        if choice_id:
            choice = get_object_or_404(PollChoice, id=choice_id, poll=poll)
            if not PollVote.objects.filter(user=request.user, choice__poll=poll).exists():
                PollVote.objects.create(choice=choice, user=request.user)
                messages.success(request, 'Vote recorded!')
            else:
                messages.warning(request, 'You have already voted on this poll.')
    return redirect('session_detail', slug=slug, session_id=session_id)


@login_required
def view_ticket(request, ticket_id):
    # Try finding by the alphanumeric ticket_id first (production standard)
    registration = Registration.objects.filter(ticket_id=ticket_id).first()
    
    # Fallback to looking by internal integer primary key if ticket_id is numeric 
    # and no alphanumeric match was found (helps during architectural transitions)
    if not registration and ticket_id.isdigit():
        registration = Registration.objects.filter(id=int(ticket_id)).first()
    
    if not registration:
        raise Http404("No Registration matches the given query.")

    # Security check: ensure the ticket belongs to the user, or they are the organizer/admin
    is_organizer = registration.event.organizer == request.user
    if registration.user != request.user and not is_organizer and not request.user.is_staff:
        messages.error(request, "You do not have permission to view this ticket.")
        return redirect('home')

    return render(request, 'events/ticket.html', {'registration': registration})


@login_required
def my_tickets(request):
    registrations = Registration.objects.filter(user=request.user).select_related('event', 'ticket_tier').order_by('-registered_at')
    return render(request, 'events/my_tickets.html', {'registrations': registrations})


@login_required
def my_events(request):
    organized = Event.objects.filter(organizer=request.user).order_by('-created_at')
    registered = Registration.objects.filter(user=request.user).select_related('event', 'ticket_tier').order_by('-registered_at')
    profile = getattr(request.user, 'profile', None)
    is_organizer = profile and profile.role in ['organizer'] or request.user.is_staff
    
    # Dashboard metrics for organizers
    metrics = {}
    if is_organizer:
        now = timezone.now()
        metrics = {
            'total_events': organized.count(),
            'active_events': organized.filter(status='published', start_date__lte=now, end_date__gte=now).count(),
            'upcoming_events': organized.filter(start_date__gt=now).count(),
            'past_events': organized.filter(end_date__lt=now).count(),
            'total_attendees': Registration.objects.filter(event__organizer=request.user, status__in=['confirmed', 'checked_in']).count(),
            'total_revenue': Registration.objects.filter(event__organizer=request.user, status__in=['confirmed', 'checked_in']).aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0,
            'total_likes': organized.aggregate(Sum('total_likes'))['total_likes__sum'] or 0,
            'total_comments': EventComment.objects.filter(event__organizer=request.user).count(),
            'total_followers': request.user.organizer_followers.count()
        }
    
    return render(request, 'events/my_events.html', {
        'organized': organized,
        'registered': registered,
        'is_organizer': is_organizer,
        'metrics': metrics
    })


@login_required
def event_delete(request, slug):
    event = get_object_or_404(Event, slug=slug)
    # Check if the user is the organizer of the event or an admin
    if event.organizer != request.user and not request.user.is_staff:
        messages.error(request, "You do not have permission to delete this event.")
        return redirect('event_detail', slug=slug)

    if request.method == 'POST':
        password = request.POST.get('password')
        if not password:
            messages.error(request, "Password is required to delete the event.")
        elif request.user.check_password(password):
            event_title = event.title
            event.delete()
            messages.success(request, f"Event '{event_title}' was successfully deleted.")
            return redirect('my_events')
        else:
            messages.error(request, "Incorrect password. Event deletion cancelled for safety.")

    return render(request, 'events/manage/delete.html', {'event': event})


# ─── AJAX Comments Endpoints (session-auth, for web templates) ───

def ajax_event_comments(request, event_id):
    """Return JSON list of comments for an event. Used by the comment drawer."""
    event = get_object_or_404(Event, id=event_id)
    from events.models import EventComment
    comments = EventComment.objects.filter(event=event).select_related('user', 'user__profile').order_by('-created_at')[:50]

    comments_data = []
    for c in comments:
        photo_url = ''
        if hasattr(c.user, 'profile') and c.user.profile.photo:
            photo_url = c.user.profile.photo.url
        comments_data.append({
            'id': c.id,
            'username': c.user.get_full_name() or c.user.username,
            'initials': (c.user.first_name[:1] + c.user.last_name[:1]).upper() if c.user.first_name else c.user.username[:2].upper(),
            'photo': photo_url,
            'content': c.content,
            'created_at': c.created_at.isoformat(),
            'time_ago': f'{c.created_at}',
        })

    return JsonResponse({
        'status': 'success',
        'comments': comments_data,
        'count': event.comments.count(),
    })


@login_required
def ajax_post_comment(request, event_id):
    """Post a new comment on an event via AJAX. Returns updated comment list."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required.'}, status=405)

    event = get_object_or_404(Event, id=event_id)

    import json
    try:
        body = json.loads(request.body)
        content = body.get('content', '').strip()
    except (json.JSONDecodeError, AttributeError):
        content = request.POST.get('content', '').strip()

    if not content:
        return JsonResponse({'status': 'error', 'message': 'Comment cannot be empty.'}, status=400)

    from events.models import EventComment, Notification
    comment = EventComment.objects.create(event=event, user=request.user, content=content)

    # Create notification for the event organizer
    if event.organizer != request.user:
        Notification.objects.create(
            user=event.organizer,
            title="New Comment",
            content=f"{request.user.get_full_name() or request.user.username} commented on '{event.title}': \"{content[:60]}\"",
            notification_type="comment",
            related_id=event.id,
        )

    photo_url = ''
    if hasattr(request.user, 'profile') and request.user.profile.photo:
        photo_url = request.user.profile.photo.url

    return JsonResponse({
        'status': 'success',
        'message': 'Comment posted.',
        'comment': {
            'id': comment.id,
            'username': request.user.get_full_name() or request.user.username,
            'initials': (request.user.first_name[:1] + request.user.last_name[:1]).upper() if request.user.first_name else request.user.username[:2].upper(),
            'photo': photo_url,
            'content': comment.content,
            'created_at': comment.created_at.isoformat(),
        },
        'comments_count': event.comments.count(),
    })


# ─── AJAX Social Toggle Endpoints (session-auth, for web templates) ───

@login_required
def ajax_toggle_like(request, event_id):
    """Toggle like on event via AJAX (web session auth)."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required.'}, status=405)

    event = get_object_or_404(Event, id=event_id)
    from events.models import EventLike, Notification

    like, created = EventLike.objects.get_or_create(event=event, user=request.user)
    if not created:
        like.delete()
        liked = False
    else:
        liked = True
        if event.organizer != request.user:
            Notification.objects.create(
                user=event.organizer,
                title="New Like!",
                content=f"{request.user.get_full_name() or request.user.username} liked your event: '{event.title}'.",
                notification_type="like",
                related_id=event.id,
            )

    return JsonResponse({
        'status': 'success',
        'is_liked': liked,
        'likes_count': event.likes.count(),
    })


@login_required
def ajax_toggle_save(request, event_id):
    """Toggle bookmark/save on event via AJAX (web session auth)."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required.'}, status=405)

    event = get_object_or_404(Event, id=event_id)
    from events.models import SavedEvent

    saved, created = SavedEvent.objects.get_or_create(event=event, user=request.user)
    if not created:
        saved.delete()
        is_saved = False
        msg = 'Event removed from saved.'
    else:
        is_saved = True
        msg = 'Event saved!'

    return JsonResponse({
        'status': 'success',
        'is_saved': is_saved,
        'message': msg,
    })


@login_required
def ajax_toggle_interest(request, event_id):
    """Set interested / not-interested on event via AJAX (web session auth)."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required.'}, status=405)

    event = get_object_or_404(Event, id=event_id)
    from events.models import EventInterest

    import json
    try:
        body = json.loads(request.body)
        interest_type = body.get('interest', 'interested')
    except (json.JSONDecodeError, AttributeError):
        interest_type = request.POST.get('interest', 'interested')

    is_interested = interest_type == 'interested'

    obj, created = EventInterest.objects.get_or_create(
        event=event, user=request.user,
        defaults={'is_interested': is_interested}
    )
    if not created:
        if obj.is_interested == is_interested:
            obj.delete()
            msg = 'Interest removed.'
        else:
            obj.is_interested = is_interested
            obj.save()
            msg = 'Interest updated.'
    else:
        msg = 'Marked as interested!' if is_interested else 'Marked as not interested.'

    return JsonResponse({
        'status': 'success',
        'message': msg,
        'interested_count': event.interests.filter(is_interested=True).count(),
    })


@login_required
def ajax_toggle_follow(request, organizer_id):
    """Toggle follow/unfollow on organizer via AJAX (web session auth)."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required.'}, status=405)
    
    organizer = get_object_or_404(User, id=organizer_id)
    profile = getattr(organizer, 'profile', None)
    if not profile or profile.role != 'organizer':
        return JsonResponse({'status': 'error', 'message': 'User is not an organizer.'}, status=400)

    from events.models import OrganizerFollow, Notification
    follow, created = OrganizerFollow.objects.get_or_create(user=request.user, organizer=organizer)
    if not created:
        follow.delete()
        following = False
        msg = "Unfollowed organizer."
    else:
        following = True
        msg = "Followed organizer."
        Notification.objects.create(
            user=organizer,
            title="New Follower!",
            content=f"{request.user.get_full_name() or request.user.username} started following you.",
            notification_type="follow",
            related_id=request.user.id
        )

    return JsonResponse({
        'status': 'success',
        'message': msg,
        'is_following': following,
        'followers_count': organizer.organizer_followers.count()
    })


@login_required
def ajax_toggle_pin(request, event_id):
    """Toggle pin event on organizer feed via AJAX (web session auth)."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required.'}, status=405)

    event = get_object_or_404(Event, id=event_id)
    if event.organizer != request.user:
        return JsonResponse({'status': 'error', 'message': 'Permission denied.'}, status=403)

    event.is_pinned = not event.is_pinned
    event.save()
    msg = "Event pinned to top." if event.is_pinned else "Event unpinned."
    return JsonResponse({
        'status': 'success',
        'message': msg,
        'is_pinned': event.is_pinned
    })


@login_required
def ajax_send_message(request):
    """Send a direct message via AJAX (web session auth)."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required.'}, status=405)

    import json
    try:
        body = json.loads(request.body)
        receiver_id = body.get('receiver_id')
        content = body.get('content', '').strip()
    except (json.JSONDecodeError, AttributeError):
        receiver_id = request.POST.get('receiver_id')
        content = request.POST.get('content', '').strip()

    if not receiver_id or not content:
        return JsonResponse({'status': 'error', 'message': 'receiver_id and content are required.'}, status=400)

    receiver = get_object_or_404(User, id=receiver_id)
    from accounts.models import Message
    msg = Message.objects.create(
        sender=request.user,
        receiver=receiver,
        content=content
    )

    from events.models import Notification
    Notification.objects.create(
        user=receiver,
        title="New Message",
        content=f"{request.user.get_full_name() or request.user.username} sent you a message: \"{content[:50]}\"",
        notification_type="message",
        related_id=request.user.id
    )

    return JsonResponse({
        'status': 'success',
        'message': 'Message sent successfully!',
        'msg_id': msg.id
    })


@login_required
def ajax_get_messages(request, user_id):
    """Retrieve message history with a user via AJAX (web session auth)."""
    other_user = get_object_or_404(User, id=user_id)
    from accounts.models import Message
    from django.db.models import Q
    msgs = Message.objects.filter(
        Q(sender=request.user, receiver=other_user) | Q(sender=other_user, receiver=request.user)
    ).order_by('created_at')

    # Mark received as read
    msgs.filter(sender=other_user, receiver=request.user, is_read=False).update(is_read=True)

    messages_data = []
    for m in msgs:
        messages_data.append({
            'id': m.id,
            'sender_id': m.sender.id,
            'content': m.content,
            'time': m.created_at.strftime("%I:%M %p"),
            'is_mine': m.sender == request.user
        })

    return JsonResponse({
        'status': 'success',
        'messages': messages_data
    })


@login_required
def event_checkout(request, slug):
    """Simulated payment checkout portal for paid tickets."""
    event = get_object_or_404(Event, slug=slug)
    tier_id = request.GET.get('tier_id')
    from events.models import TicketTier, Registration
    tier = get_object_or_404(TicketTier, id=tier_id, event=event)
    
    if Registration.objects.filter(user=request.user, event=event).exists():
        messages.warning(request, 'You are already registered for this event.')
        return redirect('event_detail', slug=slug)

    return render(request, 'events/checkout.html', {
        'event': event,
        'tier': tier,
    })


@login_required
def ajax_confirm_checkout(request):
    """Create a confirmed registration after simulated checkout via AJAX (web session auth)."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required.'}, status=405)

    import json
    try:
        body = json.loads(request.body)
        tier_id = body.get('tier_id')
    except (json.JSONDecodeError, AttributeError):
        tier_id = request.POST.get('tier_id')

    if not tier_id:
        return JsonResponse({'status': 'error', 'message': 'tier_id is required.'}, status=400)

    from events.models import TicketTier, Registration, Notification
    tier = get_object_or_404(TicketTier, id=tier_id)
    event = tier.event

    if Registration.objects.filter(user=request.user, event=event).exists():
        return JsonResponse({'status': 'error', 'message': 'You are already registered for this event.'}, status=400)

    if tier.get_available() <= 0:
        return JsonResponse({'status': 'error', 'message': 'Sorry, this ticket tier is sold out.'}, status=400)

    registration = Registration.objects.create(
        user=request.user,
        event=event,
        ticket_tier=tier,
        status='confirmed',
        amount_paid=tier.price,
    )

    # Create notification
    Notification.objects.create(
        user=request.user,
        title="Ticket Booked!",
        content=f"Successfully registered for '{event.title}'. Your Ticket ID is {registration.ticket_id}.",
        notification_type="booking",
        related_id=event.id
    )

    return JsonResponse({
        'status': 'success',
        'message': 'Checkout completed!',
        'ticket_id': registration.ticket_id
    })




