from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count
from django.utils import timezone
from django.http import JsonResponse
from .models import (Event, TicketTier, Registration, Speaker, EventSession,
                     Sponsor, Announcement, Poll, PollChoice, PollVote, QAQuestion, FavoriteSession)
from .forms import (EventForm, TicketTierForm, SpeakerForm, SessionForm,
                    SponsorForm, AnnouncementForm, QAQuestionForm, PollForm, CheckInForm)


def home(request):
    featured_events = Event.objects.filter(status='published', is_featured=True).order_by('-start_date')[:3]
    upcoming_events = Event.objects.filter(status='published', start_date__gte=timezone.now()).order_by('start_date')[:6]
    past_events = Event.objects.filter(status='completed').order_by('-start_date')[:3]
    categories = Event.CATEGORY_CHOICES
    total_events = Event.objects.filter(status__in=['published', 'completed']).count()
    total_registrations = Registration.objects.filter(status='confirmed').count()
    return render(request, 'events/home.html', {
        'featured_events': featured_events,
        'upcoming_events': upcoming_events,
        'past_events': past_events,
        'categories': categories,
        'total_events': total_events,
        'total_registrations': total_registrations,
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
        events = events.filter(category=category)
    if mode == 'virtual':
        events = events.filter(is_virtual=True)
    elif mode == 'in-person':
        events = events.filter(is_virtual=False)
    if status_filter:
        events = events.filter(status=status_filter)

    return render(request, 'events/event_list.html', {
        'events': events.order_by('-start_date'),
        'query': query,
        'category': category,
        'categories': Event.CATEGORY_CHOICES,
        'mode': mode,
    })


def event_detail(request):
    pass


def event_detail(request, slug):
    event = get_object_or_404(Event, slug=slug)
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
    event = get_object_or_404(Event, slug=slug, status='published')
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
        event = form.save(commit=False)
        event.organizer = request.user
        event.save()
        TicketTier.objects.create(event=event, name='General Admission', price=0, capacity=event.max_capacity)
        messages.success(request, 'Event created! Now add ticket tiers, speakers, and sessions.')
        return redirect('event_manage', slug=event.slug)
    return render(request, 'events/event_form.html', {'form': form, 'action': 'Create Event'})


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
    regs = event.registrations.filter(status__in=['confirmed', 'checked_in'])
    tier_data = []
    for tier in event.ticket_tiers.all():
        sold = tier.registrations.filter(status__in=['confirmed', 'checked_in']).count()
        revenue = sum(r.amount_paid for r in tier.registrations.filter(status__in=['confirmed', 'checked_in']))
        tier_data.append({'tier': tier, 'sold': sold, 'revenue': revenue})

    from django.db.models.functions import TruncDate
    daily_regs = (regs.annotate(date=TruncDate('registered_at'))
                  .values('date').annotate(count=Count('id')).order_by('date'))

    polls_count = sum(s.polls.count() for s in event.sessions.all())
    qa_count = sum(s.questions.count() for s in event.sessions.all())

    return render(request, 'events/manage/analytics.html', {
        'event': event,
        'total_registered': regs.count(),
        'total_checked_in': event.registrations.filter(status='checked_in').count(),
        'total_revenue': sum(r.amount_paid for r in regs),
        'tier_data': tier_data,
        'daily_regs': list(daily_regs),
        'polls_count': polls_count,
        'qa_count': qa_count,
        'sessions_count': event.sessions.count(),
        'speakers_count': event.speakers.count(),
        'sponsors_count': event.sponsors.count(),
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
    registration = get_object_or_404(Registration, ticket_id=ticket_id, user=request.user)
    return render(request, 'events/ticket.html', {'registration': registration})


@login_required
def my_tickets(request):
    registrations = Registration.objects.filter(user=request.user).select_related('event', 'ticket_tier').order_by('-registered_at')
    return render(request, 'events/my_tickets.html', {'registrations': registrations})


@login_required
def my_events(request):
    events = Event.objects.filter(organizer=request.user).order_by('-created_at')
    return render(request, 'events/my_events.html', {'events': events})
