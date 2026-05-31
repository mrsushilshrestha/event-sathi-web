from rest_framework import serializers
from django.contrib.auth.models import User
from accounts.models import UserProfile, OrganizerProfile, Message
from events.models import (
    Event, TicketTier, Registration, Speaker, EventLike, 
    EventComment, Category, EventImage, Payment, Notification
)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'icon', 'description']


class UserProfileSerializer(serializers.ModelSerializer):
    photo_url = serializers.SerializerMethodField()
    cover_photo_url = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = [
            'role', 'bio', 'phone', 'organization', 'designation', 
            'photo', 'photo_url', 'cover_photo', 'cover_photo_url',
            'location', 'linkedin', 'twitter', 'website', 
            'interests', 'preferences', 'is_verified'
        ]
        read_only_fields = ['is_verified']

    def get_photo_url(self, obj):
        if obj.photo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.photo.url)
            return obj.photo.url
        return None

    def get_cover_photo_url(self, obj):
        if obj.cover_photo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.cover_photo.url)
            return obj.cover_photo.url
        return None


class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(required=False)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'profile']

    def update(self, instance, validated_data):
        profile_data = validated_data.pop('profile', None)
        
        # Update user fields
        instance.first_name = validated_data.get('first_name', instance.first_name)
        instance.last_name = validated_data.get('last_name', instance.last_name)
        instance.email = validated_data.get('email', instance.email)
        instance.save()

        # Update profile fields
        if profile_data:
            profile, _ = UserProfile.objects.get_or_create(user=instance)
            for attr, value in profile_data.items():
                setattr(profile, attr, value)
            profile.save()

        return instance


class RegisterSerializer(serializers.ModelSerializer):
    username = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True)
    role = serializers.CharField(default='attendee')
    phone = serializers.CharField(required=False, allow_blank=True)
    org_name = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password', 'role', 'phone', 'org_name']

    def validate_email(self, value):
        if not value:
            raise serializers.ValidationError("Email is required.")
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def create(self, validated_data):
        password = validated_data.pop('password')
        role = validated_data.pop('role', 'attendee')
        if role == 'user':
            role = 'attendee'
        phone = validated_data.pop('phone', '')
        org_name = validated_data.pop('org_name', '')
        
        email = validated_data.get('email')
        username = validated_data.get('username') or email.split('@')[0]
        
        # Ensure username is unique
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        user = User.objects.create(
            username=username,
            email=email,
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            is_active=False  # Require OTP/email verification
        )
        user.set_password(password)
        user.save()

        # Create Profile
        UserProfile.objects.get_or_create(
            user=user,
            defaults={
                'role': role,
                'phone': phone,
                'organization': org_name if role == 'organizer' else ''
            }
        )

        return user


class TicketTierSerializer(serializers.ModelSerializer):
    benefits_list = serializers.SerializerMethodField()

    class Meta:
        model = TicketTier
        fields = ['id', 'name', 'description', 'price', 'capacity', 'benefits', 'benefits_list', 'is_active']

    def get_benefits_list(self, obj):
        return obj.get_benefits_list()


class SpeakerSerializer(serializers.ModelSerializer):
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = Speaker
        fields = ['id', 'name', 'designation', 'organization', 'bio', 'photo', 'photo_url', 'abstract', 'linkedin', 'twitter', 'website']

    def get_photo_url(self, obj):
        if obj.photo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.photo.url)
            return obj.photo.url
        return None


class EventImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = EventImage
        fields = ['id', 'image', 'image_url', 'caption']

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class CommentSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    user_photo = serializers.SerializerMethodField()
    replies = serializers.SerializerMethodField()
    likes_count = serializers.IntegerField(source='likes.count', read_only=True)

    class Meta:
        model = EventComment
        fields = ['id', 'username', 'user_photo', 'content', 'parent', 'replies', 'likes_count', 'created_at']

    def get_user_photo(self, obj):
        profile = getattr(obj.user, 'profile', None)
        if profile and profile.photo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(profile.photo.url)
            return profile.photo.url
        return None

    def get_replies(self, obj):
        if obj.replies.exists():
            return CommentSerializer(obj.replies.all(), many=True, context=self.context).data
        return []


class EventSerializer(serializers.ModelSerializer):
    organizer_name = serializers.CharField(source='organizer.username', read_only=True)
    organizer_org = serializers.SerializerMethodField()
    banner_url = serializers.SerializerMethodField()
    category_detail = CategorySerializer(source='category', read_only=True)
    ticket_tiers = TicketTierSerializer(many=True, read_only=True)
    speakers = SpeakerSerializer(many=True, read_only=True)
    images = EventImageSerializer(many=True, read_only=True)
    registered_count = serializers.IntegerField(source='get_registered_count', read_only=True)
    available_seats = serializers.IntegerField(source='get_available_seats', read_only=True)
    min_price = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()
    comments_count = serializers.IntegerField(source='comments.count', read_only=True)

    class Meta:
        model = Event
        fields = [
            'id', 'title', 'slug', 'description', 'category', 'category_detail',
            'banner', 'banner_url', 'images', 'start_date', 'end_date', 'venue', 
            'city', 'latitude', 'longitude', 'is_virtual', 'virtual_link',
            'max_capacity', 'status', 'is_featured', 'tags', 'organizer', 'organizer_name',
            'organizer_org', 'ticket_tiers', 'speakers', 'registered_count', 'available_seats',
            'min_price', 'total_likes', 'total_bookings', 'popularity_score',
            'comments_count', 'is_liked', 'created_at'
        ]
        read_only_fields = ['organizer', 'slug', 'total_likes', 'total_bookings', 'popularity_score']

    def get_organizer_org(self, obj):
        profile = getattr(obj.organizer, 'profile', None)
        if profile and profile.organization:
            return profile.organization
        return obj.organizer.get_full_name() or obj.organizer.username

    def get_banner_url(self, obj):
        if obj.banner:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.banner.url)
            return obj.banner.url
        return None

    def get_min_price(self, obj):
        return obj.get_min_price()

    def get_likes_count(self, obj):
        return obj.likes.count()

    def get_comments_count(self, obj):
        return obj.comments.count()

    def get_is_liked(self, obj):
        request = self.context.get('request')
        user = request.user if request else None
        if user and user.is_authenticated:
            return obj.likes.filter(user=user).exists()
        return False



class RegistrationSerializer(serializers.ModelSerializer):
    event_details = serializers.SerializerMethodField()
    ticket_tier_name = serializers.CharField(source='ticket_tier.name', read_only=True)
    user_name = serializers.CharField(source='user.username', read_only=True)
    qr_data = serializers.SerializerMethodField()

    class Meta:
        model = Registration
        fields = [
            'id', 'user', 'user_name', 'event', 'event_details', 'ticket_tier', 
            'ticket_tier_name', 'status', 'qr_code', 'qr_data', 'ticket_id', 'registered_at', 
            'checked_in_at', 'amount_paid'
        ]
        read_only_fields = ['user', 'ticket_id', 'qr_code', 'status', 'amount_paid']

    def get_qr_data(self, obj):
        import hashlib
        from django.conf import settings
        secret_key = settings.SECRET_KEY
        token = hashlib.sha256(f"{obj.ticket_id}{secret_key}".encode()).hexdigest()[:8]
        return f"EVENTSATHI:{obj.ticket_id}:{obj.user.id}:{obj.event.id}:{token}"

    def get_event_details(self, obj):
        return {
            'id': obj.event.id,
            'title': obj.event.title,
            'slug': obj.event.slug,
            'venue': obj.event.venue,
            'city': obj.event.city,
            'start_date': obj.event.start_date.isoformat(),
            'banner_url': obj.event.banner.url if obj.event.banner else None
        }


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'user', 'title', 'content', 'notification_type', 'is_read', 'related_id', 'created_at']


class MessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source='sender.username', read_only=True)
    receiver_name = serializers.CharField(source='receiver.username', read_only=True)

    class Meta:
        model = Message
        fields = ['id', 'sender', 'sender_name', 'receiver', 'receiver_name', 'content', 'is_read', 'created_at']


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'registration', 'transaction_id', 'amount', 'currency', 'payment_method', 'status', 'created_at']
