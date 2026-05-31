import os
import django
import random
from datetime import timedelta
from django.utils import timezone
from django.utils.text import slugify

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eventsathi.settings')
django.setup()

from django.contrib.auth.models import User
from events.models import Category, Event, TicketTier, Speaker, EventSession, Sponsor
from accounts.models import UserProfile, OrganizerProfile

def seed_data():
    print("Seeding dummy data...")

    # 1. Ensure Categories exist
    categories_data = [
        ('Conference', 'conference', 'bi-people'),
        ('Workshop', 'workshop', 'bi-tools'),
        ('Seminar', 'seminar', 'bi-journal-text'),
        ('Webinar', 'webinar', 'bi-laptop'),
        ('Hackathon', 'hackathon', 'bi-code-slash'),
        ('Cultural', 'cultural', 'bi-music-note-beamed'),
        ('Sports', 'sports', 'bi-trophy'),
        ('Networking', 'networking', 'bi-person-plus'),
        ('Tech Expo', 'tech-expo', 'bi-cpu'),
        ('Music Festival', 'music-festival', 'bi-headphones'),
    ]

    categories = []
    for name, slug, icon in categories_data:
        cat, created = Category.objects.get_or_create(
            slug=slug,
            defaults={'name': name, 'icon': icon, 'description': f"All about {name} events."}
        )
        categories.append(cat)
        if created:
            print(f"Created category: {name}")

    # 2. Get an organizer
    organizer = User.objects.filter(profile__role='organizer').first()
    if not organizer:
        # Create a default organizer if none exists
        organizer = User.objects.create_user('admin_organizer', 'admin@eventsathi.com', 'admin123')
        UserProfile.objects.get_or_create(user=organizer, defaults={'role': 'organizer', 'organization': 'EventSathi HQ'})
        OrganizerProfile.objects.get_or_create(user=organizer, defaults={'org_name': 'EventSathi HQ'})
        print("Created default organizer: admin_organizer")

    # 3. Create 12 dummy events
    event_titles = [
        "Global AI Summit 2026",
        "React Native Workshop: Building for Mobile",
        "Nepal Tech Expo: Innovation Unleashed",
        "Everest Hackathon: Peak Coding",
        "Kathmandu Jazz Festival",
        "Startup Networking Night",
        "Cloud Computing Trends Seminar",
        "Digital Marketing Webinar for Beginners",
        "Corporate Leadership Conference",
        "Annual Sports Meet 2026",
        "Python Backend Masterclass",
        "UI/UX Design Trends for 2027"
    ]

    venues = ["Kathmandu Convention Center", "Online (Zoom)", "Pokhara Exhibition Hall", "Lalitpur Tech Hub", "Bhaktapur Cultural Square", "Radisson Hotel", "Soaltee Crowne Plaza"]
    cities = ["Kathmandu", "Pokhara", "Lalitpur", "Bhaktapur", "Chitwan"]

    now = timezone.now()

    for i, title in enumerate(event_titles):
        slug = slugify(title)
        if Event.objects.filter(slug=slug).exists():
            slug = f"{slug}-{random.randint(100, 999)}"

        start_date = now + timedelta(days=random.randint(5, 60), hours=random.randint(0, 23))
        end_date = start_date + timedelta(hours=random.randint(2, 48))

        is_virtual = random.choice([True, False])
        
        event = Event.objects.create(
            organizer=organizer,
            title=title,
            slug=slug,
            description=f"This is a dummy description for {title}. Join us for an exciting experience where industry experts share their knowledge and network with peers.",
            category=random.choice(categories),
            start_date=start_date,
            end_date=end_date,
            venue=random.choice(venues) if not is_virtual else "Virtual / Online",
            city=random.choice(cities),
            is_virtual=is_virtual,
            virtual_link="https://zoom.us/j/dummy-meeting-id" if is_virtual else "",
            max_capacity=random.randint(50, 1000),
            status='published',
            is_featured=random.choice([True, False]),
            tags="tech,learning,networking" if i % 2 == 0 else "music,culture,fun",
            latitude=27.7172 if not is_virtual else None,
            longitude=85.3240 if not is_virtual else None,
        )
        print(f"Created event: {title}")

        # 4. Create Ticket Tiers
        TicketTier.objects.create(
            event=event,
            name="Early Bird",
            price=random.choice([0.00, 500.00, 1000.00]),
            capacity=event.max_capacity // 4,
            description="Special discount for early registrations."
        )
        TicketTier.objects.create(
            event=event,
            name="Standard Admission",
            price=random.choice([1500.00, 2000.00, 2500.00]),
            capacity=event.max_capacity // 2,
            description="Regular entry to all sessions."
        )
        TicketTier.objects.create(
            event=event,
            name="VIP Pass",
            price=5000.00,
            capacity=event.max_capacity // 10,
            description="Exclusive access to VIP lounge and speakers."
        )

        # 5. Create Speakers
        for j in range(2):
            Speaker.objects.create(
                event=event,
                name=f"Expert Speaker {i}-{j}",
                designation="Senior Engineer" if j == 0 else "Product Manager",
                organization="Tech Giants Inc.",
                bio="Industry veteran with 10+ years of experience in the field."
            )

        # 6. Create Sessions
        EventSession.objects.create(
            event=event,
            title="Opening Keynote",
            description="Introduction and vision for the event.",
            start_time=start_date + timedelta(minutes=30),
            end_time=start_date + timedelta(hours=1, minutes=30),
            track='keynote'
        )
        EventSession.objects.create(
            event=event,
            title="Panel Discussion: Future Trends",
            description="Experts discuss what's next in the industry.",
            start_time=start_date + timedelta(hours=2),
            end_time=start_date + timedelta(hours=3, minutes=30),
            track='panel'
        )

    print("Successfully seeded 10+ dummy events with categories, tiers, speakers, and sessions!")

if __name__ == "__main__":
    seed_data()
