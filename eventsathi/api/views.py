import csv
import io
import re
import random
import logging
from django.http import HttpResponse
from datetime import timedelta
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db.models import Sum, Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import status, permissions, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import UserProfile, EmailVerificationCode, OrganizerProfile, Message
from accounts.views import send_eventsathi_email
from events.models import (
    Event, TicketTier, Registration, Announcement, EventLike, 
    EventComment, SavedEvent, OrganizerFollow, EventInterest, 
    Notification, Category, EventImage, Payment, EventAnalytics
)
from .serializers import (
    UserSerializer, RegisterSerializer, EventSerializer, 
    TicketTierSerializer, RegistrationSerializer, CommentSerializer,
    CategorySerializer, NotificationSerializer, MessageSerializer
)
from geopy.geocoders import Nominatim
from geopy.distance import geodesic


class ReverseGeocodeView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        lat = request.query_params.get('lat')
        lng = request.query_params.get('lng')
        
        if not lat or not lng:
            return Response({'status': 'error', 'message': 'lat and lng required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            geolocator = Nominatim(user_agent="eventsathi")
            location = geolocator.reverse(f"{lat}, {lng}")
            address = location.raw.get('address', {})
            city = address.get('city') or address.get('town') or address.get('village') or address.get('suburb')
            
            return Response({
                'status': 'success',
                'city': city,
                'display_name': location.address,
                'address_details': address
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

from events.utils import log_analytics

logger = logging.getLogger(__name__)


# JWT Token generator utility
def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            
            # Generate verification code
            code = f"{random.randint(100000, 999999)}"
            EmailVerificationCode.objects.create(user=user, code=code)

            # Send activation email
            try:
                send_eventsathi_email(
                    'Verify your EventSathi Account',
                    f'Hi {user.first_name or user.username},\n\nWelcome to EventSathi!\nYour email verification code is: {code}\n\nPlease enter this code to activate your account.',
                    [user.email],
                )
            except Exception as e:
                logger.error(f"Failed to send welcome/verification email: {e}")

            return Response({
                'status': 'success',
                'message': 'Registration successful. An activation code has been sent to your email.',
                'user_id': user.id,
                'email': user.email
            }, status=status.HTTP_201_CREATED)
        
        return Response({
            'status': 'error',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class VerifyEmailView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        user_id = request.data.get('user_id')
        code = request.data.get('code', '').strip()

        if not user_id or not code:
            return Response({
                'status': 'error',
                'message': 'user_id and code are required.'
            }, status=status.HTTP_400_BAD_REQUEST)

        user = get_object_or_404(User, id=user_id)
        code_obj = EmailVerificationCode.objects.filter(user=user, code=code).first()
        if code_obj:
            # Delete verification codes
            EmailVerificationCode.objects.filter(user=user).delete()
            
            if not user.is_active:
                # Activate account
                user.is_active = True
                user.save()

            # Generate tokens
            tokens = get_tokens_for_user(user)
            user_serializer = UserSerializer(user, context={'request': request})

            return Response({
                'status': 'success',
                'message': 'Verification successful.',
                'tokens': tokens,
                'user': user_serializer.data
            }, status=status.HTTP_200_OK)
        else:
            # If code is invalid but user is already active, we can check if they had a code. If not, return already verified
            if user.is_active and not EmailVerificationCode.objects.filter(user=user).exists():
                tokens = get_tokens_for_user(user)
                user_serializer = UserSerializer(user, context={'request': request})
                return Response({
                    'status': 'success',
                    'message': 'Account is already verified.',
                    'tokens': tokens,
                    'user': user_serializer.data
                }, status=status.HTTP_200_OK)
                
            return Response({
                'status': 'error',
                'message': 'Invalid verification code.'
            }, status=status.HTTP_400_BAD_REQUEST)


class ResendCodeView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        user_id = request.data.get('user_id')
        if not user_id:
            return Response({
                'status': 'error',
                'message': 'user_id is required.'
            }, status=status.HTTP_400_BAD_REQUEST)

        user = get_object_or_404(User, id=user_id)
        if user.is_active:
            return Response({
                'status': 'error',
                'message': 'Account is already verified.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Delete old codes
        EmailVerificationCode.objects.filter(user=user).delete()
        # Generate new code
        code = f"{random.randint(100000, 999999)}"
        EmailVerificationCode.objects.create(user=user, code=code)
        
        # Send code
        send_eventsathi_email(
            'Verify your EventSathi Account',
            f'Hi {user.first_name or user.username},\n\nYour new email verification code is: {code}\n\nPlease enter this code to activate your account.',
            [user.email],
        )

        return Response({
            'status': 'success',
            'message': 'New verification code sent to email.'
        }, status=status.HTTP_200_OK)


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email_or_username = request.data.get('email_or_username', '').strip()
        password = request.data.get('password', '')

        if not email_or_username or not password:
            return Response({
                'status': 'error',
                'message': 'Username/Email and Password are required.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Find user by username or email
        user = User.objects.filter(username__iexact=email_or_username).first()
        if not user:
            user = User.objects.filter(email__iexact=email_or_username).first()

        if user and user.check_password(password):
            if not user.is_active:
                return Response({
                    'status': 'requires_verification',
                    'message': 'Email verification is required before login.',
                    'user_id': user.id
                }, status=status.HTTP_403_FORBIDDEN)

            # Check profile exists
            profile, _ = UserProfile.objects.get_or_create(user=user)

            # Generate tokens
            tokens = get_tokens_for_user(user)
            user_serializer = UserSerializer(user, context={'request': request})

            return Response({
                'status': 'success',
                'tokens': tokens,
                'user': user_serializer.data
            }, status=status.HTTP_200_OK)

        return Response({
            'status': 'error',
            'message': 'Invalid username/email or password.'
        }, status=status.HTTP_401_UNAUTHORIZED)


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({
                'status': 'success',
                'message': 'Successfully logged out.'
            }, status=status.HTTP_205_RESET_CONTENT)
        except Exception:
            return Response({
                'status': 'error',
                'message': 'Invalid token.'
            }, status=status.HTTP_400_BAD_REQUEST)


class ForgotPasswordView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({
                'status': 'error',
                'message': 'Email is required.'
            }, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(email__iexact=email).first()
        if user:
            code = f"{random.randint(100000, 999999)}"
            EmailVerificationCode.objects.filter(user=user).delete()
            EmailVerificationCode.objects.create(user=user, code=code)
            
            send_eventsathi_email(
                'Reset your EventSathi Password',
                f'Hi {user.username},\n\nYour password reset code is: {code}',
                [user.email],
            )
            
            return Response({
                'status': 'success',
                'message': 'Password reset code sent to email.'
            }, status=status.HTTP_200_OK)
        
        return Response({
            'status': 'error',
            'message': 'No user found with this email.'
        }, status=status.HTTP_404_NOT_FOUND)


class ResetPasswordView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email')
        code = request.data.get('code')
        new_password = request.data.get('new_password')

        if not all([email, code, new_password]):
            return Response({
                'status': 'error',
                'message': 'Email, code and new_password are required.'
            }, status=status.HTTP_400_BAD_REQUEST)

        user = get_object_or_404(User, email__iexact=email)
        code_obj = EmailVerificationCode.objects.filter(user=user, code=code).first()
        if code_obj:
            user.set_password(new_password)
            user.save()
            EmailVerificationCode.objects.filter(user=user).delete()
            return Response({
                'status': 'success',
                'message': 'Password reset successful.'
            }, status=status.HTTP_200_OK)
        
        return Response({
            'status': 'error',
            'message': 'Invalid reset code.'
        }, status=status.HTTP_400_BAD_REQUEST)


class HealthCheckView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response({
            'status': 'success',
            'message': 'API is connected and healthy.',
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_200_OK)


class UserProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user, context={'request': request})
        return Response({
            'status': 'success',
            'user': serializer.data
        }, status=status.HTTP_200_OK)

    def put(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response({
                'status': 'success',
                'message': 'Profile updated successfully.',
                'user': serializer.data
            }, status=status.HTTP_200_OK)
        return Response({
            'status': 'error',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class UserAvatarUploadView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        profile = get_object_or_404(UserProfile, user=request.user)
        photo = request.FILES.get('photo')
        if not photo:
            return Response({
                'status': 'error',
                'message': 'No photo file provided.'
            }, status=status.HTTP_400_BAD_REQUEST)

        profile.photo = photo
        profile.save()

        user_serializer = UserSerializer(request.user, context={'request': request})
        return Response({
            'status': 'success',
            'message': 'Avatar photo uploaded successfully.',
            'user': user_serializer.data
        }, status=status.HTTP_200_OK)


class OrganizerUpgradeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        org_name = request.data.get('org_name')
        bio = request.data.get('bio', '')
        phone = request.data.get('phone', '')
        email = request.data.get('email', '')
        designation = request.data.get('designation', '')

        if not org_name:
            return Response({
                'status': 'error',
                'message': 'Organization Name is required.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Validate Nepal phone number format
        if phone and not re.match(r'^(98|97)\d{8}$', phone):
            return Response({
                'status': 'error',
                'message': 'Phone number must be a valid Nepal mobile number (e.g. 98XXXXXXXX or 97XXXXXXXX).'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Validate email format if provided
        if email and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            return Response({
                'status': 'error',
                'message': 'Please provide a valid email address.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Update UserProfile role
        profile.role = 'organizer'
        profile.organization = org_name
        if bio:
            profile.bio = bio
        if phone:
            profile.phone = phone
        if designation:
            profile.designation = designation
        profile.is_verified = True
        profile.save()

        # Create or update the separate OrganizerProfile
        org_profile, _ = OrganizerProfile.objects.update_or_create(
            user=request.user,
            defaults={
                'org_name': org_name,
                'bio': bio,
                'phone': phone,
                'email': email or request.user.email,
            }
        )

        user_serializer = UserSerializer(request.user, context={'request': request})
        return Response({
            'status': 'success',
            'message': 'Account upgraded to Organizer successfully.',
            'user': user_serializer.data
        }, status=status.HTTP_200_OK)



class EventListCreateView(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get(self, request):
        # Return all publicly visible events (published, ongoing, completed)
        events = Event.objects.filter(
            status__in=['published', 'ongoing', 'completed']
        ).order_by('-start_date')
        
        # Filtering
        category = request.query_params.get('category')
        if category:
            events = events.filter(category__iexact=category)
            
        city = request.query_params.get('city')
        if city:
            events = events.filter(city__iexact=city)

        search = request.query_params.get('search')
        if search:
            events = events.filter(
                Q(title__icontains=search) | Q(venue__icontains=search) | Q(city__icontains=search)
            )

        serializer = EventSerializer(events, many=True, context={'request': request})
        return Response({
            'status': 'success',
            'events': serializer.data
        }, status=status.HTTP_200_OK)

    def post(self, request):
        profile = getattr(request.user, 'profile', None)
        if not profile or profile.role != 'organizer':
            return Response({
                'status': 'error',
                'message': 'Only organizers can create events.'
            }, status=status.HTTP_403_FORBIDDEN)

        serializer = EventSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            # Generate a unique slug
            title = serializer.validated_data['title']
            slug = slugify(title)
            base_slug = slug
            counter = 1
            while Event.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            # Save with organizer
            event = serializer.save(organizer=request.user, slug=slug)

            # Optionally create default ticket tier if none passed
            tiers_data = request.data.get('ticket_tiers', [])
            if not tiers_data:
                TicketTier.objects.create(
                    event=event, 
                    name='General Admission', 
                    price=0.00, 
                    capacity=event.max_capacity,
                    description='Standard free ticket'
                )
            else:
                for tier in tiers_data:
                    TicketTier.objects.create(
                        event=event,
                        name=tier.get('name', 'General Admission'),
                        price=tier.get('price', 0.00),
                        capacity=tier.get('capacity', event.max_capacity),
                        description=tier.get('description', '')
                    )

            # Re-serialize to include tiers
            response_serializer = EventSerializer(event, context={'request': request})
            return Response({
                'status': 'success',
                'message': 'Event created successfully.',
                'event': response_serializer.data
            }, status=status.HTTP_201_CREATED)

        return Response({
            'status': 'error',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class EventDetailUpdateDeleteView(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get(self, request, pk):
        event = get_object_or_404(Event, id=pk)
        
        # Log view analytics
        log_analytics(request, event, 'view')
        
        # Increment view count
        event.views += 1
        event.save(update_fields=['views'])
        
        serializer = EventSerializer(event, context={'request': request})
        return Response({
            'status': 'success',
            'event': serializer.data
        }, status=status.HTTP_200_OK)

    def _update(self, request, pk):
        event = get_object_or_404(Event, id=pk)
        if event.organizer != request.user:
            return Response({
                'status': 'error',
                'message': 'Only the organizer can modify this event.'
            }, status=status.HTTP_403_FORBIDDEN)

        serializer = EventSerializer(event, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response({
                'status': 'success',
                'message': 'Event updated successfully.',
                'event': serializer.data
            }, status=status.HTTP_200_OK)
        return Response({
            'status': 'error',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk):
        return self._update(request, pk)

    def patch(self, request, pk):
        return self._update(request, pk)

    def delete(self, request, pk):
        event = get_object_or_404(Event, id=pk)
        if event.organizer != request.user:
            return Response({
                'status': 'error',
                'message': 'Only the organizer can delete this event.'
            }, status=status.HTTP_403_FORBIDDEN)

        event.delete()
        return Response({
            'status': 'success',
            'message': 'Event deleted successfully.'
        }, status=status.HTTP_200_OK)


class EventBannerUploadView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, pk):
        event = get_object_or_404(Event, id=pk)
        if event.organizer != request.user:
            return Response({
                'status': 'error',
                'message': 'Only the organizer can upload a banner.'
            }, status=status.HTTP_403_FORBIDDEN)

        banner = request.FILES.get('banner')
        if not banner:
            return Response({
                'status': 'error',
                'message': 'No banner file provided.'
            }, status=status.HTTP_400_BAD_REQUEST)

        event.banner = banner
        event.save()

        serializer = EventSerializer(event, context={'request': request})
        return Response({
            'status': 'success',
            'message': 'Event banner uploaded successfully.',
            'event': serializer.data
        }, status=status.HTTP_200_OK)


class EventLikeToggleView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, event_id):
        try:
            event = Event.objects.get(id=event_id)
        except Event.DoesNotExist:
            return Response({
                'status': 'error',
                'message': 'Event not found.'
            }, status=status.HTTP_404_NOT_FOUND)

        like, created = EventLike.objects.get_or_create(event=event, user=request.user)
        if not created:
            like.delete()
            liked = False
            msg = "Event unliked."
            log_analytics(request, event, 'unlike')
        else:
            liked = True
            msg = "Event liked."
            log_analytics(request, event, 'like')
            # Create synced real database Notification for the organizer
            if event.organizer != request.user:
                Notification.objects.create(
                    user=event.organizer,
                    title="New Event Like!",
                    content=f"{request.user.get_full_name() or request.user.username} liked your event: '{event.title}'.",
                    notification_type="like",
                    related_id=event.id
                )

        return Response({
            'status': 'success',
            'message': msg,
            'is_liked': liked,
            'likes_count': event.likes.count()
        }, status=status.HTTP_200_OK)


class EventCommentCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, event_id):
        try:
            event = Event.objects.get(id=event_id)
        except Event.DoesNotExist:
            return Response({
                'status': 'error',
                'message': 'Event not found.'
            }, status=status.HTTP_404_NOT_FOUND)

        content = request.data.get('content', '').strip()
        if not content:
            return Response({
                'status': 'error',
                'message': 'Comment content cannot be empty.'
            }, status=status.HTTP_400_BAD_REQUEST)

        comment = EventComment.objects.create(event=event, user=request.user, content=content)
        
        # Create synced real database Notification for the organizer
        if event.organizer != request.user:
            Notification.objects.create(
                user=event.organizer,
                title="New Event Comment",
                content=f"{request.user.get_full_name() or request.user.username} commented on '{event.title}': '{content[:50]}...'.",
                notification_type="comment",
                related_id=event.id
            )

        serializer = CommentSerializer(comment, context={'request': request})
        return Response({
            'status': 'success',
            'message': 'Comment added successfully.',
            'comment': serializer.data,
            'comments_count': event.comments.count()
        }, status=status.HTTP_201_CREATED)


class EventCommentsListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, event_id):
        event = get_object_or_404(Event, id=event_id)
        comments = event.comments.filter(parent=None).order_by('-created_at')
        serializer = CommentSerializer(comments, many=True, context={'request': request})
        return Response({
            'status': 'success',
            'comments': serializer.data,
            'comments_count': event.comments.count()
        }, status=status.HTTP_200_OK)


class BookingListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        bookings = Registration.objects.filter(user=request.user).order_by('-registered_at')
        serializer = RegistrationSerializer(bookings, many=True, context={'request': request})
        return Response({
            'status': 'success',
            'bookings': serializer.data
        }, status=status.HTTP_200_OK)

    def post(self, request):
        event_id = request.data.get('event_id')
        ticket_tier_id = request.data.get('ticket_tier_id')

        if not event_id or not ticket_tier_id:
            return Response({
                'status': 'error',
                'message': 'event_id and ticket_tier_id are required.'
            }, status=status.HTTP_400_BAD_REQUEST)

        event = get_object_or_404(Event, id=event_id)
        ticket_tier = get_object_or_404(TicketTier, id=ticket_tier_id, event=event)

        # Check capacity
        if ticket_tier.get_available() <= 0 or event.get_available_seats() <= 0:
            return Response({
                'status': 'error',
                'message': 'No tickets available in this tier.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check if already registered
        if Registration.objects.filter(user=request.user, event=event).exists():
            return Response({
                'status': 'error',
                'message': 'You have already booked a ticket for this event.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Create Booking
        booking = Registration.objects.create(
            user=request.user,
            event=event,
            ticket_tier=ticket_tier,
            status='confirmed',
            amount_paid=ticket_tier.price
        )

        # Create synced real database Notification
        Notification.objects.create(
            user=request.user,
            title="Ticket Booked Successfully!",
            content=f"You have registered for '{event.title}'. Ticket Tier: {ticket_tier.name}. Ticket ID: {booking.ticket_id}.",
            notification_type="booking",
            related_id=booking.id
        )

        serializer = RegistrationSerializer(booking, context={'request': request})
        return Response({
            'status': 'success',
            'message': 'Booking confirmed successfully.',
            'booking': serializer.data
        }, status=status.HTTP_201_CREATED)


class VerifyTicketView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        profile = getattr(request.user, 'profile', None)
        if not profile or profile.role != 'organizer':
            return Response({
                'status': 'error',
                'message': 'Only organizers can verify tickets.'
            }, status=status.HTTP_403_FORBIDDEN)

        qr_code = request.data.get('qr_code')
        if not qr_code:
            return Response({
                'status': 'error',
                'message': 'qr_code is required.'
            }, status=status.HTTP_400_BAD_REQUEST)
        qr_code = str(qr_code).strip()

        # Parse QR code format if standard: EVENTSATHI:TICKET_ID:USERNAME:SLUG
        # Or new format: EVENTSATHI:TICKET_ID:USER_ID:EVENT_ID:TOKEN
        booking = None
        if qr_code.startswith("EVENTSATHI:"):
            parts = qr_code.split(":")
            if len(parts) >= 2:
                ticket_id = parts[1]
                booking = Registration.objects.filter(ticket_id=ticket_id).first()
                
                # If new format with 5 parts, verify token!
                if len(parts) == 5 and booking:
                    import hashlib
                    from django.conf import settings
                    user_id = parts[2]
                    event_id = parts[3]
                    token = parts[4]
                    
                    expected_token = hashlib.sha256(f"{ticket_id}{settings.SECRET_KEY}".encode()).hexdigest()[:8]
                    if token != expected_token:
                        return Response({
                            'status': 'error',
                            'message': 'Security token verification failed. The ticket QR code is invalid.'
                        }, status=status.HTTP_400_BAD_REQUEST)
        
        if not booking:
            # Fallback search by exact qr_code content
            booking = Registration.objects.filter(qr_code=qr_code).first()

        if not booking:
            return Response({
                'status': 'error',
                'message': 'Ticket not found or invalid.'
            }, status=status.HTTP_404_NOT_FOUND)

        # Ensure the verifying organizer owns the event
        if booking.event.organizer != request.user:
            return Response({
                'status': 'error',
                'message': 'You are not the organizer of this event.'
            }, status=status.HTTP_403_FORBIDDEN)

        if booking.status == 'checked_in':
            serializer = RegistrationSerializer(booking, context={'request': request})
            return Response({
                'status': 'warning',
                'message': 'Ticket already checked in.',
                'booking': serializer.data
            }, status=status.HTTP_200_OK)

        # Check in the attendee
        booking.status = 'checked_in'
        booking.checked_in_at = timezone.now()
        booking.save()

        serializer = RegistrationSerializer(booking, context={'request': request})
        return Response({
            'status': 'success',
            'message': f'Ticket verified and attendee checked in successfully.',
            'booking': serializer.data
        }, status=status.HTTP_200_OK)


class OrganizerEventsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        profile = getattr(request.user, 'profile', None)
        if not profile or profile.role != 'organizer':
            return Response({
                'status': 'error',
                'message': 'Only organizers can view their events.'
            }, status=status.HTTP_403_FORBIDDEN)

        events = Event.objects.filter(organizer=request.user).order_by('-created_at')
        serializer = EventSerializer(events, many=True, context={'request': request})
        
        # Calculate stats for organizer
        processed_events = []
        for event_data in serializer.data:
            # Add organizer custom metrics
            evt_id = event_data['id']
            evt_obj = Event.objects.get(id=evt_id)
            booked_count = evt_obj.get_registered_count()
            min_price = evt_obj.get_min_price() or 0.00
            
            # Simple revenue estimate
            revenue = booked_count * float(min_price)
            checked_in = evt_obj.registrations.filter(status='checked_in').count()

            event_data['revenue'] = revenue
            event_data['checkedIn'] = checked_in
            processed_events.append(event_data)

        return Response({
            'status': 'success',
            'events': processed_events
        }, status=status.HTTP_200_OK)


class GoogleLoginView(APIView):
    """Handle Google sign-in from the Flutter app.
    Receives Google user profile data, gets or creates the Django User,
    and returns JWT tokens."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email', '').strip()
        first_name = request.data.get('first_name', '')
        last_name = request.data.get('last_name', '')
        google_id = request.data.get('google_id', '')

        if not email:
            return Response({
                'status': 'error',
                'message': 'Email is required for Google login.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Find or create user
        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            username = email.split('@')[0]
            base_username = username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1

            user = User.objects.create(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                is_active=True,
            )
            user.set_unusable_password()
            user.save()

            UserProfile.objects.get_or_create(
                user=user,
                defaults={'role': 'attendee', 'is_verified': True}
            )
        else:
            # Update name if changed on Google side
            if first_name and user.first_name != first_name:
                user.first_name = first_name
            if last_name and user.last_name != last_name:
                user.last_name = last_name
            user.save()
            UserProfile.objects.get_or_create(
                user=user,
                defaults={'role': 'attendee', 'is_verified': True}
            )

        tokens = get_tokens_for_user(user)
        user_serializer = UserSerializer(user, context={'request': request})

        return Response({
            'status': 'success',
            'tokens': tokens,
            'user': user_serializer.data
        }, status=status.HTTP_200_OK)


class SwitchRoleView(APIView):
    """Switch the authenticated user's active role between
    'attendee' and 'organizer' without logging out."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        target_role = request.data.get('role', '').strip().lower()
        if target_role not in ('attendee', 'organizer'):
            return Response({
                'status': 'error',
                'message': 'Role must be either attendee or organizer.'
            }, status=status.HTTP_400_BAD_REQUEST)

        profile, _ = UserProfile.objects.get_or_create(user=request.user)

        # If switching to organizer, verify they have an OrganizerProfile
        if target_role == 'organizer':
            has_org = OrganizerProfile.objects.filter(user=request.user).exists()
            if not has_org:
                return Response({
                    'status': 'error',
                    'message': 'You must register as an organizer first via Host Event.'
                }, status=status.HTTP_400_BAD_REQUEST)

        profile.role = target_role
        profile.save()

        user_serializer = UserSerializer(request.user, context={'request': request})
        return Response({
            'status': 'success',
            'message': f'Switched to {target_role} mode.',
            'user': user_serializer.data
        }, status=status.HTTP_200_OK)


class OrganizerAnalyticsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        profile = getattr(request.user, 'profile', None)
        if not profile or profile.role != 'organizer':
            return Response({'status': 'error', 'message': 'Only organizers can view analytics'}, status=status.HTTP_403_FORBIDDEN)

        events = Event.objects.filter(organizer=request.user)
        total_views = events.aggregate(Sum('views'))['views__sum'] or 0
        total_likes = events.aggregate(Sum('total_likes'))['total_likes__sum'] or 0
        total_bookings = events.aggregate(Sum('total_bookings'))['total_bookings__sum'] or 0
        
        # Category popularity for this organizer
        category_stats = events.values('category__name').annotate(count=Count('id')).order_by('-count')
        
        # Recent analytics actions
        recent_actions = EventAnalytics.objects.filter(event__organizer=request.user).order_by('-created_at')[:20]
        actions_data = [{
            'event': a.event.title,
            'action': a.action,
            'platform': a.platform,
            'time': a.created_at.isoformat()
        } for a in recent_actions]

        return Response({
            'status': 'success',
            'summary': {
                'total_events': events.count(),
                'total_views': total_views,
                'total_likes': total_likes,
                'total_bookings': total_bookings,
            },
            'category_distribution': category_stats,
            'recent_activity': actions_data
        }, status=status.HTTP_200_OK)


class OrganizerDashboardAnalyticsView(APIView):
    """Comprehensive organizer analytics: sales, attendance, views,
    conversion, statements, upcoming/past events, attendee data."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        profile = getattr(request.user, 'profile', None)
        if not profile or profile.role != 'organizer':
            return Response({
                'status': 'error',
                'message': 'Only organizers can access the dashboard.'
            }, status=status.HTTP_403_FORBIDDEN)

        now = timezone.now()
        events = Event.objects.filter(organizer=request.user)

        # ── Event counts ──
        total_events = events.count()
        upcoming_events = events.filter(start_date__gt=now).count()
        past_events = events.filter(end_date__lt=now).count()

        # ── Ticket sales ──
        all_bookings = Registration.objects.filter(event__organizer=request.user)
        total_sold = all_bookings.filter(status__in=['confirmed', 'checked_in']).count()

        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        year_ago = now - timedelta(days=365)

        sold_weekly = all_bookings.filter(
            status__in=['confirmed', 'checked_in'],
            registered_at__gte=week_ago
        ).count()
        sold_monthly = all_bookings.filter(
            status__in=['confirmed', 'checked_in'],
            registered_at__gte=month_ago
        ).count()
        sold_yearly = all_bookings.filter(
            status__in=['confirmed', 'checked_in'],
            registered_at__gte=year_ago
        ).count()

        # ── Attendance / Check-in ──
        total_checked_in = all_bookings.filter(status='checked_in').count()

        # ── Views ──
        total_views = events.aggregate(total=Sum('views'))['total'] or 0

        # ── Conversion rate ──
        conversion_rate = 0.0
        if total_views > 0:
            conversion_rate = round((total_sold / total_views) * 100, 2)

        # ── Revenue / Statement ──
        revenue_data = all_bookings.filter(
            status__in=['confirmed', 'checked_in']
        ).aggregate(total_revenue=Sum('amount_paid'))
        total_revenue = float(revenue_data['total_revenue'] or 0)

        revenue_weekly = float(
            all_bookings.filter(
                status__in=['confirmed', 'checked_in'],
                registered_at__gte=week_ago
            ).aggregate(s=Sum('amount_paid'))['s'] or 0
        )
        revenue_monthly = float(
            all_bookings.filter(
                status__in=['confirmed', 'checked_in'],
                registered_at__gte=month_ago
            ).aggregate(s=Sum('amount_paid'))['s'] or 0
        )

        # ── Per-event breakdown ──
        events_breakdown = []
        for evt in events.order_by('-start_date'):
            evt_bookings = Registration.objects.filter(event=evt)
            evt_sold = evt_bookings.filter(status__in=['confirmed', 'checked_in']).count()
            evt_checked = evt_bookings.filter(status='checked_in').count()
            evt_revenue = float(
                evt_bookings.filter(
                    status__in=['confirmed', 'checked_in']
                ).aggregate(s=Sum('amount_paid'))['s'] or 0
            )

            # Attendee list
            attendees = []
            for reg in evt_bookings.select_related('user', 'ticket_tier'):
                attendees.append({
                    'user_id': reg.user.id,
                    'username': reg.user.username,
                    'name': reg.user.get_full_name() or reg.user.username,
                    'email': reg.user.email,
                    'ticket_tier': reg.ticket_tier.name if reg.ticket_tier else '',
                    'amount_paid': float(reg.amount_paid),
                    'status': reg.status,
                    'booked_at': reg.registered_at.isoformat() if reg.registered_at else '',
                    'checked_in_at': reg.checked_in_at.isoformat() if reg.checked_in_at else None,
                })

            evt_status = 'upcoming' if evt.start_date > now else ('past' if evt.end_date < now else 'ongoing')

            events_breakdown.append({
                'id': evt.id,
                'title': evt.title,
                'date': evt.start_date.isoformat(),
                'end_date': evt.end_date.isoformat(),
                'venue': evt.venue,
                'city': evt.city,
                'latitude': float(evt.latitude) if evt.latitude else None,
                'longitude': float(evt.longitude) if evt.longitude else None,
                'status': evt_status,
                'total_capacity': evt.max_capacity,
                'tickets_sold': evt_sold,
                'checked_in': evt_checked,
                'views': evt.views,
                'revenue': evt_revenue,
                'conversion': round((evt_sold / evt.views * 100), 2) if evt.views > 0 else 0,
                'attendees': attendees,
            })

        return Response({
            'status': 'success',
            'dashboard': {
                'total_events': total_events,
                'upcoming_events': upcoming_events,
                'past_events': past_events,
                'tickets_sold': {
                    'total': total_sold,
                    'weekly': sold_weekly,
                    'monthly': sold_monthly,
                    'yearly': sold_yearly,
                },
                'attendance': {
                    'total_checked_in': total_checked_in,
                    'attendance_rate': round((total_checked_in / total_sold * 100), 2) if total_sold > 0 else 0,
                },
                'views': total_views,
                'conversion_rate': conversion_rate,
                'statement': {
                    'total_revenue': total_revenue,
                    'revenue_weekly': revenue_weekly,
                    'revenue_monthly': revenue_monthly,
                    'total_transactions': total_sold,
                },
                'events': events_breakdown,
            }
        }, status=status.HTTP_200_OK)


class EventViewTrackView(APIView):
    """Increment the view counter for an event (called when a user opens event details)."""
    permission_classes = [permissions.AllowAny]

    def post(self, request, pk):
        event = get_object_or_404(Event, id=pk)
        event.views += 1
        event.save(update_fields=['views'])
        return Response({'status': 'success'}, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        return Response({
            'status': 'success',
            'message': 'Logged out successfully.'
        }, status=status.HTTP_200_OK)


class EventCategoriesView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        categories = [{'id': choice[0], 'name': choice[1]} for choice in Event.CATEGORY_CHOICES]
        return Response({
            'status': 'success',
            'categories': categories
        }, status=status.HTTP_200_OK)


class EventSearchView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        events = Event.objects.filter(status__in=['published', 'ongoing', 'completed']).order_by('-start_date')
        
        q = request.query_params.get('q') or request.query_params.get('search')
        if q:
            events = events.filter(Q(title__icontains=q) | Q(venue__icontains=q) | Q(description__icontains=q))
            
        category = request.query_params.get('category')
        if category:
            events = events.filter(category__iexact=category)
            
        city = request.query_params.get('city')
        if city:
            events = events.filter(city__iexact=city)

        serializer = EventSerializer(events, many=True, context={'request': request})
        return Response({
            'status': 'success',
            'events': serializer.data
        }, status=status.HTTP_200_OK)


class TicketsListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        bookings = Registration.objects.filter(user=request.user).order_by('-registered_at')
        serializer = RegistrationSerializer(bookings, many=True, context={'request': request})
        return Response({
            'status': 'success',
            'tickets': serializer.data
        }, status=status.HTTP_200_OK)


class TicketQRView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        booking = get_object_or_404(Registration, id=pk)
        if booking.user != request.user and booking.event.organizer != request.user:
            return Response({
                'status': 'error',
                'message': 'Permission denied.'
            }, status=status.HTTP_403_FORBIDDEN)
        return Response({
            'status': 'success',
            'ticket_id': booking.ticket_id,
            'qr_code': booking.qr_code,
            'status': booking.status
        }, status=status.HTTP_200_OK)


class GlobalUnreadCountView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        notification_count = Notification.objects.filter(user=request.user, is_read=False).count()
        message_count = Message.objects.filter(receiver=request.user, is_read=False).count()
        return Response({
            'status': 'success',
            'unread_notifications': notification_count,
            'unread_messages': message_count,
            'total_unread': notification_count + message_count
        }, status=status.HTTP_200_OK)


class NotificationsListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Fetch from our database-backed Notification model
        db_notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
        
        notifications_data = []
        for n in db_notifications:
            notifications_data.append({
                'id': n.id,
                'title': n.title,
                'content': n.content,
                'notification_type': n.notification_type,
                'is_read': n.is_read,
                'related_id': n.related_id,
                'created_at': n.created_at.isoformat()
            })
            
        # Fallback to a system announcement if list is empty
        if not notifications_data:
            notifications_data = [
                {
                    'id': 1,
                    'title': 'Welcome to Event-Sathi!',
                    'content': 'Discover events near you, book tickets, and follow organizers.',
                    'notification_type': 'system',
                    'is_read': False,
                    'related_id': None,
                    'created_at': timezone.now().isoformat()
                }
            ]
            
        unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
            
        return Response({
            'status': 'success',
            'unread_count': unread_count,
            'notifications': notifications_data
        }, status=status.HTTP_200_OK)


class AdminUsersListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        users = User.objects.all().order_by('-date_joined')
        users_data = []
        for u in users:
            profile = getattr(u, 'profile', None)
            role = profile.role if profile else 'attendee'
            is_verified = profile.is_verified if profile else False
            users_data.append({
                'id': str(u.id),
                'username': u.username,
                'name': u.get_full_name() or u.username,
                'email': u.email,
                'role': role,
                'status': 'verified' if is_verified else 'pending' if role == 'organizer' else 'active'
            })
        return Response({
            'status': 'success',
            'users': users_data
        }, status=status.HTTP_200_OK)


class AdminEventsListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        events = Event.objects.all().order_by('-created_at')
        events_data = []
        for evt in events:
            events_data.append({
                'id': str(evt.id),
                'title': evt.title,
                'organizer_name': evt.organizer.username,
                'views': evt.views,
                'is_featured': evt.is_featured,
                'status': evt.status
            })
        return Response({
            'status': 'success',
            'events': events_data
        }, status=status.HTTP_200_OK)


class AdminPaymentsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        registrations = Registration.objects.filter(status__in=['confirmed', 'checked_in'])
        total_revenue = sum(float(r.amount_paid) for r in registrations)
        
        return Response({
            'status': 'success',
            'finance': {
                'transaction_volume': total_revenue,
                'verification_fee': 300.0,
                'khalti_online': True,
                'esewa_online': True,
                'bank_online': True
            }
        }, status=status.HTTP_200_OK)


# ── Real Synced Social Actions (Save, Follow, Interest, Messages) ──

class EventSaveToggleView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, event_id):
        event = get_object_or_404(Event, id=event_id)
        saved_obj, created = SavedEvent.objects.get_or_create(user=request.user, event=event)
        if not created:
            saved_obj.delete()
            saved = False
            msg = "Event removed from bookmarks."
        else:
            saved = True
            msg = "Event saved to bookmarks."
            
        return Response({
            'status': 'success',
            'message': msg,
            'is_saved': saved
        }, status=status.HTTP_200_OK)


class SavedEventsListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        saved_events = SavedEvent.objects.filter(user=request.user).select_related('event')
        events = [s.event for s in saved_events]
        serializer = EventSerializer(events, many=True, context={'request': request})
        return Response({
            'status': 'success',
            'events': serializer.data
        }, status=status.HTTP_200_OK)


class OrganizerFollowToggleView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, organizer_id):
        organizer = get_object_or_404(User, id=organizer_id)
        
        # Verify the target is indeed an organizer
        profile = getattr(organizer, 'profile', None)
        if not profile or profile.role != 'organizer':
            return Response({
                'status': 'error',
                'message': 'User is not an organizer.'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        follow_obj, created = OrganizerFollow.objects.get_or_create(user=request.user, organizer=organizer)
        if not created:
            follow_obj.delete()
            following = False
            msg = "Unfollowed organizer."
        else:
            following = True
            msg = "Followed organizer."
            # Create a notification for the organizer
            Notification.objects.create(
                user=organizer,
                title="New Follower!",
                content=f"{request.user.get_full_name() or request.user.username} started following you.",
                notification_type="follow",
                related_id=request.user.id
            )
            
        followers_count = organizer.organizer_followers.count()
        return Response({
            'status': 'success',
            'message': msg,
            'is_following': following,
            'followers_count': followers_count
        }, status=status.HTTP_200_OK)


class FollowedOrganizersListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        follows = OrganizerFollow.objects.filter(user=request.user).select_related('organizer')
        organizers_data = []
        for f in follows:
            org = f.organizer
            org_profile = getattr(org, 'organizer_profile', None)
            org_name = org_profile.org_name if org_profile else org.get_full_name() or org.username
            organizers_data.append({
                'id': org.id,
                'username': org.username,
                'name': org_name,
                'email': org.email,
                'bio': org_profile.bio if org_profile else '',
                'phone': org_profile.phone if org_profile else '',
                'website': org_profile.website if org_profile else '',
            })
        return Response({
            'status': 'success',
            'organizers': organizers_data
        }, status=status.HTTP_200_OK)


class EventInterestToggleView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, event_id):
        event = get_object_or_404(Event, id=event_id)
        interest_type = request.data.get('interest', 'interested') # 'interested' or 'not_interested'
        
        is_interested = (interest_type == 'interested')
        
        interest_obj, created = EventInterest.objects.get_or_create(user=request.user, event=event)
        interest_obj.is_interested = is_interested
        interest_obj.save()
        
        return Response({
            'status': 'success',
            'message': f"Marked event as {interest_type.replace('_', ' ')}.",
            'is_interested': is_interested
        }, status=status.HTTP_200_OK)


class InterestedEventsListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        interests = EventInterest.objects.filter(user=request.user, is_interested=True).select_related('event')
        events = [i.event for i in interests]
        serializer = EventSerializer(events, many=True, context={'request': request})
        return Response({
            'status': 'success',
            'events': serializer.data
        }, status=status.HTTP_200_OK)


class EventPinToggleView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, event_id):
        event = get_object_or_404(Event, id=event_id)
        
        # Check permissions: only organizer of the event can pin it
        if event.organizer != request.user:
            return Response({
                'status': 'error',
                'message': 'Permission denied. Only the event organizer can pin this event.'
            }, status=status.HTTP_403_FORBIDDEN)
            
        event.is_pinned = not event.is_pinned
        event.save(update_fields=['is_pinned'])
        
        return Response({
            'status': 'success',
            'message': f"Event {'pinned to top' if event.is_pinned else 'unpinned'}.",
            'is_pinned': event.is_pinned
        }, status=status.HTTP_200_OK)


class ConversationsListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Fetch active chat channels/conversations
        messages = Message.objects.filter(
            Q(sender=request.user) | Q(receiver=request.user)
        ).order_by('-created_at')

        seen_users = set()
        conversations_data = []
        for msg in messages:
            other = msg.receiver if msg.sender == request.user else msg.sender
            if other.id not in seen_users:
                seen_users.add(other.id)
                unread = Message.objects.filter(sender=other, receiver=request.user, is_read=False).count()
                
                # Fetch target's organizer details if applicable
                other_profile = getattr(other, 'organizer_profile', None)
                other_name = other_profile.org_name if other_profile else other.get_full_name() or other.username
                
                conversations_data.append({
                    'other_user_id': other.id,
                    'other_username': other.username,
                    'other_name': other_name,
                    'last_message': msg.content,
                    'unread_count': unread,
                    'created_at': msg.created_at.isoformat()
                })

        return Response({
            'status': 'success',
            'conversations': conversations_data
        }, status=status.HTTP_200_OK)


class UserMessagesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, user_id):
        other_user = get_object_or_404(User, id=user_id)
        
        # Query messages exchange between user and other_user
        msgs = Message.objects.filter(
            Q(sender=request.user, receiver=other_user) | Q(sender=other_user, receiver=request.user)
        ).order_by('created_at')
        
        # Mark received messages from this user as read
        msgs.filter(sender=other_user, receiver=request.user, is_read=False).update(is_read=True)
        
        messages_data = []
        for m in msgs:
            messages_data.append({
                'id': m.id,
                'sender_id': m.sender.id,
                'sender_username': m.sender.username,
                'receiver_id': m.receiver.id,
                'content': m.content,
                'is_read': m.is_read,
                'created_at': m.created_at.isoformat()
            })

        return Response({
            'status': 'success',
            'messages': messages_data
        }, status=status.HTTP_200_OK)


class SendMessageView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        receiver_id = request.data.get('receiver_id')
        content = request.data.get('content', '').strip()

        if not receiver_id or not content:
            return Response({
                'status': 'error',
                'message': 'receiver_id and content are required.'
            }, status=status.HTTP_400_BAD_REQUEST)

        receiver = get_object_or_404(User, id=receiver_id)
        msg = Message.objects.create(
            sender=request.user,
            receiver=receiver,
            content=content
        )
        
        # Notify the receiver about the direct message
        Notification.objects.create(
            user=receiver,
            title="New Message Received",
            content=f"{request.user.get_full_name() or request.user.username} sent you a message: '{content[:50]}...'",
            notification_type="message",
            related_id=request.user.id
        )

        return Response({
            'status': 'success',
            'message': 'Message sent successfully.',
            'sent_message': {
                'id': msg.id,
                'sender_id': request.user.id,
                'receiver_id': receiver.id,
                'content': msg.content,
                'created_at': msg.created_at.isoformat()
            }
        }, status=status.HTTP_201_CREATED)


class NotificationReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        notification = get_object_or_404(Notification, id=pk, user=request.user)
        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return Response({
            'status': 'success',
            'message': 'Notification marked as read.'
        }, status=status.HTTP_200_OK)


class NotificationReadAllView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({
            'status': 'success',
            'message': 'All notifications marked as read.'
        }, status=status.HTTP_200_OK)


class NearbyEventsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        lat = request.query_params.get('lat')
        lng = request.query_params.get('lng')
        radius = float(request.query_params.get('radius', 50)) # km

        if not lat or not lng:
            return Response({
                'status': 'error',
                'message': 'lat and lng are required.'
            }, status=status.HTTP_400_BAD_REQUEST)

        user_lat = float(lat)
        user_lng = float(lng)
        
        events = Event.objects.filter(status='published')
        nearby = []
        for e in events:
            if e.latitude and e.longitude:
                # Simple distance calculation (approximate)
                dist = ((float(e.latitude) - user_lat)**2 + (float(e.longitude) - user_lng)**2)**0.5
                if dist < (radius / 111):
                    e.distance = round(dist * 111, 2)
                    nearby.append(e)
        
        nearby.sort(key=lambda x: getattr(x, 'distance', 0))
        serializer = EventSerializer(nearby, many=True, context={'request': request})
        return Response({
            'status': 'success',
            'events': serializer.data
        }, status=status.HTTP_200_OK)


class CategoryEventsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, category_slug):
        category = get_object_or_404(Category, slug=category_slug)
        events = Event.objects.filter(category=category, status='published')
        serializer = EventSerializer(events, many=True, context={'request': request})
        return Response({
            'status': 'success',
            'category': CategorySerializer(category).data,
            'events': serializer.data
        }, status=status.HTTP_200_OK)


class FeaturedEventsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        events = Event.objects.filter(is_featured=True, status='published')[:10]
        serializer = EventSerializer(events, many=True, context={'request': request})
        return Response({
            'status': 'success',
            'events': serializer.data
        }, status=status.HTTP_200_OK)


class CommentReplyView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, comment_id):
        parent_comment = get_object_or_404(EventComment, id=comment_id)
        content = request.data.get('content')
        if not content:
            return Response({'status': 'error', 'message': 'Content required'}, status=status.HTTP_400_BAD_REQUEST)

        reply = EventComment.objects.create(
            event=parent_comment.event,
            user=request.user,
            parent=parent_comment,
            content=content
        )
        return Response({
            'status': 'success',
            'comment': CommentSerializer(reply, context={'request': request}).data
        }, status=status.HTTP_201_CREATED)


class OrganizerFollowersListView(APIView):
    """List of users following a specific organizer."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, organizer_id):
        organizer = get_object_or_404(User, id=organizer_id)
        # Verify permissions: only the organizer themselves or an admin can see the full list of followers
        if organizer != request.user and not request.user.is_staff:
            return Response({
                'status': 'error',
                'message': 'Permission denied.'
            }, status=status.HTTP_403_FORBIDDEN)
            
        follows = OrganizerFollow.objects.filter(organizer=organizer).select_related('user', 'user__profile')
        followers_data = []
        for f in follows:
            u = f.user
            profile = getattr(u, 'profile', None)
            followers_data.append({
                'id': u.id,
                'username': u.username,
                'name': u.get_full_name() or u.username,
                'email': u.email,
                'photo_url': request.build_absolute_uri(profile.photo.url) if profile and profile.photo else None,
                'followed_at': f.created_at.isoformat()
            })
            
        return Response({
            'status': 'success',
            'followers': followers_data,
            'count': len(followers_data)
        }, status=status.HTTP_200_OK)


class EventDuplicateView(APIView):
    """Duplicate an existing event for the organizer."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        event = get_object_or_404(Event, id=pk)
        if event.organizer != request.user:
            return Response({
                'status': 'error',
                'message': 'Only the organizer can duplicate this event.'
            }, status=status.HTTP_403_FORBIDDEN)
            
        # Duplicate basic event info
        new_event = Event.objects.get(id=pk)
        new_event.pk = None
        new_event.title = f"Copy of {event.title}"
        new_event.status = 'draft'
        new_event.views = 0
        new_event.total_likes = 0
        new_event.total_bookings = 0
        
        # Generate new slug
        base_slug = slugify(new_event.title)
        slug = base_slug
        counter = 1
        while Event.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        new_event.slug = slug
        new_event.save()
        
        # Duplicate ticket tiers
        for tier in event.ticket_tiers.all():
            tier.pk = None
            tier.event = new_event
            tier.save()
            
        # Duplicate speakers
        for speaker in event.speakers.all():
            speaker.pk = None
            speaker.event = new_event
            speaker.save()
            
        return Response({
            'status': 'success',
            'message': 'Event duplicated successfully as draft.',
            'event': EventSerializer(new_event, context={'request': request}).data
        }, status=status.HTTP_201_CREATED)


class OrganizerExportAttendeesView(APIView):
    """Export attendees of an event to CSV."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        event = get_object_or_404(Event, id=pk)
        if event.organizer != request.user and not request.user.is_staff:
            return Response({
                'status': 'error',
                'message': 'Permission denied.'
            }, status=status.HTTP_403_FORBIDDEN)
            
        registrations = Registration.objects.filter(event=event).select_related('user', 'ticket_tier')
        
        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="attendees_{event.slug}.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Name', 'Email', 'Ticket Tier', 'Status', 'Booked At', 'Amount Paid'])
        
        for reg in registrations:
            writer.writerow([
                reg.user.get_full_name() or reg.user.username,
                reg.user.email,
                reg.ticket_tier.name,
                reg.get_status_display(),
                reg.registered_at.strftime("%Y-%m-%d %H:%M"),
                reg.amount_paid
            ])
            
        return response


class OrganizerExportRevenueView(APIView):
    """Export revenue report of an event to CSV."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        event = get_object_or_404(Event, id=pk)
        if event.organizer != request.user and not request.user.is_staff:
            return Response({
                'status': 'error',
                'message': 'Permission denied.'
            }, status=status.HTTP_403_FORBIDDEN)
            
        registrations = Registration.objects.filter(event=event, status__in=['confirmed', 'checked_in']).select_related('ticket_tier')
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="revenue_report_{event.slug}.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Ticket ID', 'Tier', 'Amount Paid', 'Date'])
        
        total_rev = 0
        for reg in registrations:
            total_rev += reg.amount_paid
            writer.writerow([
                reg.ticket_id,
                reg.ticket_tier.name,
                reg.amount_paid,
                reg.registered_at.strftime("%Y-%m-%d %H:%M")
            ])
            
        writer.writerow([])
        writer.writerow(['Total Revenue', '', total_rev, ''])
        
        return response

