from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count
from django.utils import timezone
from django.http import JsonResponse
from django.conf import settings
import requests
import uuid
import hmac
import hashlib
import base64
import json
from .models import (Event, TicketTier, Registration, Speaker, EventSession,
                     Sponsor, Announcement, Poll, PollChoice, PollVote, QAQuestion, FavoriteSession, FavoriteEvent, Payment)
from .forms import (EventForm, TicketTierForm, SpeakerForm, SessionForm,
                    SponsorForm, AnnouncementForm, QAQuestionForm, PollForm, CheckInForm)


def home(request):
    # Block admin users from exploring events
    if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
        return redirect('admin_dashboard')

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
    # Block admin users from exploring events
    if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
        messages.info(request, 'Admins cannot browse events. Use the Admin Panel instead.')
        return redirect('admin_dashboard')

    events = Event.objects.filter(status__in=['published', 'ongoing', 'completed'])
    query = request.GET.get('q', '')
    category = request.GET.get('category', '')
    event_type = request.GET.get('type', '')  # 'all' or 'live'

    if query:
        events = events.filter(Q(title__icontains=query) | Q(description__icontains=query) | Q(city__icontains=query) | Q(tags__icontains=query))
    if category:
        events = events.filter(category=category)
    if event_type == 'live':
        now = timezone.now()
        events = events.filter(
            Q(status='ongoing') | Q(status='published', start_date__lte=now, end_date__gte=now)
        ).distinct()

    # Sort: featured first, then nearest start date
    from django.db.models import Case, When, BooleanField
    events = events.annotate(
        is_featured_order=Case(
            When(is_featured=True, then=0),
            default=1,
            output_field=BooleanField()
        )
    ).order_by('is_featured_order', 'start_date')

    return render(request, 'events/event_list.html', {
        'events': events,
        'query': query,
        'category': category,
        'categories': Event.CATEGORY_CHOICES,
        'event_type': event_type,
    })


def api_event_list(request):
    events = Event.objects.filter(status__in=['published', 'ongoing', 'completed'])
    events_data = []
    for event in events:
        events_data.append({
            'id': event.id,
            'title': event.title,
            'slug': event.slug,
            'description': event.description,
            'category': event.category,
            'banner': event.banner.url if event.banner else None,
            'start_date': event.start_date.isoformat(),
            'end_date': event.end_date.isoformat() if event.end_date else None,
            'venue': event.venue,
            'city': event.city,
            'is_virtual': event.is_virtual,
            'virtual_link': event.virtual_link,
            'max_capacity': event.max_capacity,
            'price': float(event.price) if event.price else 0.0,
            'status': event.status,
            'is_featured': event.is_featured,
            'registered_count': event.get_registered_count(),
        })
    return JsonResponse(events_data, safe=False)

def api_event_detail(request, slug):
    event = get_object_or_404(Event, slug=slug)
    ticket_tiers = []
    for tier in event.ticket_tiers.filter(is_active=True):
        ticket_tiers.append({
            'id': tier.id,
            'name': tier.name,
            'description': tier.description,
            'price': float(tier.price),
            'capacity': tier.capacity,
            'sold_count': tier.get_available() if tier.capacity else 0,
            'is_active': tier.is_active,
        })
    return JsonResponse({
        'id': event.id,
        'title': event.title,
        'slug': event.slug,
        'description': event.description,
        'category': event.category,
        'banner': event.banner.url if event.banner else None,
        'start_date': event.start_date.isoformat(),
        'end_date': event.end_date.isoformat() if event.end_date else None,
        'venue': event.venue,
        'city': event.city,
        'is_virtual': event.is_virtual,
        'virtual_link': event.virtual_link,
        'max_capacity': event.max_capacity,
        'price': float(event.price) if event.price else 0.0,
        'status': event.status,
        'is_featured': event.is_featured,
        'registered_count': event.get_registered_count(),
        'ticket_tiers': ticket_tiers,
    })


def event_detail(request, slug):
    # Block admin users from exploring events
    if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
        messages.info(request, 'Admins cannot browse events. Use the Admin Panel instead.')
        return redirect('admin_dashboard')

    event = get_object_or_404(Event, slug=slug)
    is_registered_free = False
    registration = None
    has_any_registrations = False
    if request.user.is_authenticated:
        # Check if user has ANY confirmed registrations
        registration = Registration.objects.filter(user=request.user, event=event, status='confirmed').first()
        has_any_registrations = registration is not None
        # Check if user is registered for a FREE ticket specifically
        is_registered_free = Registration.objects.filter(
            user=request.user, 
            event=event, 
            status='confirmed', 
            amount_paid=0
        ).exists()
    tiers = event.ticket_tiers.filter(is_active=True)
    speakers = event.speakers.all()[:6]
    sponsors = event.sponsors.all()
    announcements = event.announcements.all()[:5]
    sessions = event.sessions.all()[:5]
    return render(request, 'events/event_detail.html', {
        'event': event,
        'is_registered_free': is_registered_free,
        'has_any_registrations': has_any_registrations,
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
    if event.organizer == request.user:
        messages.error(request, 'You cannot register for your own event.')
        return redirect('event_detail', slug=slug)
    
    # Check if user is trying to register for a free event again
    confirmed_free_reg = Registration.objects.filter(
        user=request.user, 
        event=event, 
        status='confirmed', 
        amount_paid=0
    ).first()
    if confirmed_free_reg:
        messages.warning(request, 'You are already registered for this free event.')
        return redirect('view_ticket', ticket_id=confirmed_free_reg.ticket_id)
    
    if not event.is_registration_open():
        messages.error(request, 'Registration is closed for this event.')
        return redirect('event_detail', slug=slug)
    tiers = event.ticket_tiers.filter(is_active=True)
    if request.method == 'POST':
        tier_id = request.POST.get('tier_id')
        payment_method = 'esewa'  # Only eSewa is supported
        tier = get_object_or_404(TicketTier, id=tier_id, event=event)
        if tier.get_available() <= 0 and tier.capacity != 0:
            messages.error(request, 'Sorry, this ticket tier is sold out.')
            return redirect('event_register', slug=slug)
        
        # Enforce 5-free-event limit: users can register for max 5 UNIQUE free events total
        if tier.is_free():
            # Count unique free events the user has registered for
            unique_free_events = Registration.objects.filter(
                user=request.user,
                status='confirmed',
                amount_paid=0
            ).values('event').distinct().count()
            
            if unique_free_events >= 5:
                messages.error(request, 'You have reached the maximum of 5 free event registrations. Choose a paid ticket for unlimited registrations.')
                return redirect('event_register', slug=slug)
            
            # Free ticket, register immediately
            registration = Registration.objects.create(
                user=request.user,
                event=event,
                ticket_tier=tier,
                status='confirmed',
                amount_paid=tier.price,
            )
            messages.success(request, f'Successfully registered! Your ticket ID: {registration.ticket_id}')
            return redirect('view_ticket', ticket_id=registration.ticket_id)
        else:
            # First, delete any existing pending registrations/payments for this user+event
            Registration.objects.filter(user=request.user, event=event, status='pending').delete()
            Payment.objects.filter(user=request.user, registration__event=event, status='pending').delete()
            
            # Paid ticket, initiate eSewa payment
            return initiate_esewa_payment(request, event, tier)
    # Prepare JSON-serializable tiers data
    tiers_data = [
        {
            'id': tier.id,
            'price': float(tier.price)
        }
        for tier in tiers
    ]
    return render(request, 'events/event_register.html', {'event': event, 'tiers': tiers, 'tiers_data': tiers_data})


def generate_esewa_signature(message, secret):
    """Generate eSewa signature using HMAC-SHA256"""
    digest = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).digest()
    return base64.b64encode(digest).decode()


@login_required
def initiate_esewa_payment(request, event, tier):
    # Create pending registration first
    registration = Registration.objects.create(
        user=request.user,
        event=event,
        ticket_tier=tier,
        status='pending',
        amount_paid=tier.price,
    )
    
    # Generate unique transaction UUID
    transaction_uuid = str(uuid.uuid4())
    
    # Create payment record
    payment = Payment.objects.create(
        user=request.user,
        registration=registration,
        amount=tier.price,
        payment_method='esewa',
        transaction_uuid=transaction_uuid,
        status='pending'
    )
    
    # Prepare eSewa payment data
    total_amount = float(tier.price)
    product_code = settings.ESEWA_MERCHANT_CODE
    
    # Generate message for signature
    message = f"total_amount={total_amount},transaction_uuid={transaction_uuid},product_code={product_code}"
    
    # Generate signature
    signature = generate_esewa_signature(message, settings.ESEWA_SECRET_KEY)
    
    # Context for the template that will auto-submit the form
    context = {
        'amount': total_amount,
        'tax_amount': 0,
        'total_amount': total_amount,
        'transaction_uuid': transaction_uuid,
        'product_code': product_code,
        'product_service_charge': 0,
        'product_delivery_charge': 0,
        'success_url': settings.ESEWA_SUCCESS_URL,
        'failure_url': settings.ESEWA_FAILURE_URL,
        'signed_field_names': 'total_amount,transaction_uuid,product_code',
        'signature': signature,
    }
    
    return render(request, 'events/esewa_payment.html', context)


def esewa_payment_success(request):
    data_param = request.GET.get('data')
    
    if not data_param:
        # Clean up any pending payments/registrations for this user
        if request.user.is_authenticated:
            pending_payments = Payment.objects.filter(user=request.user, status='pending')
            for payment in pending_payments:
                if payment.registration:
                    payment.registration.delete()
                payment.delete()
        messages.error(request, 'Invalid payment response.')
        return redirect('event_list')
    
    try:
        # Decode base64 data
        decoded_data = base64.b64decode(data_param)
        payment_data = json.loads(decoded_data)
        
        transaction_uuid = payment_data.get('transaction_uuid')
        total_amount = payment_data.get('total_amount')
        status = payment_data.get('status')
        
        if not transaction_uuid or not total_amount:
            raise ValueError("Missing required fields in payment data")
        
    except Exception as e:
        # Clean up on error
        if request.user.is_authenticated:
            pending_payments = Payment.objects.filter(user=request.user, status='pending')
            for payment in pending_payments:
                if payment.registration:
                    payment.registration.delete()
                payment.delete()
        messages.error(request, f'Error processing payment data: {str(e)}')
        return redirect('event_list')
    
    try:
        payment = Payment.objects.get(transaction_uuid=transaction_uuid)
    except Payment.DoesNotExist:
        messages.error(request, 'Payment record not found.')
        return redirect('event_list')
    
    # First check the status from eSewa's response
    if status == 'COMPLETE':
        # Verify payment with eSewa's API to be safe
        try:
            params = {
                'product_code': settings.ESEWA_MERCHANT_CODE,
                'total_amount': total_amount,
                'transaction_uuid': transaction_uuid
            }
            response = requests.get(
                "https://rc.esewa.com.np/api/epay/transaction/status/",
                params=params
            )
            response_data = response.json()
            
            if response.status_code == 200 and response_data.get('status') == 'COMPLETE':
                # Payment successful
                payment.status = 'completed'
                payment.transaction_id = response_data.get('ref_id')
                payment.save()
                
                # Confirm registration
                registration = payment.registration
                registration.status = 'confirmed'
                registration.save()
                
                messages.success(request, f'Payment successful! Your ticket ID: {registration.ticket_id}')
                return redirect('view_ticket', ticket_id=registration.ticket_id)
        except Exception as e:
            # If API verification fails but eSewa said it's complete, still proceed? Or fail?
            # Let's proceed with eSewa's response for now
            pass
    
    # If we get here, payment failed
    payment.status = 'failed'
    payment.save()
    
    # Delete pending registration
    if payment.registration:
        payment.registration.delete()
    
    messages.error(request, 'Payment failed or cancelled. Please try again.')
    return redirect('event_list')


def esewa_payment_failure(request):
    # Clean up any pending payments/registrations for this user
    if request.user.is_authenticated:
        # Delete pending payments and their associated registrations
        pending_payments = Payment.objects.filter(user=request.user, status='pending')
        for payment in pending_payments:
            if payment.registration:
                payment.registration.delete()
            payment.delete()
    
    messages.error(request, 'Payment cancelled or failed. Please try again.')
    return redirect('event_list')


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
        event.status = 'published'
        event.save()
        TicketTier.objects.create(event=event, name='General Admission', price=event.price or 0.00, capacity=event.max_capacity)
        messages.success(request, 'Event published! Now add ticket tiers, speakers, and sessions.')
        return redirect('event_manage', slug=event.slug)
    return render(request, 'events/event_form.html', {'form': form, 'action': 'Post Event'})


@login_required
def event_edit(request, slug):
    event = get_object_or_404(Event, slug=slug, organizer=request.user)
    form = EventForm(request.POST or None, request.FILES or None, instance=event)
    if request.method == 'POST' and form.is_valid():
        event = form.save()
        messages.success(request, 'Event updated successfully!')
        return redirect('event_manage', slug=event.slug)
    return render(request, 'events/event_form.html', {'form': form, 'action': 'Edit Event'})


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
    return redirect('event_detail', slug=slug)


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
    registration = get_object_or_404(Registration, ticket_id=ticket_id, user=request.user, status__in=['confirmed', 'checked_in'])
    return render(request, 'events/ticket.html', {'registration': registration})


@login_required
def my_tickets(request):
    registrations = Registration.objects.filter(user=request.user, status__in=['confirmed', 'checked_in']).select_related('event', 'ticket_tier').order_by('-registered_at')
    return render(request, 'events/my_tickets.html', {'registrations': registrations})


@login_required
def my_events(request):
    organized = Event.objects.filter(organizer=request.user).order_by('-created_at')
    registered = Registration.objects.filter(user=request.user, status__in=['confirmed', 'checked_in']).select_related('event', 'ticket_tier').order_by('-registered_at')
    profile = getattr(request.user, 'profile', None)
    is_organizer = profile and profile.role == 'organizer'
    return render(request, 'events/my_events.html', {
        'organized': organized,
        'registered': registered,
        'is_organizer': is_organizer,
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


@login_required
def toggle_favorite_event(request, slug):
    if request.method == 'POST':
        event = get_object_or_404(Event, slug=slug)
        fav, created = FavoriteEvent.objects.get_or_create(user=request.user, event=event)
        if not created:
            fav.delete()
            messages.success(request, f"Removed '{event.title}' from your interests.")
        else:
            messages.success(request, f"Added '{event.title}' to your interests.")
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect('event_list')

